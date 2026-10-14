# Databricks notebook source
# MAGIC %md
# MAGIC # 05 · Forecast model: tomorrow's afternoon peak heat stress
# MAGIC
# MAGIC **The question this notebook answers:** *at 6:30 pm today, how hot (in WBGT) will tomorrow afternoon be at each weather station?*
# MAGIC
# MAGIC **Why it matters for coordinators:** Active Ageing Centre staff plan check-ins the evening before. Knowing that tomorrow afternoon will reach
# MAGIC NEA's **High** heat-stress band (WBGT ≥ 33 °C) lets them call or visit the most vulnerable seniors *before* the hottest hours, rather than react after.
# MAGIC
# MAGIC **What this notebook does, step by step:**
# MAGIC 1. Loads `gold_forecast_features` (built by the pipeline): one row per station per day, with what we know by 6:30 pm and the next day's actual peak.
# MAGIC 2. Explores the data to check which signals actually relate to tomorrow's heat, so the model is built on evidence, not assumptions.
# MAGIC 3. Splits the data **by time** (train on the past, test on the most recent months) so the evaluation mimics real use.
# MAGIC 4. Measures simple **baselines** any forecast must beat.
# MAGIC 5. Trains and tunes a **gradient-boosted tree model**, then tests it on months it has never seen.
# MAGIC 6. Turns each forecast into a **probability** of Moderate and High heat, and checks those probabilities are honest.
# MAGIC 7. Registers the final model in **MLflow / Unity Catalog** as `workspace.heatguard.wbgt_peak_forecaster` (alias `champion`) and saves evaluation tables for the app.
# MAGIC
# MAGIC **Run it:** top to bottom on serverless. It takes a few minutes. Re-run whenever you want to retrain on newer data;
# MAGIC `06_score_forecast` always uses whichever version holds the `champion` alias.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Setup
# MAGIC
# MAGIC Installs MLflow (for experiment tracking and the model registry), scikit-learn (the model) and matplotlib (charts), then restarts Python so the new versions load.

# COMMAND ----------

# MAGIC %pip install -q "mlflow[databricks]>=2.19" "scikit-learn>=1.4" matplotlib

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %md
# MAGIC **Settings.** The model predicts `target_peak_wbgt_c` (tomorrow's afternoon peak) from the feature columns below. Each feature is
# MAGIC explained in the pipeline notebook (`04_pipeline`, section *Gold: model features*). In short:
# MAGIC
# MAGIC - **Recent heat at the station** (today, yesterday, the day before, 7-day average and maximum, today's all-day maximum)
# MAGIC - **The station's usual level** (average of all its earlier days)
# MAGIC - **Island-wide heat today** (average and maximum across stations)
# MAGIC - **Season** (day of year as a circle)
# MAGIC - **NEA's forecast for tomorrow** (temperature, humidity, wind, rain expected island-wide and in the station's region)
# MAGIC - **Haze** (today's 24-hour PSI in the station's region)
# MAGIC - **Location** (latitude, longitude)
# MAGIC
# MAGIC **Time split:** train on targets before 1 Apr 2026, tune on Apr–Jun 2026 (validation), and test on Jul 2026 onwards (the most recent months, never used for training or tuning).

# COMMAND ----------

import math, datetime, json, itertools
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import mlflow
from mlflow.models import infer_signature
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance

CATALOG, SCHEMA = "workspace", "heatguard"
FEATURE_TABLE = f"{CATALOG}.{SCHEMA}.gold_forecast_features"
MODEL_NAME = f"{CATALOG}.{SCHEMA}.wbgt_peak_forecaster"
TARGET = "target_peak_wbgt_c"
WBGT_MODERATE, WBGT_HIGH = 31.0, 33.0
VALID_START, TEST_START = pd.Timestamp("2026-04-01"), pd.Timestamp("2026-07-01")

FEATURES = [
    "peak_d", "peak_d1", "peak_d2", "peak_mean_7d", "peak_max_7d", "daily_max_d", "station_mean_to_date",
    "network_mean_peak_d", "network_max_peak_d", "doy_sin", "doy_cos",
    "nea_temp_high_c", "nea_temp_low_c", "nea_rh_high_pct", "nea_rh_low_pct", "nea_wind_high_kmh",
    "nea_rain_expected", "nea_region_afternoon_rain", "psi_24h_d", "latitude", "longitude",
]
FEATURE_LABELS = {
    "peak_d": "Today's afternoon peak", "peak_d1": "Yesterday's peak", "peak_d2": "Peak 2 days ago",
    "peak_mean_7d": "7-day average peak", "peak_max_7d": "7-day highest peak", "daily_max_d": "Today's all-day maximum",
    "station_mean_to_date": "Station's usual peak", "network_mean_peak_d": "Island average peak today",
    "network_max_peak_d": "Island highest peak today", "doy_sin": "Season (sin)", "doy_cos": "Season (cos)",
    "nea_temp_high_c": "NEA forecast max temperature", "nea_temp_low_c": "NEA forecast min temperature",
    "nea_rh_high_pct": "NEA forecast max humidity", "nea_rh_low_pct": "NEA forecast min humidity",
    "nea_wind_high_kmh": "NEA forecast wind speed", "nea_rain_expected": "NEA expects rain (island)",
    "nea_region_afternoon_rain": "NEA expects afternoon rain (region)", "psi_24h_d": "Haze today (PSI)",
    "latitude": "Latitude", "longitude": "Longitude",
}

