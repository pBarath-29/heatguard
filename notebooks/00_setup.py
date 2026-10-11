# Databricks notebook source
# MAGIC %md
# MAGIC # 00 · Setup and day-1 checks
# MAGIC
# MAGIC Run this once in the demo workspace. It:
# MAGIC 1. Creates the `heatguard` schema and the `raw` volume for landed files
# MAGIC 2. Tests whether this workspace can reach the data.gov.sg APIs (live, history, file downloads)
# MAGIC 3. Checks that the H3 / spatial SQL functions we need are available
# MAGIC 4. Lists the model-serving endpoints (Foundation Model APIs) we can use
# MAGIC
# MAGIC Read the **summary** in the last cell and paste it into `docs/decision-log.md`.

# COMMAND ----------

CATALOG = "workspace"   # Free Edition default catalog
SCHEMA = "heatguard"
VOLUME = "raw"

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA} COMMENT 'HeatGuard: next-day heat-risk check-in list for eldercare outreach (DAISI 2026, B1)'")
spark.sql(f"CREATE VOLUME IF NOT EXISTS {CATALOG}.{SCHEMA}.{VOLUME} COMMENT 'Raw files landed from data.gov.sg APIs and downloads'")

VOLUME_PATH = f"/Volumes/{CATALOG}/{SCHEMA}/{VOLUME}"
dbutils.fs.mkdirs(f"{VOLUME_PATH}/_setup_test")
print("Schema and volume ready:", VOLUME_PATH)

# COMMAND ----------

# MAGIC %md
# MAGIC ## API key (optional for this test)
# MAGIC
# MAGIC Without a key, data.gov.sg allows only a few calls per 10 seconds; the backfill needs one.
# MAGIC Store it as a secret so it never appears in a notebook or on screen during the demo:
# MAGIC
# MAGIC ```
# MAGIC databricks secrets create-scope heatguard
# MAGIC databricks secrets put-secret heatguard datagov_api_key
# MAGIC ```
# MAGIC This cell runs fine without a key; it just uses the lower rate limit.

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
# MAGIC ## Can this workspace reach data.gov.sg?

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
# MAGIC ## Can we download a file? (downloads are served from Amazon S3, a different host)

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
# MAGIC ## Spatial functions (station → subzone mapping, distance to nearest cool space)

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
# MAGIC ## Which model-serving endpoints (Foundation Model APIs) are available?

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
# MAGIC ## Summary: paste this into `docs/decision-log.md`

# COMMAND ----------

print(f"Setup check run at {time.strftime('%Y-%m-%d %H:%M')} (API key: {'yes' if API_KEY else 'no'})")
for k, v in results.items():
    print(f"- {k}: {v}")

api_ok = all(results[k].startswith("OK") for k in checks)
print("\nVERDICT:", "Workspace can reach data.gov.sg directly: ingest from notebooks/jobs."
      if api_ok and results["file_download_s3"].startswith("OK")
      else "Some calls failed: try 'Verify identity' (top right), then re-run; otherwise ingest via an external poller into the volume.")
