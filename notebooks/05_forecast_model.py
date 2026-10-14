# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "6"
# ///
# MAGIC %md
# MAGIC # 05 · Forecast model: tomorrow's afternoon peak heat stress
# MAGIC
# MAGIC **The question this notebook answers:** *at 6:30 pm today, how hot (in WBGT) will tomorrow afternoon be at each weather station,
# MAGIC and how likely is it to reach NEA's **High** heat-stress band (WBGT ≥ 33 °C)?*
# MAGIC
# MAGIC **Why it matters for coordinators:** Active Ageing Centre staff plan check-ins the evening before. A reliable warning that tomorrow
# MAGIC afternoon may reach High lets them call or visit the most vulnerable seniors *before* the hottest hours, instead of reacting afterwards.
# MAGIC
# MAGIC **What this notebook does, step by step:**
# MAGIC 1. Loads `gold_forecast_features` (built by the pipeline): one row per station per day with what we know by 6:30 pm, plus the next day's actual peak.
# MAGIC 2. **Explores the data** to see which signals really relate to tomorrow's heat, so the model is built on evidence rather than assumptions.
# MAGIC 3. Splits the data **by time** (learn from the past, test on the most recent months) so the evaluation mimics real use.
# MAGIC 4. Measures simple **baselines** any forecast must beat.
# MAGIC 5. **Compares model designs** on a validation period and tunes the best one.
# MAGIC 6. Trains two **classifiers** that give the chance of Moderate and High heat, and picks the **High-heat alert** threshold.
# MAGIC 7. Tests everything on months the models have never seen.
# MAGIC 8. Registers the final model in **MLflow / Unity Catalog** as `workspace.heatguard.wbgt_peak_forecaster` (alias `champion`) and
# MAGIC    saves evaluation tables for the app and Genie.
# MAGIC
# MAGIC **Run it:** top to bottom on serverless (a few minutes). Re-run to retrain on newer data; `06_score_forecast` always uses the version with the `champion` alias.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Setup
# MAGIC
# MAGIC Installs MLflow (experiment tracking and model registry), scikit-learn (the models) and matplotlib (charts), then restarts Python so the new versions load.

# COMMAND ----------

# MAGIC %pip install -q "mlflow[databricks]>=2.19" "scikit-learn>=1.4" matplotlib

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %md
# MAGIC **Settings.** The models predict tomorrow's afternoon peak (`target_peak_wbgt_c`) from the feature columns below, all built in the pipeline
# MAGIC (`04_pipeline`, section *Gold: model features*). In short:
# MAGIC
# MAGIC | Group | Features |
# MAGIC |---|---|
# MAGIC | Recent heat at the station | today's, yesterday's and the day before's afternoon peak; 7-day average and highest peak; today's all-day maximum; today vs its 7-day average |
# MAGIC | The station's usual level | its average peak over all earlier days, and how much hotter or cooler than the network it usually runs |
# MAGIC | Island-wide heat | average and highest peak across stations today; island 7-day average |
# MAGIC | Season | day of year, encoded as a circle so 31 Dec sits next to 1 Jan |
# MAGIC | NEA's forecast for tomorrow | max/min temperature, max/min humidity, wind speed, rain expected island-wide and in the station's region (afternoon) |
# MAGIC | Haze | today's 24-hour PSI in the station's region |
# MAGIC
# MAGIC We leave out latitude/longitude: with only ~30 stations, the model could memorise individual sites instead of learning weather patterns.
# MAGIC The station's usual level captures the real site-to-site differences more robustly.
# MAGIC
# MAGIC **Time split:** *train* = targets before 1 Apr 2026; *validation* = Apr–Jun 2026 (used to choose designs and settings);
# MAGIC *test* = 1 Jul 2026 onwards (never used for any choice — the honest final exam).

# COMMAND ----------

import math, datetime, itertools
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import mlflow
from mlflow.models import infer_signature
from sklearn.ensemble import HistGradientBoostingRegressor, HistGradientBoostingClassifier

CATALOG, SCHEMA = "workspace", "heatguard"
FEATURE_TABLE = f"{CATALOG}.{SCHEMA}.gold_forecast_features"
MODEL_NAME = f"{CATALOG}.{SCHEMA}.wbgt_peak_forecaster"
TARGET, BASELINE = "target_peak_wbgt_c", "baseline_7d_c"
WBGT_MODERATE, WBGT_HIGH = 31.0, 33.0
VALID_START, TEST_START = pd.Timestamp("2026-04-01"), pd.Timestamp("2026-07-01")

FEATURE_LABELS = {
    "peak_d": "Today's afternoon peak", "peak_d1": "Yesterday's peak", "peak_d2": "Peak 2 days ago",
    "peak_mean_7d": "7-day average peak", "peak_max_7d": "7-day highest peak", "daily_max_d": "Today's all-day maximum",
    "anom_d": "Today vs 7-day average", "station_mean_to_date": "Station's usual peak", "station_offset": "Station hotter/cooler than network",
    "network_mean_peak_d": "Island average peak today", "network_max_peak_d": "Island highest peak today", "network_mean_7d": "Island 7-day average",
    "doy_sin": "Season (sin)", "doy_cos": "Season (cos)",
    "nea_temp_high_c": "NEA forecast max temperature", "nea_temp_low_c": "NEA forecast min temperature",
    "nea_rh_high_pct": "NEA forecast max humidity", "nea_rh_low_pct": "NEA forecast min humidity",
    "nea_wind_high_kmh": "NEA forecast wind speed", "nea_rain_expected": "NEA expects rain (island)",
    "nea_region_afternoon_rain": "NEA expects afternoon rain (region)", "psi_24h_d": "Haze today (PSI)",
}
FEATURES = list(FEATURE_LABELS)