def band(x):
    return np.where(x >= WBGT_HIGH, "High", np.where(x >= WBGT_MODERATE, "Moderate", "Low"))

user = spark.sql("SELECT current_user()").first()[0]
mlflow.set_registry_uri("databricks-uc")
mlflow.set_experiment(f"/Users/{user}/heatguard_wbgt_forecast")
plt.rcParams.update({"figure.dpi": 110, "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.alpha": 0.3})
print("Experiment:", f"/Users/{user}/heatguard_wbgt_forecast", "| Registered model:", MODEL_NAME)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Load the data and check what we have
# MAGIC
# MAGIC We keep rows where tomorrow's actual peak is known (the target) and there is at least some recent heat information.
# MAGIC The table below shows, for each feature, the share of rows where it is **missing**.
# MAGIC
# MAGIC **How to read it:** recent-heat features are almost always present. The NEA forecast features are missing on roughly a quarter of days,
# MAGIC because on those days no forecast issued by 6:30 pm the day before was captured by the API history. We do **not** fill these in with guesses:
# MAGIC the model we use (histogram gradient boosting) handles missing values natively by learning the best direction to send them at each split,
# MAGIC which is more honest than inventing a value.

# COMMAND ----------

raw = spark.table(FEATURE_TABLE).toPandas()
for c in ["feature_date", "target_date"]:
    raw[c] = pd.to_datetime(raw[c])
for c in FEATURES + [TARGET]:
    raw[c] = pd.to_numeric(raw[c], errors="coerce")

data = raw[raw[TARGET].notna() & (raw["peak_d"].notna() | raw["peak_mean_7d"].notna())].copy()
data["split"] = np.where(data["target_date"] < VALID_START, "train", np.where(data["target_date"] < TEST_START, "validation", "test"))

overview = (data.groupby("split")
            .agg(rows=(TARGET, "size"), stations=("station_id", "nunique"),
                 first_day=("target_date", "min"), last_day=("target_date", "max"),
                 avg_peak=(TARGET, "mean"), share_high=(TARGET, lambda s: (s >= WBGT_HIGH).mean()))
            .reindex(["train", "validation", "test"]))
display(overview.reset_index())

missing = (data[FEATURES].isna().mean().rename("share_missing").to_frame()
           .assign(feature=lambda d: d.index.map(FEATURE_LABELS)).sort_values("share_missing", ascending=False))
