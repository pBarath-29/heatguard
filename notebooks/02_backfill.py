# Databricks notebook source
# MAGIC %md
# MAGIC # 02 · Backfill history (heat stress, NEA forecasts, haze)
# MAGIC
# MAGIC Downloads past data from the data.gov.sg real-time APIs into the `raw` volume, one file per day:
# MAGIC
# MAGIC | Folder | API | Per day |
# MAGIC |---|---|---|
# MAGIC | `raw/wbgt/` | Wet Bulb Globe Temperature (heat stress), every 15 min, from 16 Jan 2025 | 96 readings, 4 pages |
# MAGIC | `raw/forecast_24h/` | NEA 24-hour forecast | ~8 records, 1 call |
# MAGIC | `raw/psi/` | Pollutant Standards Index (haze), hourly, 5 regions | 24 records, 1 call |
# MAGIC | `raw/pm25/` | PM2.5 (haze), hourly, 5 regions | 24 records, 1 call |
# MAGIC
# MAGIC Each file is JSON Lines (one API record per line), the same layout the live job writes, so one Auto Loader stream reads both.
# MAGIC
# MAGIC **Resumable:** days already saved are skipped, so if it stops, just run it again.
# MAGIC With the production API key the full run (Feb 2025 → yesterday) takes roughly 20–30 minutes.

# COMMAND ----------

import json, time, datetime
import requests

CATALOG, SCHEMA = "workspace", "heatguard"
RAW = f"/Volumes/{CATALOG}/{SCHEMA}/raw"
API_KEY = dbutils.secrets.get(scope="heatguard", key="datagov_api_key")
HEADERS = {"x-api-key": API_KEY}
BASE = "https://api-open.data.gov.sg/v2/real-time/api"

START = datetime.date(2025, 1, 16)          # first day of WBGT history on the API (checked 11 Oct 2026)
END = datetime.date.today() - datetime.timedelta(days=1)   # today's data comes from the live job

SOURCES = {
    "wbgt":         {"url": f"{BASE}/weather?api=wbgt", "list_key": "records"},
    "forecast_24h": {"url": f"{BASE}/twenty-four-hr-forecast", "list_key": "records"},
    # haze: each line also carries the region list (5 regions with label locations), same layout as the live job
    "psi":          {"url": f"{BASE}/psi", "list_key": "items", "keep": ["regionMetadata"]},
    "pm25":         {"url": f"{BASE}/pm25", "list_key": "items", "keep": ["regionMetadata"]},
}
for name in SOURCES:
    dbutils.fs.mkdirs(f"{RAW}/{name}")

# COMMAND ----------

session = requests.Session()
session.headers.update(HEADERS)

def get_page(url, tries=6):
    """One API call with backoff on rate limits (HTTP 429 / code 24) and transient errors."""
    for attempt in range(tries):
        try:
            r = session.get(url, timeout=60)
            body = r.json()
        except Exception:
            time.sleep(2 * (attempt + 1)); continue
        if r.status_code == 429 or body.get("code") == 24:
            time.sleep(4 * (attempt + 1)); continue
        if body.get("code") == 17:          # REAL_TIME_API_DATA_NOT_FOUND: no data for that day
            return {}
        if body.get("code") != 0:
            raise RuntimeError(f"API error for {url}: {body.get('errorMsg')}")
        return body["data"]
    raise RuntimeError(f"Gave up after {tries} tries: {url}")

def fetch_day(source, day):
    """All records for one day, following paginationToken."""
    cfg = SOURCES[source]
    sep = "&" if "?" in cfg["url"] else "?"
    url = f"{cfg['url']}{sep}date={day.isoformat()}"
    records, token = [], None
    while True:
        data = get_page(url + (f"&paginationToken={requests.utils.quote(token)}" if token else ""))
        extra = {k: data.get(k) for k in cfg.get("keep", [])}
        records.extend({**extra, **rec} for rec in (data.get(cfg["list_key"]) or []))
        token = data.get("paginationToken")
        time.sleep(0.35)                    # stays under the production limit (30 calls / 10 s)
        if not token:
            return records

def exists(path):
    try:
        dbutils.fs.ls(path); return True
    except Exception:
        return False

# COMMAND ----------

# MAGIC %md
# MAGIC ## Run the backfill

# COMMAND ----------

summary = {name: {"saved": 0, "skipped": 0, "empty": 0} for name in SOURCES}
day = START
started = time.time()
while day <= END:
    for source in SOURCES:
        path = f"{RAW}/{source}/history_{day.isoformat()}.jsonl"
        if exists(path):
            summary[source]["skipped"] += 1; continue
        records = fetch_day(source, day)
        if not records:
            summary[source]["empty"] += 1; continue
        with open(path, "w", encoding="utf-8") as fh:
            for rec in records:
                fh.write(json.dumps({"source": "history", "fetched_for_date": day.isoformat(), **rec}) + "\n")
        summary[source]["saved"] += 1
    if day.day == 1:
        print(f"{day:%b %Y} … {summary}  ({(time.time() - started) / 60:.1f} min)")
    day += datetime.timedelta(days=1)

print(f"\nDone in {(time.time() - started) / 60:.1f} min: {summary}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Check: days saved and stations per day
# MAGIC The WBGT network has grown over time (8 stations in early 2025, ~30 now), so expect the station count to rise.

# COMMAND ----------

wbgt = spark.read.json(f"{RAW}/wbgt/history_*.jsonl")
from pyspark.sql import functions as F
per_month = (wbgt
    .select(F.substring("datetime", 1, 7).alias("month"), F.explode("item.readings").alias("r"))
    .groupBy("month").agg(F.countDistinct("r.station.id").alias("stations"), F.count("*").alias("readings"))
    .orderBy("month"))
display(per_month)
