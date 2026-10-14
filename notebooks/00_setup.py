# Databricks notebook source
# MAGIC %md
# MAGIC # 00 · Setup and day-1 checks
# MAGIC
# MAGIC **What this notebook is for:** run it **once** in a new workspace, before anything else. It prepares the place where all HeatGuard data
# MAGIC lives and checks that everything we depend on actually works on Databricks Free Edition — so we find blockers on day 1, not on demo day.
# MAGIC
# MAGIC **What it does:**
# MAGIC 1. Creates the `workspace.heatguard` schema (a folder for our tables), the `raw` volume (a folder for downloaded files) and the empty
# MAGIC    forecast table the pipeline reads.
# MAGIC 2. Checks the data.gov.sg API key is stored as a secret (never typed into a notebook).
# MAGIC 3. Tests that this workspace can reach every data.gov.sg API we use (live readings, history, forecasts, Census, file downloads).
# MAGIC 4. Checks the map functions we need (distances, points) are available.
# MAGIC 5. Lists the AI model endpoints (Foundation Model APIs) this workspace can call.
# MAGIC 6. Prints a summary and a verdict to paste into `docs/decision-log.md`.
# MAGIC
# MAGIC **Result on 11 Oct 2026:** every check passed, so we ingest directly from Databricks with no external poller.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Create the schema, the raw-files volume and the forecast table
# MAGIC
# MAGIC - **Schema** `workspace.heatguard`: every table HeatGuard creates lives here, so permissions and lineage are managed in one place in Unity Catalog.
# MAGIC - **Volume** `raw`: a governed folder for the JSON and CSV files we download. Keeping the original files means we can always rebuild the tables from source.
# MAGIC - **Table** `ml_wbgt_forecast`: created empty so the pipeline can always read it. `06_score_forecast` fills it with tomorrow's forecast every day;
# MAGIC   until then, the check-in list falls back to observed heat.
# MAGIC
# MAGIC `IF NOT EXISTS` makes this safe to re-run: nothing is overwritten.

# COMMAND ----------

CATALOG = "workspace"   # Free Edition default catalog
SCHEMA = "heatguard"
VOLUME = "raw"

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA} COMMENT 'HeatGuard: next-day heat-risk check-in list for eldercare outreach (DAISI 2026, B1)'")
spark.sql(f"CREATE VOLUME IF NOT EXISTS {CATALOG}.{SCHEMA}.{VOLUME} COMMENT 'Raw files landed from data.gov.sg APIs and downloads'")
spark.sql(f"""CREATE TABLE IF NOT EXISTS {CATALOG}.{SCHEMA}.ml_wbgt_forecast (
  station_id STRING COMMENT 'NEA WBGT station id', station_name STRING, feature_date DATE COMMENT 'Day the forecast was made (SGT)',
  target_date DATE COMMENT 'Day being forecast (SGT)', predicted_peak_wbgt_c DOUBLE COMMENT 'Forecast afternoon (12:00-17:59) peak WBGT, deg C',
  predicted_band STRING COMMENT 'NEA band of the forecast peak', prob_moderate_plus DOUBLE COMMENT 'Chance the peak reaches 31 deg C or more',
  prob_high DOUBLE COMMENT 'Chance the peak reaches 33 deg C or more', high_alert BOOLEAN COMMENT 'Chance of High at or above the alert threshold',
  high_alert_threshold DOUBLE COMMENT 'Alert threshold chosen in 05_forecast_model', model_name STRING, model_version STRING, scored_at TIMESTAMP)
COMMENT 'Tomorrow forecast of afternoon peak WBGT per station, written daily by 06_score_forecast (one row per station per target date).'""")

VOLUME_PATH = f"/Volumes/{CATALOG}/{SCHEMA}/{VOLUME}"
dbutils.fs.mkdirs(f"{VOLUME_PATH}/_setup_test")
print("Schema, volume and forecast table ready:", VOLUME_PATH)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. The data.gov.sg API key
# MAGIC
# MAGIC Without a key, data.gov.sg allows only a few calls every 10 seconds — far too slow to download 20 months of history.
# MAGIC With a (free) production key, the limit is 30 calls per 10 seconds.
# MAGIC
# MAGIC The key is stored as a **Databricks secret**, so it never appears in a notebook, a log or on screen during the demo. It was stored once with the Databricks CLI:
# MAGIC
# MAGIC ```
# MAGIC databricks secrets create-scope heatguard
# MAGIC databricks secrets put-secret heatguard datagov_api_key
# MAGIC ```
# MAGIC The cell below only checks the secret exists. If it doesn't, the checks still run, just with the lower no-key rate limit.

# COMMAND ----------

def get_api_key():
    try:
        return dbutils.secrets.get(scope="heatguard", key="datagov_api_key")
    except Exception:
        return None

API_KEY = get_api_key()
HEADERS = {"x-api-key": API_KEY} if API_KEY else {}
print("API key found in secrets" if API_KEY else "No API key found: running with no-key rate limits")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Can this workspace reach data.gov.sg?
# MAGIC
# MAGIC Free Edition runs on serverless compute, which may restrict outbound internet access. We call each API we depend on once:
# MAGIC
# MAGIC | Check | Why we need it |
# MAGIC |---|---|
# MAGIC | `wbgt_live` | Latest heat-stress readings (the main signal) |
# MAGIC | `wbgt_history` | Past readings, to train the forecast model |
# MAGIC | `air_temperature`, `humidity` | Supporting weather readings |
# MAGIC | `forecast_24h` | NEA's own forecast for tomorrow (a model input) |
# MAGIC | `datastore_census` | Census 2020 tables (who lives where) |
# MAGIC
# MAGIC If the API says we're calling too fast (HTTP 429 or data.gov.sg code 24), the helper waits and retries instead of failing.