display(missing.reset_index(names="column"))
print(f"{len(data):,} labelled station-days from {data.target_date.min():%d %b %Y} to {data.target_date.max():%d %b %Y}; "
      f"{(data[TARGET] >= WBGT_HIGH).mean():.1%} reached High, {(data[TARGET] >= WBGT_MODERATE).mean():.1%} reached Moderate or higher.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Exploring the data
# MAGIC
# MAGIC Before modelling we check four questions with charts. Each answer shapes a modelling decision.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3a. How hot do afternoons get, and how often is it High?
# MAGIC
# MAGIC **Chart:** distribution of tomorrow's afternoon peak across all station-days, with NEA's band cut-offs as dashed lines.
# MAGIC
# MAGIC **Why we look:** if High days are rare, a model can score a low average error while still missing most of them. So besides the
# MAGIC average error, we must report **how many High days the model catches** (recall) and how often its High warnings are right (precision).

# COMMAND ----------

fig, ax = plt.subplots(figsize=(9, 4))
ax.hist(data[TARGET], bins=np.arange(24, 37.01, 0.25), color="#6b8fb5", edgecolor="white")
for x, lbl, col in [(WBGT_MODERATE, "Moderate ≥ 31 °C", "#e0a030"), (WBGT_HIGH, "High ≥ 33 °C", "#c0392b")]:
    ax.axvline(x, ls="--", color=col, lw=1.5); ax.text(x + 0.08, ax.get_ylim()[1] * 0.92, lbl, color=col, fontsize=9)
ax.set_xlabel("Afternoon peak WBGT (°C)"); ax.set_ylabel("Station-days")
ax.set_title("Afternoon peak WBGT, all stations and days")
fig.tight_layout(); fig_dist = fig; plt.show()

shares = pd.Series(band(data[TARGET].values)).value_counts(normalize=True).reindex(["Low", "Moderate", "High"])
print("Share of station-days by band:", ", ".join(f"{k} {v:.1%}" for k, v in shares.items()))

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3b. Is there a seasonal pattern?
# MAGIC
# MAGIC **Chart:** for each calendar month, the average afternoon peak (bars) and the share of station-days that reached High (line).
# MAGIC
# MAGIC **Why we look:** Singapore's inter-monsoon months are known to be the hottest. If the data shows the same pattern, a season feature
# MAGIC is justified. It also tells us that the test months (Jul–Oct) include a hot season (Sep–Oct), so the test is a fair challenge.

# COMMAND ----------

monthly = (data.assign(month=data.target_date.dt.month)
           .groupby("month").agg(avg_peak=(TARGET, "mean"), share_high=(TARGET, lambda s: (s >= WBGT_HIGH).mean()), n=(TARGET, "size")))
fig, ax = plt.subplots(figsize=(9, 4))
ax.bar(monthly.index, monthly.avg_peak, color="#6b8fb5")
ax.set_ylim(monthly.avg_peak.min() - 1, monthly.avg_peak.max() + 0.6)
ax.set_xticks(range(1, 13)); ax.set_xticklabels(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])
ax.set_ylabel("Average afternoon peak (°C)")
ax2 = ax.twinx(); ax2.plot(monthly.index, monthly.share_high * 100, color="#c0392b", marker="o"); ax2.set_ylabel("% of station-days High", color="#c0392b")
ax2.grid(False); ax.set_title("Seasonal pattern: average peak (bars) and share of High days (line)")
fig.tight_layout(); fig_season = fig; plt.show()
display(monthly.reset_index().round(3))

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3c. Does today's heat predict tomorrow's?
# MAGIC
# MAGIC **Chart:** each dot is one station-day: today's afternoon peak (x) against tomorrow's (y). The diagonal is "tomorrow = today".
# MAGIC
# MAGIC **Why we look:** if the dots hug the diagonal, weather is persistent and "tomorrow = today" is a strong baseline that our model must beat.
# MAGIC The spread around the line is the part of tomorrow's heat that today alone can't explain — that is what NEA's forecast and the other features need to capture.

# COMMAND ----------

sub = data.dropna(subset=["peak_d"])
r = np.corrcoef(sub.peak_d, sub[TARGET])[0, 1]
fig, ax = plt.subplots(figsize=(5.5, 5.5))
ax.scatter(sub.peak_d, sub[TARGET], s=4, alpha=0.25, color="#34495e")
lims = [24, 37]; ax.plot(lims, lims, color="#c0392b", lw=1, label="tomorrow = today")
ax.set_xlim(lims); ax.set_ylim(lims); ax.set_xlabel("Today's afternoon peak (°C)"); ax.set_ylabel("Tomorrow's afternoon peak (°C)")
ax.set_title(f"Persistence: correlation r = {r:.2f}"); ax.legend(loc="upper left")
fig.tight_layout(); fig_persist = fig; plt.show()
print(f"Correlation between today's and tomorrow's peak: {r:.2f}; average absolute day-to-day change: {np.mean(np.abs(sub.peak_d - sub[TARGET])):.2f} °C")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3d. Do NEA's forecast and haze add information?
# MAGIC
# MAGIC **Charts:** (left) tomorrow's peak when NEA does / doesn't expect afternoon rain in the station's region; (middle) tomorrow's peak against
# MAGIC NEA's forecast maximum temperature; (right) tomorrow's peak against today's haze level (PSI), averaged within PSI bins.
# MAGIC
# MAGIC **Why we look:** these are the features that can tell us something *new* about tomorrow beyond persistence. A visible difference in the
# MAGIC left and middle charts means NEA's forecast carries signal. The haze chart checks our assumption that thick haze lowers the peak by blocking sunlight.

# COMMAND ----------

fig, axes = plt.subplots(1, 3, figsize=(13, 4))
rain = data.dropna(subset=["nea_region_afternoon_rain"])
groups = [rain.loc[rain.nea_region_afternoon_rain == v, TARGET] for v in (0, 1)]
axes[0].boxplot(groups, showfliers=False)
axes[0].set_xticks([1, 2]); axes[0].set_xticklabels(["No rain expected", "Rain expected"])
axes[0].set_ylabel("Tomorrow's afternoon peak (°C)"); axes[0].set_title("NEA afternoon outlook (region)")

temp = data.dropna(subset=["nea_temp_high_c"]).groupby("nea_temp_high_c")[TARGET].agg(["mean", "size"])
temp = temp[temp["size"] >= 30]
axes[1].plot(temp.index, temp["mean"], marker="o", color="#e67e22")
axes[1].set_xlabel("NEA forecast max temperature (°C)"); axes[1].set_title("NEA temperature forecast")