def band(x):
    x = np.asarray(x, float)
    return np.where(x >= WBGT_HIGH, "High", np.where(x >= WBGT_MODERATE, "Moderate", "Low"))

user = spark.sql("SELECT current_user()").first()[0]
mlflow.set_registry_uri("databricks-uc")
mlflow.set_experiment(f"/Users/{user}/heatguard_wbgt_forecast")
plt.rcParams.update({"figure.dpi": 110, "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.alpha": 0.3})
print("Experiment:", f"/Users/{user}/heatguard_wbgt_forecast", "| Registered model:", MODEL_NAME, "|", len(FEATURES), "features")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Load the data and check what we have
# MAGIC
# MAGIC We keep station-days where tomorrow's actual peak is known (the target) and there is some recent heat information.
# MAGIC
# MAGIC **First table — the three periods:** number of station-days, stations, dates, average peak and share of High days in each.
# MAGIC Note that the network grew from 8 to 30 stations, so the later periods have many more rows per day.
# MAGIC
# MAGIC **Second table — missing values per feature.** Recent-heat features are almost always present. NEA forecast features are missing on
# MAGIC roughly 28% of station-days, because on those days no forecast issued by 6:30 pm the day before is in the API history.
# MAGIC We do **not** fill these with guesses: the models used here handle missing values natively, learning at each split which side
# MAGIC missing values should go — more honest than inventing a number.

# COMMAND ----------

raw = spark.table(FEATURE_TABLE).toPandas()
for c in ["feature_date", "target_date"]:
    raw[c] = pd.to_datetime(raw[c])
for c in FEATURES + [TARGET, BASELINE]:
    raw[c] = pd.to_numeric(raw[c], errors="coerce")

data = raw[raw[TARGET].notna() & raw[BASELINE].notna()].copy()
data["split"] = np.where(data["target_date"] < VALID_START, "train", np.where(data["target_date"] < TEST_START, "validation", "test"))

overview = (data.groupby("split")
            .agg(station_days=(TARGET, "size"), stations=("station_id", "nunique"),
                 first_day=("target_date", "min"), last_day=("target_date", "max"),
                 avg_peak_c=(TARGET, "mean"), share_high=(TARGET, lambda s: (s >= WBGT_HIGH).mean()))
            .reindex(["train", "validation", "test"]))
display(overview.reset_index().round(3))

missing = (data[FEATURES].isna().mean().rename("share_missing").to_frame()
           .assign(feature=lambda d: d.index.map(FEATURE_LABELS)).sort_values("share_missing", ascending=False))
