# Databricks notebook source
# MAGIC %md
# MAGIC # 06 · Score tomorrow's forecast (runs daily)
# MAGIC
# MAGIC **What this notebook does:** every evening, after the pipeline has loaded today's data, it asks the registered forecast model
# MAGIC (`workspace.heatguard.wbgt_peak_forecaster`, alias `champion`) for **tomorrow's afternoon peak WBGT at every active station**, together with the
# MAGIC chance of Moderate and High heat, and saves the result to **`ml_wbgt_forecast`**.
# MAGIC
# MAGIC The next pipeline run blends these station forecasts into each subzone, and the check-in list switches from "observed" to "forecast" heat.
# MAGIC
# MAGIC **Safety checks built in:**
# MAGIC - If today's data is missing or old (e.g. ingestion failed), the notebook still forecasts from the newest day available but **warns loudly**,
# MAGIC   and the forecast is stamped with the day it was made from, so the app can show that it is out of date.
# MAGIC - Re-running on the same day replaces that day's forecast rather than adding duplicates.
# MAGIC
# MAGIC It also refreshes **`ml_forecast_track_record`**, a view comparing every past forecast with what actually happened — the app's
# MAGIC "how accurate has it been?" panel.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Setup
# MAGIC Installs the same libraries the model was trained with, so it loads exactly as it was saved.

# COMMAND ----------

# MAGIC %pip install -q "mlflow[databricks]>=2.19" "scikit-learn>=1.4"

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

import datetime
import pandas as pd
import mlflow

CATALOG, SCHEMA = "workspace", "heatguard"
MODEL_NAME = f"{CATALOG}.{SCHEMA}.wbgt_peak_forecaster"
FEATURE_TABLE = f"{CATALOG}.{SCHEMA}.gold_forecast_features"
FORECAST_TABLE = f"{CATALOG}.{SCHEMA}.ml_wbgt_forecast"
mlflow.set_registry_uri("databricks-uc")

spark.sql(f"""CREATE TABLE IF NOT EXISTS {FORECAST_TABLE} (
  station_id STRING COMMENT 'NEA WBGT station id', station_name STRING, feature_date DATE COMMENT 'Day the forecast was made (SGT)',
  target_date DATE COMMENT 'Day being forecast (SGT)', predicted_peak_wbgt_c DOUBLE COMMENT 'Forecast afternoon (12:00-17:59) peak WBGT, deg C',
  predicted_band STRING COMMENT 'NEA band of the forecast peak', prob_moderate_plus DOUBLE COMMENT 'Chance the peak reaches 31 deg C or more',
  prob_high DOUBLE COMMENT 'Chance the peak reaches 33 deg C or more', high_alert BOOLEAN COMMENT 'Chance of High at or above the alert threshold',
  high_alert_threshold DOUBLE COMMENT 'Alert threshold chosen in 05_forecast_model', model_name STRING, model_version STRING, scored_at TIMESTAMP)
COMMENT 'Tomorrow''s afternoon peak WBGT forecast per station, written daily by 06_score_forecast (one row per station per target date).'""")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Load the champion model
# MAGIC
# MAGIC The `champion` alias always points to the version `05_forecast_model` approved last, so retraining never requires changing this notebook.

# COMMAND ----------

client = mlflow.MlflowClient()
champion = client.get_model_version_by_alias(MODEL_NAME, "champion")
model = mlflow.pyfunc.load_model(f"models:/{MODEL_NAME}@champion")
features = model.metadata.get_input_schema().input_names()
print(f"Loaded {MODEL_NAME} version {champion.version} ({len(features)} features)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Build today's inputs and check they are fresh
# MAGIC
# MAGIC We take the newest day in `gold_forecast_features` (normally today) for every station that has recent heat data.
# MAGIC "Today" is Singapore time. If the newest day is older than today, ingestion or the pipeline has not run — we still forecast,
# MAGIC but print a warning, and the app will show the forecast's real date.

# COMMAND ----------

today_sgt = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=8)).date()
latest_day = spark.sql(f"SELECT max(feature_date) FROM {FEATURE_TABLE} WHERE peak_d IS NOT NULL").first()[0]
inputs = (spark.table(FEATURE_TABLE)
          .where(f"feature_date = DATE'{latest_day}' AND baseline_7d_c IS NOT NULL")
          .toPandas())
for c in features:
    inputs[c] = pd.to_numeric(inputs[c], errors="coerce")

age_days = (today_sgt - latest_day).days
if age_days > 0:
    print(f"⚠️ WARNING: newest data is from {latest_day} ({age_days} day(s) old). Forecasting {latest_day + datetime.timedelta(days=1)} from stale data.")
else:
    print(f"Data is fresh: today's data ({latest_day}) is available for {len(inputs)} stations.")