hz = data.dropna(subset=["psi_24h_d"]).assign(psi_bin=lambda d: pd.cut(d.psi_24h_d, [0, 25, 50, 75, 100, 150, 250]))
hzg = hz.groupby("psi_bin", observed=True)[TARGET].agg(["mean", "size"])
axes[2].bar([str(i) for i in hzg.index], hzg["mean"], color="#95a5a6")
axes[2].set_ylim(hzg["mean"].min() - 0.8, hzg["mean"].max() + 0.5)
axes[2].set_xlabel("Today's 24-hour PSI"); axes[2].set_title("Haze today"); axes[2].tick_params(axis="x", rotation=30)
fig.tight_layout(); fig_signals = fig; plt.show()

print("Average peak, no rain expected vs rain expected:", [round(g.mean(), 2) for g in groups])
display(temp.reset_index().round(2)); display(hzg.reset_index().astype({"psi_bin": str}).round(2))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Time-based split and baselines
# MAGIC
# MAGIC **Why split by time, not at random:** weather on neighbouring days is strongly related. A random split would put 14 Oct in training
# MAGIC and 15 Oct in testing, letting the model "see" the answer through its neighbour and look far better than it will be in real use.
# MAGIC Training only on the past and testing on later months is exactly how the model will be used.
# MAGIC
# MAGIC **Baselines** — the simple rules any model must beat to be worth using:
# MAGIC | Baseline | Rule |
# MAGIC |---|---|
# MAGIC | Persistence | Tomorrow's peak = today's peak |
# MAGIC | 7-day average | Tomorrow's peak = this station's average peak over the last 7 days |
# MAGIC | Station's usual level | Tomorrow's peak = this station's average peak over all earlier days |
# MAGIC
# MAGIC **How we score forecasts:**
# MAGIC - **MAE** (mean absolute error): the average size of the miss in °C. Lower is better.
# MAGIC - **Within ±1 °C**: share of forecasts within one degree.
# MAGIC - **Band accuracy**: share of days where the forecast band (Low / Moderate / High) is right.
# MAGIC - **High recall**: of the days that really were High, how many we warned about. **High precision**: of our High warnings, how many were right.
# MAGIC   For outreach, recall matters most: a missed High day is worse than an extra phone call.

# COMMAND ----------

train, valid, test = (data[data.split == s].copy() for s in ("train", "validation", "test"))

def baselines(df):
    fallback = df["peak_mean_7d"].fillna(df["network_mean_peak_d"])
    return {
        "Persistence (tomorrow = today)": df["peak_d"].fillna(fallback),
        "7-day average": df["peak_mean_7d"].fillna(df["peak_d"]).fillna(df["network_mean_peak_d"]),
        "Station's usual level": df["station_mean_to_date"].fillna(fallback),
    }

def scores(y, p, prob_high=None):
    y, p = np.asarray(y, float), np.asarray(p, float)
    yb, pb = band(y), band(p)
    hi, phi = yb == "High", pb == "High"
    mod, pmod = y >= WBGT_MODERATE, p >= WBGT_MODERATE
    return {
        "MAE (°C)": np.mean(np.abs(y - p)),
        "RMSE (°C)": math.sqrt(np.mean((y - p) ** 2)),
        "Within ±1 °C": np.mean(np.abs(y - p) <= 1.0),
        "Band accuracy": np.mean(yb == pb),
        "High recall": hi[phi].sum() / hi.sum() if hi.sum() else np.nan,
        "High precision": hi[phi].sum() / phi.sum() if phi.sum() else np.nan,
        "Moderate+ recall": mod[pmod].sum() / mod.sum() if mod.sum() else np.nan,
        "Moderate+ precision": mod[pmod].sum() / pmod.sum() if pmod.sum() else np.nan,
        "Days": len(y),
    }

rows = []
for split_name, df in [("validation", valid), ("test", test)]:
    for name, pred in baselines(df).items():
        rows.append({"model": name, "split": split_name, **scores(df[TARGET], pred)})
baseline_scores = pd.DataFrame(rows)
display(baseline_scores.round(3))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Train and tune the model
# MAGIC
# MAGIC **Model:** `HistGradientBoostingRegressor` (scikit-learn). It builds hundreds of small decision trees, each correcting the previous ones' errors.
# MAGIC We chose it because it:
# MAGIC - captures non-linear effects and interactions (e.g. "hot today **and** no rain expected tomorrow") that a straight-line model can't;
# MAGIC - handles missing NEA forecasts natively, without guessing values;
# MAGIC - trains in seconds on our ~10,000 rows, so it can be retrained daily on Free Edition.
# MAGIC
# MAGIC **Tuning:** we try a small grid of settings (learning rate, tree size, minimum rows per leaf), train each on the **training** period,
# MAGIC and pick the one with the lowest MAE on the **validation** period. The test period stays untouched until the very end.

