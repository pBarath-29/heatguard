# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "6"
# ///
# MAGIC %md
# MAGIC # 02 · Backfill history (heat stress, NEA forecasts, haze)
# MAGIC
# MAGIC **What this notebook does:** downloads past data from NEA's real-time APIs on data.gov.sg (which accept a `date=` parameter) and saves
# MAGIC **one file per source per day** in the `raw` volume. This history is what the forecast model learns from.
# MAGIC
# MAGIC | Folder | API | Per day |
# MAGIC |---|---|---|
# MAGIC | `raw/wbgt/` | Wet Bulb Globe Temperature (heat stress), every 15 minutes, from 16 Jan 2025 | 96 readings, 4 pages |
# MAGIC | `raw/forecast_24h/` | NEA 24-hour forecast | ~8 issued forecasts, 1 call |
# MAGIC | `raw/psi/` | Pollutant Standards Index (haze), hourly, 5 regions | 24 records, 1 call |
# MAGIC | `raw/pm25/` | PM2.5 (haze), hourly, 5 regions | 24 records, 1 call |
# MAGIC
# MAGIC Each file is JSON Lines (one API record per line) in the same layout the live job writes, so a single Auto Loader stream in the pipeline reads both.
# MAGIC
# MAGIC **Two ways to run it:**
# MAGIC - **Full backfill** (default: `start_date` = 2025-01-16, `refresh_days` = 0): fetches every missing day up to yesterday. **Resumable** — days
# MAGIC   already saved are skipped, so if it stops, just run it again. With the production API key the full run takes about 30 minutes.
# MAGIC - **Daily refresh** (used by the `heatguard-daily` job: `start_date` = `recent`, `refresh_days` = 1): also re-fetches **today and
# MAGIC   yesterday**, which are still filling up, so the evening forecast uses today's complete afternoon.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Settings
# MAGIC
# MAGIC **Parameters** (widgets at the top of the notebook, or `base_parameters` when run by a job):
# MAGIC - `start_date` — first day to fetch (default: 16 Jan 2025, the first day of WBGT history on the API, checked 11 Oct 2026),
# MAGIC   or `recent` for the last 3 days (used by the daily job, so it only checks a few days instead of 600+).
# MAGIC - `refresh_days` — how many recent days to **re-fetch every run** (0 = none). Recent days are saved as new `recent_<day>_<time>.jsonl`
# MAGIC   files rather than overwriting, because Auto Loader only reads each file once; the pipeline removes the duplicate readings.
# MAGIC   Once a day falls out of the refresh window, a complete `history_<day>.jsonl` file is fetched for it as normal.
# MAGIC
# MAGIC "Today" is Singapore time (UTC+8), because NEA's days are Singapore days.

# COMMAND ----------

import json, time, datetime
import requests

dbutils.widgets.text("start_date", "2025-01-16", "First day to fetch (YYYY-MM-DD)")
dbutils.widgets.text("refresh_days", "0", "Recent days to re-fetch every run")

CATALOG, SCHEMA = "workspace", "heatguard"
RAW = f"/Volumes/{CATALOG}/{SCHEMA}/raw"
API_KEY = dbutils.secrets.get(scope="heatguard", key="datagov_api_key")
HEADERS = {"x-api-key": API_KEY}
BASE = "https://api-open.data.gov.sg/v2/real-time/api"

TODAY_SGT = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=8)).date()
_start = dbutils.widgets.get("start_date").strip() or "2025-01-16"
START = TODAY_SGT - datetime.timedelta(days=3) if _start == "recent" else datetime.date.fromisoformat(_start)
REFRESH_DAYS = int(dbutils.widgets.get("refresh_days").strip() or 0)
REFRESH_FROM = TODAY_SGT - datetime.timedelta(days=REFRESH_DAYS) if REFRESH_DAYS > 0 else None
END = TODAY_SGT if REFRESH_DAYS > 0 else TODAY_SGT - datetime.timedelta(days=1)
STAMP = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")