# COMMAND ----------

import time
import requests

BASE = "https://api-open.data.gov.sg"
checks = {
    "wbgt_live":        f"{BASE}/v2/real-time/api/weather?api=wbgt",
    "wbgt_history":     f"{BASE}/v2/real-time/api/weather?api=wbgt&date=2025-03-01",
    "air_temperature":  f"{BASE}/v2/real-time/api/air-temperature",
    "humidity":         f"{BASE}/v2/real-time/api/relative-humidity",
    "forecast_24h":     f"{BASE}/v2/real-time/api/twenty-four-hr-forecast",
    "datastore_census": "https://data.gov.sg/api/action/datastore_search?resource_id=d_d95ae740c0f8961a0b10435836660ce0&limit=1",
}

def call(url, tries=4):
    """GET with retry on rate limiting (HTTP 429 or data.gov.sg code 24)."""
    for attempt in range(tries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
        except Exception as e:
            return None, f"BLOCKED / network error: {type(e).__name__}: {e}"[:200]
        rate_limited = r.status_code == 429 or (r.headers.get("content-type", "").startswith("application/json") and r.json().get("code") == 24)
        if not rate_limited:
            return r, f"HTTP {r.status_code}"
        time.sleep(11)
    return r, "rate limited after retries"

results = {}
for name, url in checks.items():
    r, status = call(url)
    ok = r is not None and r.status_code == 200
    results[name] = ("OK" if ok else "FAIL") + f" ({status})"
    print(f"{name:18} {results[name]}")
    time.sleep(2)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Can we download a file?
# MAGIC
# MAGIC Dataset files (Census CSVs, map GeoJSON) are not served by the API itself: the API returns a temporary link to Amazon S3, a different website.
# MAGIC Serverless compute could reach one and not the other, so we test a real download — the small Community Clubs file — and save it to the volume.

# COMMAND ----------

CC_DATASET = "d_f706de1427279e61fe41e89e24d440fa"  # Community Clubs (GeoJSON), small file
r, status = call(f"{BASE}/v1/public/api/datasets/{CC_DATASET}/poll-download")
try:
    file_url = r.json()["data"]["url"]
    f = requests.get(file_url, timeout=60)
    f.raise_for_status()
    out = f"{VOLUME_PATH}/_setup_test/community_clubs.geojson"
    with open(out, "wb") as fh:
        fh.write(f.content)
    results["file_download_s3"] = f"OK ({len(f.content):,} bytes saved to volume)"
except Exception as e:
    results["file_download_s3"] = f"FAIL ({status}; {type(e).__name__}: {str(e)[:150]})"
print(results["file_download_s3"])

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Map functions
# MAGIC
# MAGIC The pipeline measures distances on the earth's surface — station to subzone, subzone to the nearest Community Club or library — using
# MAGIC Databricks' built-in spatial SQL functions. We check each one returns a sensible value (e.g. the distance between two points in Singapore
# MAGIC should be roughly 15 km, not an error).

# COMMAND ----------

spatial_tests = {
    "h3": "SELECT h3_longlatash3(103.85, 1.35, 8) AS cell",
    "st_point": "SELECT st_astext(st_point(103.85, 1.35)) AS pt",
    "st_distance": "SELECT st_distancesphere(st_point(103.85, 1.35), st_point(103.98, 1.37)) AS metres",
}
for name, sql in spatial_tests.items():
    try:
        val = spark.sql(sql).first()[0]
        results[f"spatial_{name}"] = f"OK ({val})"
    except Exception as e:
        results[f"spatial_{name}"] = f"FAIL ({str(e).splitlines()[0][:150]})"
    print(f"spatial_{name:12} {results[f'spatial_{name}']}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Which AI model endpoints can we use?
# MAGIC
# MAGIC The app uses a large language model only to **rewrite** rulebook actions into a friendly message (it never chooses the actions).
# MAGIC Free Edition offers a set of hosted Foundation Model APIs; this lists the ones available in this workspace. We chose
# MAGIC `databricks-meta-llama-3-3-70b-instruct` (strong instruction-following and multilingual output).

# COMMAND ----------

try:
    from databricks.sdk import WorkspaceClient
    endpoints = sorted(e.name for e in WorkspaceClient().serving_endpoints.list())
    results["serving_endpoints"] = f"{len(endpoints)} found"
    for name in endpoints:
        print(name)
except Exception as e:
    results["serving_endpoints"] = f"FAIL ({str(e)[:150]})"
    print(results["serving_endpoints"])

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Summary and verdict
# MAGIC
# MAGIC One line per check, then a verdict: if every API call and the file download worked, we can ingest directly from Databricks notebooks
# MAGIC and jobs. If not, the message says what to try next. Paste the output into `docs/decision-log.md`.

# COMMAND ----------

print(f"Setup check run at {time.strftime('%Y-%m-%d %H:%M')} (API key: {'yes' if API_KEY else 'no'})")
for k, v in results.items():
    print(f"- {k}: {v}")

api_ok = all(results[k].startswith("OK") for k in checks)
print("\nVERDICT:", "Workspace can reach data.gov.sg directly: ingest from notebooks/jobs."
      if api_ok and results["file_download_s3"].startswith("OK")
      else "Some calls failed: try 'Verify identity' (top right), then re-run; otherwise ingest via an external poller into the volume.")