# COMMAND ----------

GRID = {"learning_rate": [0.03, 0.08], "max_leaf_nodes": [15, 31], "min_samples_leaf": [20, 60], "l2_regularization": [0.0, 1.0]}

def make_model(**params):
    return HistGradientBoostingRegressor(loss="squared_error", max_iter=400, early_stopping=False, random_state=42, **params)

tuning = []
for values in itertools.product(*GRID.values()):
    params = dict(zip(GRID.keys(), values))
    m = make_model(**params).fit(train[FEATURES], train[TARGET])
    tuning.append({**params, **{f"val {k}": v for k, v in scores(valid[TARGET], m.predict(valid[FEATURES])).items() if k in ("MAE (°C)", "High recall", "Band accuracy")}})
tuning = pd.DataFrame(tuning).sort_values("val MAE (°C)")
best_params = {k: type(GRID[k][0])(tuning.iloc[0][k]) for k in GRID}   # back to each setting's own type (int or float)
display(tuning.round(4))
print("Best settings on validation:", best_params)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Test on months the model has never seen
# MAGIC
# MAGIC We now retrain with the best settings on **train + validation** (everything before July 2026) and forecast the **test** period (July 2026 onwards).
# MAGIC This is the honest estimate of how well the model will do in real use. The chart compares it with the baselines on the same days.

# COMMAND ----------

dev = pd.concat([train, valid])
model_dev = make_model(**best_params).fit(dev[FEATURES], dev[TARGET])
test["pred_model"] = model_dev.predict(test[FEATURES])
for name, pred in baselines(test).items():
    test[f"pred_{name}"] = pred

test_scores = pd.DataFrame([{"model": "HeatGuard model (gradient boosting)", "split": "test", **scores(test[TARGET], test.pred_model)}]
                           + [r for r in baseline_scores.to_dict("records") if r["split"] == "test"])
display(test_scores.round(3))

best_baseline = test_scores.iloc[1:].sort_values("MAE (°C)").iloc[0]
model_mae = test_scores.iloc[0]["MAE (°C)"]
improvement = 1 - model_mae / best_baseline["MAE (°C)"]
print(f"Test MAE: model {model_mae:.3f} °C vs best baseline ({best_baseline['model']}) {best_baseline['MAE (°C)']:.3f} °C "
      f"→ {improvement:.1%} smaller errors.")

fig, axes = plt.subplots(1, 2, figsize=(12, 4))
order = test_scores.sort_values("MAE (°C)")
colors = ["#27ae60" if m.startswith("HeatGuard") else "#95a5a6" for m in order.model]
axes[0].barh(order.model, order["MAE (°C)"], color=colors); axes[0].invert_yaxis()
axes[0].set_xlabel("Average error (°C) — lower is better"); axes[0].set_title("Test period: average error")
w = 0.38; idx = np.arange(len(test_scores))
axes[1].bar(idx - w / 2, test_scores["High recall"], w, label="High recall (caught)", color="#c0392b")
axes[1].bar(idx + w / 2, test_scores["Moderate+ recall"], w, label="Moderate+ recall", color="#e0a030")
axes[1].set_xticks(idx); axes[1].set_xticklabels([m.split(" (")[0] for m in test_scores.model], rotation=15, fontsize=8)
axes[1].set_ylim(0, 1); axes[1].set_title("Test period: share of hot days caught"); axes[1].legend(fontsize=8)
fig.tight_layout(); fig_compare = fig; plt.show()

# COMMAND ----------

# MAGIC %md
# MAGIC ### Where does the model go wrong?
# MAGIC
# MAGIC **Left:** forecast vs actual peak on the test period. Points near the diagonal are good forecasts; the shaded box marks High days.
# MAGIC **Right:** average error by month, to check the model is not good in some months and poor in others.

# COMMAND ----------

fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
axes[0].scatter(test[TARGET], test.pred_model, s=6, alpha=0.3, color="#2c3e50")
axes[0].plot([25, 37], [25, 37], color="#c0392b", lw=1)
axes[0].axvspan(WBGT_HIGH, 37, color="#c0392b", alpha=0.06); axes[0].axhspan(WBGT_HIGH, 37, color="#c0392b", alpha=0.06)
axes[0].set_xlim(25, 37); axes[0].set_ylim(25, 37)
axes[0].set_xlabel("Actual afternoon peak (°C)"); axes[0].set_ylabel("Forecast (°C)"); axes[0].set_title("Forecast vs actual (test)")
bymonth = test.assign(m=test.target_date.dt.strftime("%Y-%m"), err=np.abs(test[TARGET] - test.pred_model),
                      err_base=np.abs(test[TARGET] - test[f"pred_{best_baseline['model']}"])).groupby("m")[["err", "err_base"]].mean()