SOURCES = {
    "wbgt":         {"url": f"{BASE}/weather?api=wbgt", "list_key": "records"},
    "forecast_24h": {"url": f"{BASE}/twenty-four-hr-forecast", "list_key": "records"},
    # haze: each line also carries the region list (5 regions with label locations), same layout as the live job
    "psi":          {"url": f"{BASE}/psi", "list_key": "items", "keep": ["regionMetadata"]},
    "pm25":         {"url": f"{BASE}/pm25", "list_key": "items", "keep": ["regionMetadata"]},
}
for name in SOURCES:
    dbutils.fs.mkdirs(f"{RAW}/{name}")
print(f"Fetching {START} → {END} (SGT)" + (f"; re-fetching {REFRESH_FROM} onwards every run" if REFRESH_FROM else ""))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Download helpers
# MAGIC
# MAGIC - **`get_page`** — one API call. If data.gov.sg says we're going too fast (HTTP 429 / code 24) or the network hiccups, it waits a little longer
# MAGIC   each time and retries (up to 6 times). Code 17 means "no data for that day", which is returned as empty rather than an error.
# MAGIC - **`fetch_day`** — all records for one source and one day. WBGT history comes in pages, so it follows the `paginationToken` until the last page.
# MAGIC   A 0.35-second pause between calls keeps us under the production limit (30 calls per 10 seconds).
# MAGIC - **`exists`** — whether a day's file is already saved, which makes the backfill resumable.

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
# MAGIC ## 3. Run the backfill
# MAGIC
# MAGIC Goes day by day from `start_date` to the end date, for each source:
# MAGIC - **Recent day** (inside the refresh window): always fetched again and saved as a new `recent_…` file.
# MAGIC - **Older day already saved**: skipped.
# MAGIC - **Older day not yet saved**: fetched and saved as `history_<day>.jsonl`; days with no data are counted as empty.
# MAGIC
# MAGIC Every line records `source = "history"` and the day it was fetched for. Progress is printed at the start of each month, and a summary at the end.

# COMMAND ----------

summary = {name: {"saved": 0, "refreshed": 0, "skipped": 0, "empty": 0} for name in SOURCES}
day = START
started = time.time()
while day <= END:
    recent = REFRESH_FROM is not None and day >= REFRESH_FROM
    for source in SOURCES:
        path = (f"{RAW}/{source}/recent_{day.isoformat()}_{STAMP}.jsonl" if recent
                else f"{RAW}/{source}/history_{day.isoformat()}.jsonl")
        if not recent and exists(path):
            summary[source]["skipped"] += 1; continue
        records = fetch_day(source, day)
        if not records:
            summary[source]["empty"] += 1; continue
        with open(path, "w", encoding="utf-8") as fh:
            for rec in records:
                fh.write(json.dumps({"source": "history", "fetched_for_date": day.isoformat(), **rec}) + "\n")
        summary[source]["refreshed" if recent else "saved"] += 1
    if day.day == 1:
        print(f"{day:%b %Y} … {summary}  ({(time.time() - started) / 60:.1f} min)")
    day += datetime.timedelta(days=1)

print(f"\nDone in {(time.time() - started) / 60:.1f} min: {summary}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Check: stations and readings per month
# MAGIC
# MAGIC A quick sanity check on the saved WBGT history. Expect the number of stations to **rise over time** — the network grew from 8 stations in
# MAGIC early 2025 to 30 by August 2026 — and roughly 96 readings per station per day. A sudden drop in a month would point to a gap worth investigating.

# COMMAND ----------

wbgt = spark.read.json(f"{RAW}/wbgt/history_*.jsonl")
from pyspark.sql import functions as F
per_month = (wbgt
    .select(F.substring("datetime", 1, 7).alias("month"), F.explode("item.readings").alias("r"))
    .groupBy("month").agg(F.countDistinct("r.station.id").alias("stations"), F.count("*").alias("readings"))
    .orderBy("month"))
display(per_month)