missing_nea = inputs["nea_temp_high_c"].isna().mean()
print(f"NEA forecast for tomorrow available for {1 - missing_nea:.0%} of stations" + (" (model will rely on recent heat alone)" if missing_nea == 1 else ""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Forecast and save
# MAGIC
# MAGIC The model returns the forecast peak, its band, the chance of Moderate+ and High heat, and the High-heat alert. We save one row per station for tomorrow,
# MAGIC replacing any earlier forecast for the same day (so re-running is safe).

# COMMAND ----------

if inputs.empty:
    raise RuntimeError("No stations with recent heat data: run the ingestion and pipeline first.")

preds = model.predict(inputs[features])
out = pd.concat([inputs[["station_id", "station_name", "feature_date", "target_date"]].reset_index(drop=True), preds.reset_index(drop=True)], axis=1)
out = out.assign(model_name=MODEL_NAME, model_version=str(champion.version),
                 scored_at=datetime.datetime.now(datetime.timezone.utc))
target = out.target_date.iloc[0]

sdf = spark.createDataFrame(out).selectExpr(
    "station_id", "station_name", "CAST(feature_date AS DATE) feature_date", "CAST(target_date AS DATE) target_date",
    "CAST(predicted_peak_wbgt_c AS DOUBLE) predicted_peak_wbgt_c", "predicted_band",
    "CAST(prob_moderate_plus AS DOUBLE) prob_moderate_plus", "CAST(prob_high AS DOUBLE) prob_high",
    "CAST(high_alert AS BOOLEAN) high_alert", "CAST(high_alert_threshold AS DOUBLE) high_alert_threshold",
    "model_name", "model_version", "CAST(scored_at AS TIMESTAMP) scored_at")
sdf.write.mode("overwrite").option("replaceWhere", f"target_date = DATE'{target}'").saveAsTable(FORECAST_TABLE)
print(f"Saved {len(out)} station forecasts for {target}.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Tomorrow at a glance
# MAGIC
# MAGIC A quick island-wide summary: the hottest stations, how many are expected to reach Moderate or High, the highest chance of High heat,
# MAGIC and how many stations are on **High-heat alert** (chance of High at or above the threshold chosen in `05_forecast_model`).

# COMMAND ----------

summary = out.sort_values("predicted_peak_wbgt_c", ascending=False)
print(f"Forecast for {pd.Timestamp(target):%A %d %b %Y}: "
      f"{(summary.predicted_band == 'High').sum()} stations High, {(summary.predicted_band == 'Moderate').sum()} Moderate, "
      f"{(summary.predicted_band == 'Low').sum()} Low. Hottest: {summary.station_name.iloc[0]} at {summary.predicted_peak_wbgt_c.iloc[0]:.1f} °C. "
      f"Highest chance of High heat: {summary.prob_high.max():.0%}; {int(summary.high_alert.sum())} station(s) on High-heat alert.")
display(summary[["station_name", "predicted_peak_wbgt_c", "predicted_band", "prob_moderate_plus", "prob_high", "high_alert"]])

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Track record view
# MAGIC
# MAGIC `ml_forecast_track_record` joins every saved forecast with the afternoon peak that was later observed, so we can show
# MAGIC (and judges can check) how the live forecasts have performed, day by day. Forecasts for days not yet observed simply have no actual value yet.

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE VIEW {CATALOG}.{SCHEMA}.ml_forecast_track_record
COMMENT 'Every saved station forecast next to the afternoon peak WBGT actually observed (null until that day has been observed).'
AS SELECT f.station_id, f.station_name, f.feature_date, f.target_date, f.predicted_peak_wbgt_c, f.predicted_band,
          f.prob_moderate_plus, f.prob_high, f.high_alert, f.model_version,
          p.afternoon_peak_wbgt_c AS actual_peak_wbgt_c, p.afternoon_peak_band AS actual_band,
          round(abs(f.predicted_peak_wbgt_c - p.afternoon_peak_wbgt_c), 2) AS abs_error_c
   FROM {FORECAST_TABLE} f
   LEFT JOIN {CATALOG}.{SCHEMA}.silver_wbgt_daily_peak p
     ON p.station_id = f.station_id AND p.date_sgt = f.target_date AND p.afternoon_readings >= 12
""")
display(spark.sql(f"""SELECT target_date, count(*) stations, round(avg(abs_error_c), 2) avg_error_c,
                             sum(CASE WHEN actual_band = predicted_band THEN 1 ELSE 0 END) correct_band
                      FROM {CATALOG}.{SCHEMA}.ml_forecast_track_record WHERE actual_peak_wbgt_c IS NOT NULL
                      GROUP BY target_date ORDER BY target_date DESC"""))