x = np.arange(len(bymonth))
axes[1].bar(x - 0.2, bymonth.err, 0.4, label="Model", color="#27ae60"); axes[1].bar(x + 0.2, bymonth.err_base, 0.4, label=best_baseline["model"], color="#95a5a6")
axes[1].set_xticks(x); axes[1].set_xticklabels(bymonth.index); axes[1].set_ylabel("Average error (°C)"); axes[1].set_title("Error by month (test)"); axes[1].legend(fontsize=8)
fig.tight_layout(); fig_errors = fig; plt.show()
display(bymonth.reset_index().round(3))

# COMMAND ----------

# MAGIC %md
# MAGIC ### Which features does the model rely on?
# MAGIC
# MAGIC **Method — permutation importance:** we shuffle one feature at a time on the test data and measure how much worse the forecasts get.
# MAGIC A big increase in error means the model leans heavily on that feature; near zero means it barely uses it.
# MAGIC This is more trustworthy than the model's internal importance scores because it is measured on unseen data.

# COMMAND ----------

pi = permutation_importance(model_dev, test[FEATURES], test[TARGET], scoring="neg_mean_absolute_error", n_repeats=5, random_state=42)
importance = (pd.DataFrame({"column": FEATURES, "feature": [FEATURE_LABELS[f] for f in FEATURES],
                            "mae_increase_c": pi.importances_mean, "std": pi.importances_std})
              .sort_values("mae_increase_c", ascending=False))
fig, ax = plt.subplots(figsize=(8, 6))
top = importance.head(12).iloc[::-1]
ax.barh(top.feature, top.mae_increase_c, xerr=top["std"], color="#6b8fb5")
ax.set_xlabel("Increase in average error when shuffled (°C)"); ax.set_title("What the model relies on (test period)")
fig.tight_layout(); fig_importance = fig; plt.show()
display(importance.round(4))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. From a number to a chance of High heat
# MAGIC
# MAGIC A single number ("32.4 °C") hides uncertainty. Coordinators can act better on "**40% chance of High**".
# MAGIC
# MAGIC **Method:** the model's errors on the validation period are roughly bell-shaped (normal), with a typical spread σ.
# MAGIC So for a forecast *f*, the chance the real peak reaches 33 °C is the chance a normal value centred on *f* with spread σ is above 33.
# MAGIC σ is measured on validation data (a model trained on the training period only) so it reflects real out-of-sample errors.
# MAGIC
# MAGIC **Check (reliability chart):** on the test period we group forecasts by their predicted chance (0–10%, 10–20%, …) and compare with how often
# MAGIC High actually happened. Honest probabilities sit on the diagonal: when we say 30%, it happens about 30% of the time.
# MAGIC The **Brier score** summarises this (0 = perfect; lower is better); we compare it with always predicting the long-run average rate.

# COMMAND ----------

def normal_exceed(mu, sigma, threshold):
    z = (threshold - np.asarray(mu, float)) / sigma
    return 0.5 * np.vectorize(math.erfc)(z / math.sqrt(2))

model_train_only = make_model(**best_params).fit(train[FEATURES], train[TARGET])
val_resid = valid[TARGET] - model_train_only.predict(valid[FEATURES])
sigma = float(np.std(val_resid))
test["prob_high"] = normal_exceed(test.pred_model, sigma, WBGT_HIGH)
test["prob_moderate_plus"] = normal_exceed(test.pred_model, sigma, WBGT_MODERATE)

def brier(p, y):
    return float(np.mean((np.asarray(p) - np.asarray(y, float)) ** 2))

calib = {}
fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
for ax, (col, thr, label) in zip(axes, [("prob_high", WBGT_HIGH, "High (≥ 33 °C)"), ("prob_moderate_plus", WBGT_MODERATE, "Moderate or higher (≥ 31 °C)")]):
    y = (test[TARGET] >= thr).astype(int)
    bins = pd.cut(test[col], np.linspace(0, 1, 11), include_lowest=True)
    rel = test.assign(y=y).groupby(bins, observed=True).agg(pred=(col, "mean"), obs=("y", "mean"), n=("y", "size"))
    ax.plot([0, 1], [0, 1], color="#7f8c8d", ls="--", lw=1, label="perfectly honest")
    ax.scatter(rel.pred, rel.obs, s=np.clip(rel.n, 10, 300), color="#c0392b" if col == "prob_high" else "#e0a030", alpha=0.8, label="test forecasts (size = days)")
    ax.set_xlabel("Predicted chance"); ax.set_ylabel("Observed frequency"); ax.set_title(f"Reliability: {label}"); ax.legend(fontsize=8)
    clim = float(((train[TARGET] >= thr).mean()))
    calib[col] = {"brier_model": brier(test[col], y), "brier_climatology": brier(np.full(len(y), clim), y)}