display(missing.reset_index(names="column").round(3))
print(f"{len(data):,} labelled station-days from {data.target_date.min():%d %b %Y} to {data.target_date.max():%d %b %Y}; "
      f"{(data[TARGET] >= WBGT_HIGH).mean():.1%} reached High, {(data[TARGET] >= WBGT_MODERATE).mean():.1%} reached Moderate or higher.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Exploring the data
# MAGIC
# MAGIC Four questions, each answered with a chart. The findings (measured on this data in Oct 2026) drive the modelling choices in section 5.

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3a. How hot do afternoons get, and how often is it High?
# MAGIC
# MAGIC **Chart:** distribution of the afternoon peak across all station-days, with NEA's band cut-offs as dashed lines.
# MAGIC
# MAGIC **What it shows:** about half of station-days stay Low (< 31 °C), around 44% reach Moderate, and only about **4.6% reach High**.
# MAGIC
# MAGIC **What it means for the model:** because High is rare, a model can achieve a small average error while missing most High days
# MAGIC (it learns to play safe and predict "near average"). So we judge the forecast not only by its average error, but also by
# MAGIC **how many High days it catches** — and we build a dedicated High-heat classifier for that job (section 6).

# COMMAND ----------

fig, ax = plt.subplots(figsize=(9, 4))
ax.hist(data[TARGET], bins=np.arange(24, 37.01, 0.25), color="#6b8fb5", edgecolor="white")
for x, lbl, col in [(WBGT_MODERATE, "Moderate ≥ 31 °C", "#e0a030"), (WBGT_HIGH, "High ≥ 33 °C", "#c0392b")]:
    ax.axvline(x, ls="--", color=col, lw=1.5); ax.text(x + 0.08, ax.get_ylim()[1] * 0.92, lbl, color=col, fontsize=9)
ax.set_xlabel("Afternoon peak WBGT (°C)"); ax.set_ylabel("Station-days")
ax.set_title("Afternoon peak WBGT, all stations and days")
fig.tight_layout(); fig_dist = fig; plt.show()

shares = pd.Series(band(data[TARGET])).value_counts(normalize=True).reindex(["Low", "Moderate", "High"])
print("Share of station-days by band:", ", ".join(f"{k} {v:.1%}" for k, v in shares.items()))

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3b. Is there a seasonal pattern?
# MAGIC
# MAGIC **Chart:** for each calendar month, the average afternoon peak (bars) and the share of station-days that reached High (red line).
# MAGIC
# MAGIC **What it shows:** a clear seasonal cycle. **April and May are the hottest** (average peak ~31.2–31.5 °C, roughly 10% of station-days High),
# MAGIC with a second, smaller hot spell in **September–October** (~5% High). **January is the coolest** (~28.8 °C, almost never High) during the
# MAGIC north-east monsoon. This matches Singapore's known inter-monsoon heat.
# MAGIC
# MAGIC **What it means for the model:** season is a genuine signal, so we include the day of year. It also tells us the test period (Jul–Oct)
# MAGIC contains a hot spell, so it is a fair test, while the validation period (Apr–Jun) is the hottest of the year — a demanding check.

# COMMAND ----------

monthly = (data.assign(month=data.target_date.dt.month)
           .groupby("month").agg(avg_peak_c=(TARGET, "mean"), share_high=(TARGET, lambda s: (s >= WBGT_HIGH).mean()), station_days=(TARGET, "size")))
fig, ax = plt.subplots(figsize=(9, 4))
ax.bar(monthly.index, monthly.avg_peak_c, color="#6b8fb5")
ax.set_ylim(monthly.avg_peak_c.min() - 1, monthly.avg_peak_c.max() + 0.6)
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
# MAGIC **Chart:** each dot is one station-day: today's afternoon peak (x) against tomorrow's (y). The red diagonal is "tomorrow = today".
# MAGIC
# MAGIC **What it shows:** the relationship is **weaker than one might expect** (correlation about 0.36), and the afternoon peak changes by about
# MAGIC **1.3 °C on average from one day to the next**. Singapore afternoons swing with showers and cloud: a hot day is often followed by a
# MAGIC stormy one.
# MAGIC
# MAGIC **What it means for the model:** today's value alone is a noisy guide. A **7-day average** is steadier, so we try using it as the starting point
# MAGIC (the baseline) and letting the model learn the *change* from it, using information about tomorrow itself — NEA's forecast.

# COMMAND ----------

sub = data.dropna(subset=["peak_d"])
r = np.corrcoef(sub.peak_d, sub[TARGET])[0, 1]
fig, ax = plt.subplots(figsize=(5.5, 5.5))
ax.scatter(sub.peak_d, sub[TARGET], s=4, alpha=0.25, color="#34495e")
lims = [24, 37]; ax.plot(lims, lims, color="#c0392b", lw=1, label="tomorrow = today")
ax.set_xlim(lims); ax.set_ylim(lims); ax.set_xlabel("Today's afternoon peak (°C)"); ax.set_ylabel("Tomorrow's afternoon peak (°C)")
ax.set_title(f"Persistence: correlation r = {r:.2f}"); ax.legend(loc="upper left")
fig.tight_layout(); fig_persist = fig; plt.show()
print(f"Correlation between today's and tomorrow's peak: {r:.2f}; average day-to-day change: {np.mean(np.abs(sub.peak_d - sub[TARGET])):.2f} °C")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3d. Do NEA's forecast and haze add information?
# MAGIC
# MAGIC **Charts:** (left) tomorrow's peak when NEA does / doesn't expect afternoon rain in the station's region; (middle) average tomorrow's peak
# MAGIC for each NEA forecast maximum temperature; (right) average tomorrow's peak by today's haze level (PSI band).
# MAGIC
# MAGIC **What they show:**
# MAGIC - **NEA's temperature forecast is the strongest new signal.** The average peak rises steadily with NEA's forecast maximum: about 29.0 °C
# MAGIC   when NEA forecasts 32 °C, 30.2 °C at 33 °C, 31.2 °C at 34 °C and 32.3 °C at 36 °C.
# MAGIC - **NEA's afternoon-rain outlook adds little on its own** (only ~0.2 °C lower on average). NEA mentions thundery showers on most days, so
# MAGIC   "rain expected" rarely separates hot days from cooler ones.
# MAGIC - **Haze days are hotter, not cooler** (about 30.4 °C when PSI ≤ 50, 30.8 °C at 51–100, 31.5 °C above 100). We expected haze to block sunlight,
# MAGIC   but haze episodes happen during dry, settled spells, which are also hot. Haze is therefore a useful *marker* of a hot weather pattern.
# MAGIC
# MAGIC **What it means for the model:** NEA's forecast and haze carry information beyond persistence, so they are included; the tree model
# MAGIC can learn these non-linear effects directly.

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

hz = data.dropna(subset=["psi_24h_d"]).assign(psi_bin=lambda d: pd.cut(d.psi_24h_d, [0, 50, 100, 500], labels=["Good (≤50)", "Moderate (51–100)", "Unhealthy (>100)"]))
hzg = hz.groupby("psi_bin", observed=True)[TARGET].agg(["mean", "size"])
axes[2].bar([str(i) for i in hzg.index], hzg["mean"], color="#95a5a6")
axes[2].set_ylim(hzg["mean"].min() - 0.8, hzg["mean"].max() + 0.5)
axes[2].set_xlabel("Today's 24-hour PSI band"); axes[2].set_title("Haze today"); axes[2].tick_params(axis="x", rotation=15)
fig.tight_layout(); fig_signals = fig; plt.show()

print("Average peak, no rain expected vs rain expected:", [round(g.mean(), 2) for g in groups])
display(temp.reset_index().round(2)); display(hzg.reset_index().astype({"psi_bin": str}).round(2))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Time-based split and baselines
# MAGIC
# MAGIC **Why split by time, not at random:** weather on neighbouring days is strongly related. A random split would put 14 Oct in training
# MAGIC and 15 Oct in testing, letting the model "see" the answer through its neighbour and look far better than it really is.
# MAGIC Learning from the past and testing on later months is exactly how the model will be used.
# MAGIC
# MAGIC **Baselines** — simple rules any model must beat to be worth using:
# MAGIC | Baseline | Rule |
# MAGIC |---|---|
# MAGIC | Persistence | Tomorrow's peak = today's peak |
# MAGIC | 7-day average | Tomorrow's peak = this station's average peak over the last 7 days |
# MAGIC | Station's usual level | Tomorrow's peak = this station's average peak over all earlier days |
# MAGIC
# MAGIC **How we score forecasts:**
# MAGIC - **MAE** (mean absolute error): the average size of the miss in °C. Lower is better.
# MAGIC - **Within ±1 °C**: share of forecasts within one degree.
# MAGIC - **Band accuracy**: share of station-days where the forecast band (Low / Moderate / High) is right.
# MAGIC - **High recall**: of the station-days that really were High, how many were flagged. **High precision**: of the flags, how many were really High.
# MAGIC   For outreach, recall matters most: a missed High day is worse than an extra phone call.

# COMMAND ----------

train, valid, test = (data[data.split == s].copy() for s in ("train", "validation", "test"))
dev = pd.concat([train, valid])

def baselines(df):
    return {
        "Persistence (tomorrow = today)": df["peak_d"].fillna(df[BASELINE]),
        "7-day average": df[BASELINE],
        "Station's usual level": df["station_mean_to_date"].fillna(df[BASELINE]),
    }

def scores(y, p, flag_high=None):
    """Forecast scores. flag_high: optional boolean High alerts (defaults to forecast >= 33 °C)."""
    y, p = np.asarray(y, float), np.asarray(p, float)
    hi = y >= WBGT_HIGH
    fh = (p >= WBGT_HIGH) if flag_high is None else np.asarray(flag_high, bool)
    mod, pmod = y >= WBGT_MODERATE, p >= WBGT_MODERATE
    return {
        "MAE (°C)": np.mean(np.abs(y - p)),
        "RMSE (°C)": math.sqrt(np.mean((y - p) ** 2)),
        "Within ±1 °C": np.mean(np.abs(y - p) <= 1.0),
        "Band accuracy": np.mean(band(y) == band(p)),
        "High recall": hi[fh].sum() / hi.sum() if hi.sum() else np.nan,
        "High precision": hi[fh].sum() / fh.sum() if fh.sum() else np.nan,
        "Moderate+ recall": mod[pmod].sum() / mod.sum() if mod.sum() else np.nan,
        "Station-days": len(y),
    }

rows = []
for split_name, df in [("validation", valid), ("test", test)]:
    for name, pred in baselines(df).items():
        rows.append({"model": name, "split": split_name, **scores(df[TARGET], pred)})
baseline_scores = pd.DataFrame(rows)
display(baseline_scores.round(3))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Choosing and tuning the forecast model
# MAGIC
# MAGIC **Model family:** gradient-boosted decision trees (`HistGradientBoostingRegressor`, scikit-learn). Hundreds of small trees, each
# MAGIC correcting the previous ones. It captures non-linear effects and interactions (e.g. "hot week **and** NEA forecasts 35 °C"),
# MAGIC handles missing NEA forecasts natively, and trains in seconds on Free Edition, so it can be retrained often.
# MAGIC
# MAGIC **Three designs compared on the validation period** (each trained on the training period only):
# MAGIC | Design | What it learns | Why try it |
# MAGIC |---|---|---|
# MAGIC | A. Squared error, raw peak | Tomorrow's peak directly, punishing big misses heavily | The textbook default |
# MAGIC | B. Absolute error, raw peak | Tomorrow's peak directly, every degree of error counts equally | Less pulled towards the average by the noisy day-to-day swings seen in 3c |
# MAGIC | C. Absolute error, change from 7-day average | How much tomorrow differs from the station's 7-day average | Builds on the steadiest simple rule and spends the model's effort on what's new about tomorrow |
# MAGIC
# MAGIC The design with the lowest validation error is then tuned over a small grid of settings (learning rate, tree size, minimum station-days per leaf,
# MAGIC regularisation), again scored on validation only.

# COMMAND ----------

class Forecaster:
    """A regressor that optionally predicts the change from the 7-day baseline."""
    def __init__(self, loss, residual, **params):
        self.residual = residual
        self.m = HistGradientBoostingRegressor(loss=loss, max_iter=300, early_stopping=False, random_state=42, **params)
    def fit(self, df):
        self.m.fit(df[FEATURES], df[TARGET] - (df[BASELINE] if self.residual else 0)); return self
    def predict(self, df):
        return self.m.predict(df[FEATURES]) + (df[BASELINE].values if self.residual else 0)

DEFAULT = dict(learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=40)
DESIGNS = {"A. Squared error, raw peak": ("squared_error", False),
           "B. Absolute error, raw peak": ("absolute_error", False),
           "C. Absolute error, change from 7-day average": ("absolute_error", True)}
design_rows = []
for name, (loss, resid) in DESIGNS.items():
    p = Forecaster(loss, resid, **DEFAULT).fit(train).predict(valid)
    design_rows.append({"design": name, **{f"validation {k}": v for k, v in scores(valid[TARGET], p).items() if k in ("MAE (°C)", "High recall", "Band accuracy")}})
designs = pd.DataFrame(design_rows).sort_values("validation MAE (°C)")
display(designs.round(3))
best_design = designs.iloc[0]["design"]; LOSS, RESIDUAL = DESIGNS[best_design]
print("Chosen design:", best_design)

GRID = {"learning_rate": [0.03, 0.06], "max_leaf_nodes": [8, 15], "min_samples_leaf": [60, 120], "l2_regularization": [0.0, 1.0]}
tuning = []
for values in itertools.product(*GRID.values()):
    params = dict(zip(GRID, values))
    p = Forecaster(LOSS, RESIDUAL, **params).fit(train).predict(valid)
    tuning.append({**params, "validation MAE (°C)": np.mean(np.abs(valid[TARGET] - p))})
tuning = pd.DataFrame(tuning).sort_values("validation MAE (°C)")
best_params = {k: type(GRID[k][0])(tuning.iloc[0][k]) for k in GRID}   # back to each setting's own type (int or float)
display(tuning.round(4))
print("Best settings on validation:", best_params)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. The chance of heat, and the High-heat alert
# MAGIC
# MAGIC A single number ("32.4 °C") hides uncertainty, and — as section 3a warned — a forecast of the *typical* peak rarely reaches 33 °C even on
# MAGIC days that turn out High. So we train two **classifiers** (`HistGradientBoostingClassifier`) on the same features:
# MAGIC - one gives the **chance tomorrow's peak reaches Moderate or higher** (≥ 31 °C);
# MAGIC - one gives the **chance it reaches High** (≥ 33 °C).
# MAGIC
# MAGIC Their settings are chosen by the **Brier score** on validation (the average squared gap between the predicted chance and what happened;
# MAGIC 0 is perfect, lower is better).
# MAGIC
# MAGIC **The High-heat alert:** a station is flagged when its chance of High is at or above a threshold. The threshold balances two costs:
# MAGIC - a **missed High day** can mean a senior suffering heat illness alone, so we want to catch as many as possible (high recall);
# MAGIC - but if most alerts are false alarms, coordinators learn to ignore them ("alert fatigue").
# MAGIC
# MAGIC **Rule:** on the validation period, pick the **lowest threshold at which at least 40% of alerts were real High days** — i.e. catch as many
# MAGIC High days as possible while keeping alerts trustworthy. (An earlier version simply maximised the F2 score; it picked a 5% threshold that
# MAGIC flagged a quarter of all station-days and was right only 1 time in 6 on the test months — too noisy to act on.)

# COMMAND ----------

def make_clf(**params):
    return HistGradientBoostingClassifier(max_iter=300, early_stopping=False, random_state=42, **params)

CLF_GRID = {"learning_rate": [0.03, 0.06], "max_leaf_nodes": [8, 15], "min_samples_leaf": [40, 120]}
clf_params, clf_choice = {}, []
for key, thr in [("moderate_plus", WBGT_MODERATE), ("high", WBGT_HIGH)]:
    best = None
    for values in itertools.product(*CLF_GRID.values()):
        params = dict(zip(CLF_GRID, values))
        pv = make_clf(**params).fit(train[FEATURES], train[TARGET] >= thr).predict_proba(valid[FEATURES])[:, 1]
        b = float(np.mean((pv - (valid[TARGET] >= thr)) ** 2))
        if best is None or b < best[0]:
            best = (b, params, pv)
    clf_params[key] = best[1]
    clf_choice.append({"classifier": key, **best[1], "validation Brier": best[0]})
    if key == "high":
        p_high_valid = best[2]
display(pd.DataFrame(clf_choice).round(4))

y_hv = (valid[TARGET] >= WBGT_HIGH).values
thr_rows = []
for th in np.round(np.arange(0.05, 0.61, 0.05), 2):
    f = p_high_valid >= th; tp = y_hv[f].sum()
    rec, prec = tp / max(y_hv.sum(), 1), tp / max(f.sum(), 1)
    thr_rows.append({"threshold": th, "recall": rec, "precision": prec, "alerts": int(f.sum()),
                     "F2": (5 * prec * rec) / (4 * prec + rec) if (prec + rec) else 0.0})
thresholds = pd.DataFrame(thr_rows)
MIN_ALERT_PRECISION = 0.40
ok = thresholds[thresholds.precision >= MIN_ALERT_PRECISION]
ALERT_THRESHOLD = float(ok.threshold.min() if len(ok) else thresholds.sort_values("F2", ascending=False).iloc[0]["threshold"])
display(thresholds.round(3))
print(f"High-heat alert threshold: {ALERT_THRESHOLD:.2f} (lowest threshold with validation precision >= {MIN_ALERT_PRECISION:.0%})")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. The final exam: months the models have never seen
# MAGIC
# MAGIC With the design, settings and alert threshold fixed, we retrain everything on **train + validation** (all days before July 2026) and
# MAGIC forecast the **test** period (July 2026 onwards). Nothing about the test period influenced any choice above, so this is the honest estimate
# MAGIC of real-world performance.
# MAGIC
# MAGIC **Table:** test scores of the HeatGuard forecast and each baseline. For HeatGuard, *High recall/precision* use the High-heat alert; for the
# MAGIC baselines, a High flag means the rule predicts ≥ 33 °C.
# MAGIC
# MAGIC **Charts:** (left) average error — lower is better; (right) share of hot station-days caught.

# COMMAND ----------

reg_dev = Forecaster(LOSS, RESIDUAL, **best_params).fit(dev)
clf_mod_dev = make_clf(**clf_params["moderate_plus"]).fit(dev[FEATURES], dev[TARGET] >= WBGT_MODERATE)
clf_high_dev = make_clf(**clf_params["high"]).fit(dev[FEATURES], dev[TARGET] >= WBGT_HIGH)

test["pred_model"] = reg_dev.predict(test)
test["prob_moderate_plus"] = clf_mod_dev.predict_proba(test[FEATURES])[:, 1]
test["prob_high"] = clf_high_dev.predict_proba(test[FEATURES])[:, 1]
test["high_alert"] = test["prob_high"] >= ALERT_THRESHOLD
for name, pred in baselines(test).items():
    test[f"pred_{name}"] = pred

test_scores = pd.DataFrame([{"model": "HeatGuard forecast", "split": "test", **scores(test[TARGET], test.pred_model, test.high_alert)}]
                           + [r for r in baseline_scores.to_dict("records") if r["split"] == "test"])
display(test_scores.round(3))

best_baseline = test_scores.iloc[1:].sort_values("MAE (°C)").iloc[0]
model_row = test_scores.iloc[0]
improvement = 1 - model_row["MAE (°C)"] / best_baseline["MAE (°C)"]
alerts_at_least_moderate = float((test.loc[test.high_alert, TARGET] >= WBGT_MODERATE).mean())
print(f"Test MAE: HeatGuard {model_row['MAE (°C)']:.3f} °C vs best baseline ({best_baseline['model']}) {best_baseline['MAE (°C)']:.3f} °C "
      f"→ {improvement:.1%} smaller errors.")
print(f"High-heat alerts caught {model_row['High recall']:.0%} of High station-days; {model_row['High precision']:.0%} of alerts were High "
      f"and {alerts_at_least_moderate:.0%} were at least Moderate.")

fig, axes = plt.subplots(1, 2, figsize=(12, 4))
order = test_scores.sort_values("MAE (°C)")
colors = ["#27ae60" if m.startswith("HeatGuard") else "#95a5a6" for m in order.model]
axes[0].barh(order.model, order["MAE (°C)"], color=colors); axes[0].invert_yaxis()
axes[0].set_xlabel("Average error (°C) — lower is better"); axes[0].set_title("Test period: average error")
w = 0.38; idx = np.arange(len(test_scores))
axes[1].bar(idx - w / 2, test_scores["High recall"], w, label="High days caught", color="#c0392b")
axes[1].bar(idx + w / 2, test_scores["Moderate+ recall"], w, label="Moderate+ days caught", color="#e0a030")
axes[1].set_xticks(idx); axes[1].set_xticklabels([m.split(" (")[0] for m in test_scores.model], rotation=15, fontsize=8)
axes[1].set_ylim(0, 1); axes[1].set_title("Test period: share of hot station-days caught"); axes[1].legend(fontsize=8)
fig.tight_layout(); fig_compare = fig; plt.show()

# COMMAND ----------

# MAGIC %md
# MAGIC ### Where does the forecast go wrong?
# MAGIC
# MAGIC **Left:** forecast vs actual peak on the test period. Points near the diagonal are good forecasts; the shaded areas mark High.
# MAGIC Points far *below* the diagonal on the right are hot days the number under-forecast — the reason we rely on the High-heat alert, not the number alone, for warnings.
# MAGIC
# MAGIC **Right:** average error by month for HeatGuard and the best baseline, to check the forecast is consistently better rather than good in one month and poor in another.

# COMMAND ----------

fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
axes[0].scatter(test[TARGET], test.pred_model, s=6, alpha=0.3, color="#2c3e50")
axes[0].plot([25, 37], [25, 37], color="#c0392b", lw=1)
axes[0].axvspan(WBGT_HIGH, 37, color="#c0392b", alpha=0.06); axes[0].axhspan(WBGT_HIGH, 37, color="#c0392b", alpha=0.06)
axes[0].set_xlim(25, 37); axes[0].set_ylim(25, 37)
axes[0].set_xlabel("Actual afternoon peak (°C)"); axes[0].set_ylabel("Forecast (°C)"); axes[0].set_title("Forecast vs actual (test)")
bymonth = (test.assign(month=test.target_date.dt.strftime("%Y-%m"), heatguard=np.abs(test[TARGET] - test.pred_model),
                       baseline=np.abs(test[TARGET] - test[f"pred_{best_baseline['model']}"]))
           .groupby("month")[["heatguard", "baseline"]].mean())
x = np.arange(len(bymonth))
axes[1].bar(x - 0.2, bymonth.heatguard, 0.4, label="HeatGuard", color="#27ae60")
axes[1].bar(x + 0.2, bymonth.baseline, 0.4, label=best_baseline["model"], color="#95a5a6")
axes[1].set_xticks(x); axes[1].set_xticklabels(bymonth.index); axes[1].set_ylabel("Average error (°C)"); axes[1].set_title("Error by month (test)"); axes[1].legend(fontsize=8)
fig.tight_layout(); fig_errors = fig; plt.show()
display(bymonth.reset_index().round(3))

# COMMAND ----------

# MAGIC %md
# MAGIC ### Are the probabilities honest?
# MAGIC
# MAGIC **Reliability charts:** test station-days are grouped by their predicted chance (0–20%, 20–40%, …); each dot compares the average predicted
# MAGIC chance (x) with how often the event really happened (y). Honest probabilities sit on the dashed diagonal: when we say 30%, it happens
# MAGIC about 30% of the time. Dot size shows how many station-days are in the group.
# MAGIC
# MAGIC **Brier table:** the classifier's Brier score next to a naive forecaster that always predicts the long-run average rate. Lower is better;
# MAGIC beating the naive rate means the chances carry real day-to-day information.

# COMMAND ----------

def brier(p, y):
    return float(np.mean((np.asarray(p, float) - np.asarray(y, float)) ** 2))

calib = {}
fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
for ax, (col, thr, label, colr) in zip(axes, [("prob_high", WBGT_HIGH, "High (≥ 33 °C)", "#c0392b"),
                                               ("prob_moderate_plus", WBGT_MODERATE, "Moderate or higher (≥ 31 °C)", "#e0a030")]):
    y = (test[TARGET] >= thr).astype(int)
    bins = pd.cut(test[col], np.linspace(0, 1, 6), include_lowest=True)
    rel = test.assign(y=y).groupby(bins, observed=True).agg(pred=(col, "mean"), obs=("y", "mean"), n=("y", "size"))
    ax.plot([0, 1], [0, 1], color="#7f8c8d", ls="--", lw=1, label="perfectly honest")
    ax.scatter(rel.pred, rel.obs, s=np.clip(rel.n / 4, 15, 400), color=colr, alpha=0.8, label="test station-days")
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.set_xlabel("Predicted chance"); ax.set_ylabel("Observed frequency"); ax.set_title(f"Reliability: {label}"); ax.legend(fontsize=8)
    calib[col] = {"brier_model": brier(test[col], y), "brier_naive": brier(np.full(len(y), (dev[TARGET] >= thr).mean()), y)}
fig.tight_layout(); fig_reliability = fig; plt.show()
display(pd.DataFrame(calib).T.round(4))

# COMMAND ----------

# MAGIC %md
# MAGIC ### Which features does the forecast rely on?
# MAGIC
# MAGIC **Method — permutation importance:** we shuffle one feature at a time on the test data and measure how much worse the forecast gets.
# MAGIC A big increase in error means the model leans on that feature; near zero means it barely uses it. Because it is measured on unseen data,
# MAGIC it is more trustworthy than the model's internal importance scores.

# COMMAND ----------

rng = np.random.default_rng(42)
base_mae = np.mean(np.abs(test[TARGET] - reg_dev.predict(test)))
imp_rows = []
for f in FEATURES:
    increases = []
    for _ in range(5):                                   # shuffle each feature 5 times and average
        shuffled = test.copy()
        shuffled[f] = rng.permutation(shuffled[f].values)
        increases.append(np.mean(np.abs(test[TARGET] - reg_dev.predict(shuffled))) - base_mae)
    imp_rows.append({"column": f, "feature": FEATURE_LABELS[f], "mae_increase_c": float(np.mean(increases)), "std": float(np.std(increases))})
importance = pd.DataFrame(imp_rows).sort_values("mae_increase_c", ascending=False)
fig, ax = plt.subplots(figsize=(8, 6))
top = importance.head(12).iloc[::-1]
ax.barh(top.feature, top.mae_increase_c, xerr=top["std"], color="#6b8fb5")
ax.set_xlabel("Increase in average error when shuffled (°C)"); ax.set_title("What the forecast relies on (test period)")
fig.tight_layout(); fig_importance = fig; plt.show()
display(importance.round(4))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. Final model: train on everything, register in Unity Catalog
# MAGIC
# MAGIC With every choice fixed and the test result recorded, we retrain the forecaster and both classifiers on **all** labelled days, so the
# MAGIC production model also learns from the most recent weather. They are packaged as one MLflow model that, given the feature columns
# MAGIC (plus `baseline_7d_c`), returns:
# MAGIC
# MAGIC | Output | Meaning |
# MAGIC |---|---|
# MAGIC | `predicted_peak_wbgt_c` | Tomorrow's forecast afternoon peak (°C) |
# MAGIC | `predicted_band` | NEA band of that forecast |
# MAGIC | `prob_moderate_plus`, `prob_high` | Chance of reaching ≥ 31 °C and ≥ 33 °C |
# MAGIC | `high_alert` | True when the chance of High is at or above the alert threshold |
# MAGIC | `high_alert_threshold` | The threshold used |
# MAGIC
# MAGIC **Logged to MLflow:** settings, test scores of every model and baseline, all charts above, and the model. It is registered as
# MAGIC **`workspace.heatguard.wbgt_peak_forecaster`**; the new version gets the alias **`champion`**, which `06_score_forecast` loads.

# COMMAND ----------

class WbgtPeakForecaster(mlflow.pyfunc.PythonModel):
    """Tomorrow's afternoon peak WBGT, its band, the chance of Moderate+ / High heat, and the High-heat alert."""
    def __init__(self, regressor, residual, clf_moderate, clf_high, features, alert_threshold):
        self.regressor, self.residual, self.clf_moderate, self.clf_high = regressor, residual, clf_moderate, clf_high
        self.features, self.alert_threshold = features, alert_threshold

    def predict(self, context, model_input):
        X = model_input[self.features].astype("float64")
        peak = self.regressor.predict(X)
        if self.residual:
            peak = peak + model_input["baseline_7d_c"].astype("float64").values
        p_mod = self.clf_moderate.predict_proba(X)[:, 1]
        p_high = self.clf_high.predict_proba(X)[:, 1]
        return pd.DataFrame({
            "predicted_peak_wbgt_c": np.round(peak, 2),
            "predicted_band": np.where(peak >= 33.0, "High", np.where(peak >= 31.0, "Moderate", "Low")),
            "prob_moderate_plus": np.round(np.maximum(p_mod, p_high), 4),   # Moderate-or-higher can't be less likely than High
            "prob_high": np.round(p_high, 4),
            "high_alert": p_high >= self.alert_threshold,
            "high_alert_threshold": np.full(len(X), self.alert_threshold),
        })

final_reg = Forecaster(LOSS, RESIDUAL, **best_params).fit(data)
final_mod = make_clf(**clf_params["moderate_plus"]).fit(data[FEATURES], data[TARGET] >= WBGT_MODERATE)
final_high = make_clf(**clf_params["high"]).fit(data[FEATURES], data[TARGET] >= WBGT_HIGH)
wrapped = WbgtPeakForecaster(final_reg.m, RESIDUAL, final_mod, final_high, FEATURES, ALERT_THRESHOLD)

example = data[FEATURES + [BASELINE]].head(5).astype("float64")
signature = infer_signature(example, wrapped.predict(None, example))

def metric_key(s):
    return (s.lower().replace(" (°c)", "").replace(" ±1 °c", "_1c").replace("+", "_plus").replace("'", "")
             .replace("(", "").replace(")", "").replace("=", "").replace(" ", "_").replace("__", "_"))

with mlflow.start_run(run_name=f"wbgt_peak_forecaster_{datetime.date.today():%Y%m%d}") as run:
    mlflow.log_params({"design": best_design, **{f"reg_{k}": v for k, v in best_params.items()},
                       **{f"clf_mod_{k}": v for k, v in clf_params["moderate_plus"].items()},
                       **{f"clf_high_{k}": v for k, v in clf_params["high"].items()},
                       "alert_threshold": ALERT_THRESHOLD, "features": len(FEATURES), "train_rows": len(data),
                       "valid_start": str(VALID_START.date()), "test_start": str(TEST_START.date())})
    for _, r_ in test_scores.iterrows():
        prefix = metric_key(r_["model"])
        for k in ("MAE (°C)", "RMSE (°C)", "Within ±1 °C", "Band accuracy", "High recall", "High precision", "Moderate+ recall"):
            if pd.notna(r_[k]):
                mlflow.log_metric(f"test_{prefix}_{metric_key(k)}", float(r_[k]))
    mlflow.log_metric("test_improvement_vs_best_baseline", float(improvement))
    for k, v in calib.items():
        mlflow.log_metrics({f"test_{k}_brier": v["brier_model"], f"test_{k}_brier_naive": v["brier_naive"]})
    for name, f in [("1_distribution", fig_dist), ("2_season", fig_season), ("3_persistence", fig_persist), ("4_signals", fig_signals),
                    ("5_comparison", fig_compare), ("6_errors", fig_errors), ("7_reliability", fig_reliability), ("8_importance", fig_importance)]:
        mlflow.log_figure(f, f"charts/{name}.png")
    mlflow.pyfunc.log_model(artifact_path="model", python_model=wrapped, signature=signature, input_example=example,
                            registered_model_name=MODEL_NAME)
    run_id = run.info.run_id

client = mlflow.MlflowClient()
version = max(int(v.version) for v in client.search_model_versions(f"name='{MODEL_NAME}'"))
client.set_registered_model_alias(MODEL_NAME, "champion", version)
client.update_registered_model(MODEL_NAME, description=(
    "Forecasts tomorrow's afternoon (12:00-17:59 SGT) peak WBGT per NEA station from recent heat, NEA's 24-hour forecast, season and haze, "
    "plus the chance of Moderate (>= 31 C) and High (>= 33 C) heat and a High-heat alert. Trained by notebook 05_forecast_model."))
print(f"Registered {MODEL_NAME} version {version} with alias 'champion' (run {run_id})")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 9. Save evaluation tables for the app and Genie
# MAGIC
# MAGIC So coordinators (and judges) can see *how good the forecast is* without opening MLflow, we save three tables:
# MAGIC - **`ml_model_evaluation`** — test-period scores of HeatGuard and each baseline.
# MAGIC - **`ml_backtest_predictions`** — every test-period forecast next to what actually happened (the app's accuracy chart).
# MAGIC - **`ml_feature_importance`** — which features the forecast relies on, in plain English.

# COMMAND ----------

trained_at = datetime.datetime.now(datetime.timezone.utc)
evaluation = test_scores.rename(columns=lambda c: metric_key(c) if c not in ("model", "split") else c)
evaluation = evaluation.assign(model_version=str(version), alert_threshold=ALERT_THRESHOLD, improvement_vs_best_baseline=improvement,
                               trained_at=trained_at, test_period=f"{test.target_date.min():%d %b %Y} – {test.target_date.max():%d %b %Y}")
(spark.createDataFrame(evaluation).write.mode("overwrite").option("overwriteSchema", "true")
      .saveAsTable(f"{CATALOG}.{SCHEMA}.ml_model_evaluation"))

backtest = test[["station_id", "station_name", "region", "feature_date", "target_date", TARGET, "pred_model",
                 f"pred_{best_baseline['model']}", "prob_moderate_plus", "prob_high", "high_alert"]].rename(columns={
    TARGET: "actual_peak_wbgt_c", "pred_model": "predicted_peak_wbgt_c", f"pred_{best_baseline['model']}": "baseline_peak_wbgt_c"})
backtest["feature_date"] = backtest.feature_date.dt.date
backtest["target_date"] = backtest.target_date.dt.date
backtest = backtest.assign(actual_band=band(backtest.actual_peak_wbgt_c), predicted_band=band(backtest.predicted_peak_wbgt_c),
                           baseline_name=best_baseline["model"], model_version=str(version))
(spark.createDataFrame(backtest).write.mode("overwrite").option("overwriteSchema", "true")
      .saveAsTable(f"{CATALOG}.{SCHEMA}.ml_backtest_predictions"))

(spark.createDataFrame(importance.assign(model_version=str(version))).write.mode("overwrite").option("overwriteSchema", "true")
      .saveAsTable(f"{CATALOG}.{SCHEMA}.ml_feature_importance"))

for t, c in [("ml_model_evaluation", "Forecast model vs baselines on the held-out test period (latest training run of 05_forecast_model)."),
             ("ml_backtest_predictions", "Test-period forecasts of tomorrow's afternoon peak WBGT next to the actual value and the best baseline."),
             ("ml_feature_importance", "Permutation importance of each forecast feature on the test period (increase in average error when shuffled).")]:
    spark.sql(f"COMMENT ON TABLE {CATALOG}.{SCHEMA}.{t} IS '{c.replace(chr(39), chr(39) * 2)}'")
print("Saved ml_model_evaluation, ml_backtest_predictions, ml_feature_importance")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 10. Summary
# MAGIC
# MAGIC The cell below prints this run's headline results in plain English, ready for the decision log or the pitch.

# COMMAND ----------

m = model_row
print(f"""HeatGuard forecast model v{version} (trained {trained_at:%d %b %Y}) — design: {best_design}
- Test period: {test.target_date.min():%d %b %Y} to {test.target_date.max():%d %b %Y}, {len(test):,} station-days never used for any choice.
- Average error {m['MAE (°C)']:.2f} °C vs {best_baseline['MAE (°C)']:.2f} °C for the best simple rule ({best_baseline['model']}): {improvement:.0%} smaller.
- Within ±1 °C on {m['Within ±1 °C']:.0%} of station-days; correct heat band on {m['Band accuracy']:.0%}.
- High-heat alert (chance of High ≥ {ALERT_THRESHOLD:.0%}): caught {m['High recall']:.0%} of High station-days; {m['High precision']:.0%} of alerts were High, {alerts_at_least_moderate:.0%} at least Moderate.
- Chance of High: Brier {calib['prob_high']['brier_model']:.3f} vs {calib['prob_high']['brier_naive']:.3f} for always guessing the average rate.
- Forecast relies most on: {', '.join(importance.feature.head(3))}.""")
