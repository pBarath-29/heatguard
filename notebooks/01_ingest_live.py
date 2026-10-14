# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "6"
# ///
# MAGIC %md
# MAGIC # 01 · Live ingestion (runs every 15 minutes as a job)
# MAGIC
# MAGIC **What this notebook does:** fetches the **latest** readings from NEA's real-time APIs on data.gov.sg and saves each response as a new
# MAGIC file in the `raw` volume. It is run by the job **`heatguard-live-ingest`** every 15 minutes (NEA updates WBGT every 15 minutes).
# MAGIC The pipeline's Auto Loader then picks up each new file exactly once.
# MAGIC
# MAGIC **Why it exists alongside the daily backfill:** the daily job (`02_backfill` in refresh mode) is enough to forecast tomorrow. This live job
# MAGIC keeps the app's **"Now"** view current during the day and shows judges a real streaming source. It can be paused to save Free Edition quota
# MAGIC (decision of 11 Oct) and unpaused for the demo.
# MAGIC
# MAGIC | Folder | API | What one line in the file is |
# MAGIC |---|---|---|
# MAGIC | `raw/wbgt/` | Wet Bulb Globe Temperature (heat stress) | one 15-minute record with all station readings (same layout as the backfill) |
# MAGIC | `raw/forecast_24h/` | 24-hour forecast | one forecast record (same layout as the backfill) |
# MAGIC | `raw/four_day_outlook/` | 4-day outlook | one outlook record |
# MAGIC | `raw/air_temperature/` | Air temperature | one timestamp with all station values, plus the station list |
# MAGIC | `raw/humidity/` | Relative humidity | one timestamp with all station values, plus the station list |
# MAGIC | `raw/psi/` | Pollutant Standards Index (haze), hourly, 5 regions | one hourly record with all PSI measures, plus the region list |
# MAGIC | `raw/pm25/` | PM2.5 (haze), hourly, 5 regions | one hourly record, plus the region list |
# MAGIC
# MAGIC Overlapping runs are harmless: the same reading fetched twice is removed later in the pipeline (silver de-duplicates by station and time).

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Sources and how each response becomes lines in a file
# MAGIC
# MAGIC Each NEA API returns its data in a slightly different shape, so each source has a small function that turns the response into a list of
# MAGIC records (one per line of the JSON Lines file):
# MAGIC - **`records`** — WBGT and forecasts already come as a list of records.
# MAGIC - **`station_readings`** — temperature and humidity return a station list plus readings; we copy the station list onto every reading so each line is self-contained.
# MAGIC - **`region_items`** — PSI and PM2.5 return the 5 regions' locations plus hourly items; we copy the region list onto every item.
# MAGIC
# MAGIC The API key is read from the Databricks secret, never typed here.

# COMMAND ----------

import json, time, datetime
import requests

CATALOG, SCHEMA = "workspace", "heatguard"
RAW = f"/Volumes/{CATALOG}/{SCHEMA}/raw"
BASE = "https://api-open.data.gov.sg/v2/real-time/api"
HEADERS = {"x-api-key": dbutils.secrets.get(scope="heatguard", key="datagov_api_key")}

# name -> (url, how to turn the response into lines)
def records(data):
    return data.get("records") or []

def station_readings(data):
    """air-temperature / relative-humidity: one line per timestamp, carrying the station list and unit."""
    stations = data.get("stations") or []
    return [{"readingType": data.get("readingType"), "readingUnit": data.get("readingUnit"),
             "stations": stations, **r} for r in (data.get("readings") or [])]

def region_items(data):
    """psi / pm25: one line per hourly item, carrying the region list (name + label location)."""
    regions = data.get("regionMetadata") or []
    return [{"regionMetadata": regions, **i} for i in (data.get("items") or [])]

SOURCES = {
    "wbgt":              (f"{BASE}/weather?api=wbgt", records),
    "forecast_24h":      (f"{BASE}/twenty-four-hr-forecast", records),
    "four_day_outlook":  (f"{BASE}/four-day-outlook", records),
    "air_temperature":   (f"{BASE}/air-temperature", station_readings),
    "humidity":          (f"{BASE}/relative-humidity", station_readings),
    "psi":               (f"{BASE}/psi", region_items),
    "pm25":              (f"{BASE}/pm25", region_items),
}

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Fetch every source and save one new file each
# MAGIC
# MAGIC **Error handling, in order:**
# MAGIC - Network errors and rate limits (HTTP 429 / code 24): wait a little longer each time and retry, up to 5 times.
# MAGIC - "No data right now" (code 17): not an error — nothing is saved for that source this run.
# MAGIC - Any other API error: recorded as a failure for that source; the other sources still run.
# MAGIC
# MAGIC Each file is named with the fetch time (e.g. `live_20261014T103000Z.jsonl`) so files never overwrite each other, and every line records
# MAGIC `source = "live"` and when it was fetched.
# MAGIC
# MAGIC **When the job shows as failed:** only if **WBGT** — the main heat signal — could not be fetched. A missing haze or humidity reading is
# MAGIC logged but doesn't fail the run, so one flaky API doesn't stop heat data flowing.

# COMMAND ----------

def get_data(url, tries=5):
    for attempt in range(tries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            body = r.json()
        except Exception as e:
            last = f"{type(e).__name__}: {e}"
            time.sleep(2 * (attempt + 1)); continue
        if r.status_code == 429 or body.get("code") == 24:
            last = "rate limited"; time.sleep(3 * (attempt + 1)); continue
        if body.get("code") == 17:      # no data right now
            return {}
        if body.get("code") != 0:
            raise RuntimeError(f"{url}: {body.get('errorMsg')}")
        return body["data"]
    raise RuntimeError(f"{url}: gave up after {tries} tries ({last})")

fetched_at = datetime.datetime.now(datetime.timezone.utc)
stamp = fetched_at.strftime("%Y%m%dT%H%M%SZ")
results, failures = {}, []

for name, (url, to_lines) in SOURCES.items():
    try:
        lines = to_lines(get_data(url))
        if lines:
            dbutils.fs.mkdirs(f"{RAW}/{name}")
            with open(f"{RAW}/{name}/live_{stamp}.jsonl", "w", encoding="utf-8") as fh:
                for line in lines:
                    fh.write(json.dumps({"source": "live", "fetched_at": fetched_at.isoformat(), **line}) + "\n")
        results[name] = len(lines)
    except Exception as e:
        failures.append(f"{name}: {e}")
        results[name] = "FAILED"
    time.sleep(0.2)

print(f"Run at {fetched_at:%Y-%m-%d %H:%M} UTC →", results)

# Fail the job run (so it shows red in job history) only if the main signal is missing.
if results.get("wbgt") == "FAILED":
    raise RuntimeError("WBGT fetch failed: " + "; ".join(failures))
if failures:
    print("Non-critical failures:", failures)