fig.tight_layout(); fig_reliability = fig; plt.show()
print(f"Error spread σ (validation) = {sigma:.3f} °C")
display(pd.DataFrame(calib).T.round(4))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. Final model: train on everything, register in Unity Catalog
# MAGIC
# MAGIC With the settings chosen and the test result recorded, we train the production model on **all** labelled days (so it learns from the
# MAGIC most recent weather too) and wrap it with the probability step into one MLflow model. Given the feature columns, it returns:
# MAGIC `predicted_peak_wbgt_c`, `predicted_band`, `prob_moderate_plus` and `prob_high`.
# MAGIC
# MAGIC **What gets logged to MLflow:** the settings, the test-period scores of every model and baseline, all charts above, and the model itself.
# MAGIC The model is registered as **`workspace.heatguard.wbgt_peak_forecaster`** and the new version gets the alias **`champion`**, which
# MAGIC `06_score_forecast` uses. Unity Catalog records lineage from `gold_forecast_features` to the model.
# MAGIC
# MAGIC σ for the final model is the spread of test-period errors (out-of-sample errors on the most recent months).

# COMMAND ----------

class WbgtPeakForecaster(mlflow.pyfunc.PythonModel):
    """Forecast tomorrow's afternoon peak WBGT and the chance of Moderate+ / High heat."""
    def __init__(self, model, features, sigma, moderate=WBGT_MODERATE, high=WBGT_HIGH):
        self.model, self.features, self.sigma, self.moderate, self.high = model, features, sigma, moderate, high

    def predict(self, context, model_input):
        X = model_input[self.features].astype("float64")
        mu = self.model.predict(X)
        z = lambda t: (t - mu) / self.sigma
        erfc = np.vectorize(math.erfc)
        return pd.DataFrame({
            "predicted_peak_wbgt_c": np.round(mu, 2),
            "predicted_band": np.where(mu >= self.high, "High", np.where(mu >= self.moderate, "Moderate", "Low")),
            "prob_moderate_plus": np.round(0.5 * erfc(z(self.moderate) / math.sqrt(2)), 4),
            "prob_high": np.round(0.5 * erfc(z(self.high) / math.sqrt(2)), 4),
        })

final_sigma = float(np.std(test[TARGET] - test.pred_model))
final_model = make_model(**best_params).fit(data[FEATURES], data[TARGET])
wrapped = WbgtPeakForecaster(final_model, FEATURES, final_sigma)
example = data[FEATURES].head(5).astype("float64")
signature = infer_signature(example, wrapped.predict(None, example))

with mlflow.start_run(run_name=f"wbgt_peak_forecaster_{datetime.date.today():%Y%m%d}") as run:
    mlflow.log_params({**best_params, "max_iter": 400, "features": len(FEATURES), "train_rows": len(data),
                       "sigma_c": round(final_sigma, 4), "test_start": str(TEST_START.date()), "valid_start": str(VALID_START.date())})
    for _, r_ in test_scores.iterrows():
        prefix = "model" if r_["model"].startswith("HeatGuard") else "baseline_" + r_["model"].split(" (")[0].lower().replace(" ", "_").replace("'", "")
        for k in ("MAE (°C)", "RMSE (°C)", "Within ±1 °C", "Band accuracy", "High recall", "High precision", "Moderate+ recall"):
            key = k.lower().replace(" (°c)", "").replace(" ±1 °c", "_1c").replace("+", "_plus").replace(" ", "_")
            mlflow.log_metric(f"test_{prefix}_{key}", float(r_[k]) if pd.notna(r_[k]) else 0.0)
    mlflow.log_metric("test_improvement_vs_best_baseline", float(improvement))
    for k, v in calib.items():
        mlflow.log_metrics({f"test_{k}_brier": v["brier_model"], f"test_{k}_brier_climatology": v["brier_climatology"]})
    for name, f in [("distribution", fig_dist), ("season", fig_season), ("persistence", fig_persist), ("signals", fig_signals),
                    ("comparison", fig_compare), ("errors", fig_errors), ("importance", fig_importance), ("reliability", fig_reliability)]:
        mlflow.log_figure(f, f"charts/{name}.png")
    info = mlflow.pyfunc.log_model(
        artifact_path="model", python_model=wrapped, signature=signature, input_example=example,
        registered_model_name=MODEL_NAME)
    run_id = run.info.run_id

