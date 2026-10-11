# Databricks notebook source
# MAGIC %md
# MAGIC # 01 · Live ingestion (runs every 15 minutes as a job)
# MAGIC
# MAGIC Fetches the latest readings from the data.gov.sg real-time APIs and lands them in the `raw` volume as JSON Lines,
# MAGIC one new file per source per run. Auto Loader in the pipeline picks up new files incrementally.
# MAGIC
# MAGIC | Folder | API | What one line is |
# MAGIC |---|---|---|
# MAGIC | `raw/wbgt/` | Wet Bulb Globe Temperature (heat stress) | one 15-min record with all station readings (same layout as the backfill) |
# MAGIC | `raw/forecast_24h/` | 24-hour forecast | one forecast record (same layout as the backfill) |
# MAGIC | `raw/four_day_outlook/` | 4-day outlook | one outlook record |
# MAGIC | `raw/air_temperature/` | Air temperature | one timestamp with all station values, plus the station list |
# MAGIC | `raw/humidity/` | Relative humidity | one timestamp with all station values, plus the station list |
# MAGIC
# MAGIC Duplicates (the same reading fetched by two runs) are removed later in the pipeline, so overlapping runs are harmless.

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

SOURCES = {
    "wbgt":              (f"{BASE}/weather?api=wbgt", records),
    "forecast_24h":      (f"{BASE}/twenty-four-hr-forecast", records),
    "four_day_outlook":  (f"{BASE}/four-day-outlook", records),
    "air_temperature":   (f"{BASE}/air-temperature", station_readings),
    "humidity":          (f"{BASE}/relative-humidity", station_readings),
}

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