client = mlflow.MlflowClient()
version = max(int(v.version) for v in client.search_model_versions(f"name='{MODEL_NAME}'"))
client.set_registered_model_alias(MODEL_NAME, "champion", version)
client.update_registered_model(MODEL_NAME, description=(
    "Forecasts tomorrow's afternoon (12:00-17:59 SGT) peak WBGT per NEA station from today's heat, NEA's 24-hour forecast, season and haze. "
    "Returns the forecast, its NEA band, and the chance of Moderate (>= 31 C) and High (>= 33 C) heat. Trained by notebook 05_forecast_model."))
print(f"Registered {MODEL_NAME} version {version} with alias 'champion' (run {run_id})")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 9. Save evaluation tables for the app and Genie
# MAGIC
# MAGIC So that coordinators (and judges) can see *how good the forecast is* without opening MLflow, we save three tables:
# MAGIC - **`ml_model_evaluation`** — test-period scores of the model and each baseline.
# MAGIC - **`ml_backtest_predictions`** — every test-period forecast next to what actually happened (for the "how accurate has it been?" chart).
# MAGIC - **`ml_feature_importance`** — which features the model relies on, in plain English.

# COMMAND ----------

trained_at = datetime.datetime.now(datetime.timezone.utc)
evaluation = test_scores.rename(columns=lambda c: c.lower().replace(" (°c)", "_c").replace(" ±1 °c", "_1c").replace("+", "_plus").replace(" ", "_"))
evaluation = evaluation.assign(model_version=str(version), sigma_c=final_sigma, trained_at=trained_at,
                               test_period=f"{test.target_date.min():%d %b %Y} – {test.target_date.max():%d %b %Y}")
(spark.createDataFrame(evaluation).write.mode("overwrite").option("overwriteSchema", "true")
      .saveAsTable(f"{CATALOG}.{SCHEMA}.ml_model_evaluation"))

backtest = test[["station_id", "station_name", "region", "feature_date", "target_date", TARGET, "pred_model",
                 f"pred_{best_baseline['model']}", "prob_moderate_plus", "prob_high"]].rename(columns={
    TARGET: "actual_peak_wbgt_c", "pred_model": "predicted_peak_wbgt_c", f"pred_{best_baseline['model']}": "baseline_peak_wbgt_c"})
backtest["feature_date"] = backtest.feature_date.dt.date
backtest["target_date"] = backtest.target_date.dt.date
backtest = backtest.assign(actual_band=band(backtest.actual_peak_wbgt_c.values), predicted_band=band(backtest.predicted_peak_wbgt_c.values),
                           baseline_name=best_baseline["model"], model_version=str(version))
(spark.createDataFrame(backtest).write.mode("overwrite").option("overwriteSchema", "true")
      .saveAsTable(f"{CATALOG}.{SCHEMA}.ml_backtest_predictions"))

(spark.createDataFrame(importance.assign(model_version=str(version))).write.mode("overwrite").option("overwriteSchema", "true")
      .saveAsTable(f"{CATALOG}.{SCHEMA}.ml_feature_importance"))

for t, c in [("ml_model_evaluation", "Forecast model vs baselines on the held-out test period (latest training run of 05_forecast_model)."),
             ("ml_backtest_predictions", "Test-period forecasts of tomorrow's afternoon peak WBGT next to the actual value and the best baseline."),
             ("ml_feature_importance", "Permutation importance of each forecast feature on the test period (increase in average error when shuffled).")]:
    spark.sql(f"COMMENT ON TABLE {CATALOG}.{SCHEMA}.{t} IS '{c}'")
print("Saved ml_model_evaluation, ml_backtest_predictions, ml_feature_importance")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 10. Summary
# MAGIC
# MAGIC The cell below prints the headline results of this run in plain English, ready to paste into the decision log or the pitch.

# COMMAND ----------

m = test_scores.iloc[0]
print(f"""HeatGuard forecast model v{version} (trained {trained_at:%d %b %Y})
- Test period: {test.target_date.min():%d %b %Y} to {test.target_date.max():%d %b %Y}, {len(test):,} station-days never used for training.
- Average error {m['MAE (°C)']:.2f} °C vs {best_baseline['MAE (°C)']:.2f} °C for the best simple rule ({best_baseline['model']}): {improvement:.0%} smaller.
- Within ±1 °C on {m['Within ±1 °C']:.0%} of days; correct heat band on {m['Band accuracy']:.0%} of days.
- High heat days: caught {m['High recall']:.0%} (High recall); {m['High precision']:.0%} of High warnings were right.
- Moderate-or-higher days: caught {m['Moderate+ recall']:.0%}.
- Probabilities: Brier score for High {calib['prob_high']['brier_model']:.3f} vs {calib['prob_high']['brier_climatology']:.3f} for always guessing the average rate.
- Biggest drivers: {', '.join(importance.feature.head(3))}.""")
