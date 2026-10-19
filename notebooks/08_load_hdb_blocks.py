# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "6"
# ///
# MAGIC %md
# MAGIC # 08 · HDB blocks: load and place on the map (for Block Radar)
# MAGIC
# MAGIC **Why:** an area-level list says *Bedok North is a priority*; volunteers then need to know **which blocks** to visit. HDB's
# MAGIC **Property Information** dataset (data.gov.sg) lists every HDB block with its 1-room and 2-room **rental** flats, year completed and
# MAGIC highest floor — but no coordinates and no subzone. This notebook:
# MAGIC
# MAGIC 1. Downloads HDB Property Information into **`bronze_hdb_property`** (as published, values as text).
# MAGIC 2. Finds each residential block's location with **OneMap** (Singapore Land Authority's address search) and caches it in
# MAGIC    **`silver_hdb_block_geocode`**. The pipeline then places each block in its subzone (`gold_hdb_blocks`).
# MAGIC
# MAGIC **Matching rules (to avoid wrong matches between similar addresses):** HDB abbreviates street names ("BEDOK NTH AVE 4"). We expand the
# MAGIC abbreviations and accept a OneMap result **only if the block number matches exactly and the full street name matches exactly**.
# MAGIC Results more than 150 m apart for the same block and street → `ambiguous` (results closer than that are entrances of one block); none → `unmatched`. Both are kept (without coordinates) so the
# MAGIC app can list blocks it could not place.
# MAGIC
# MAGIC **Resumable and polite:** blocks already in the cache are skipped (re-run any time, e.g. after HDB updates the dataset); requests are
# MAGIC paced well below OneMap's limit and retried with back-off on errors. A first full run (about 10,800 blocks) takes roughly an hour.
# MAGIC
# MAGIC **Important:** rental-flat counts are a **proxy** for where outreach may be needed. They are not counts of elderly residents,
# MAGIC low-income households or homes without air-conditioning.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Settings

# COMMAND ----------

import datetime, json, re, time
import threading
from concurrent.futures import ThreadPoolExecutor

import requests
from pyspark.sql import functions as F

CATALOG, SCHEMA = "workspace", "heatguard"
DATASET_ID = "d_17f5382f26140b1fdae0ba2ef6239d2f"   # HDB Property Information (data.gov.sg)
BRONZE = f"{CATALOG}.{SCHEMA}.bronze_hdb_property"
CACHE = f"{CATALOG}.{SCHEMA}.silver_hdb_block_geocode"
STATIC_DIR = f"/Volumes/{CATALOG}/{SCHEMA}/raw/static"
HEADERS = {"x-api-key": dbutils.secrets.get(scope="heatguard", key="datagov_api_key")}
ONEMAP = "https://www.onemap.gov.sg/api/common/elastic/search"
MAX_RPS = 3.5            # all threads together: ~210 requests a minute, under OneMap's published 250/min
WORKERS = 3              # a few requests in flight at once (each takes ~0.5 s), still capped by MAX_RPS
BATCH = 250              # write to the cache every 250 blocks, so a stopped run loses little

dbutils.widgets.text("max_blocks", "0", "Max blocks to geocode this run (0 = all)")
MAX_BLOCKS = int(dbutils.widgets.get("max_blocks") or 0)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Download HDB Property Information → `bronze_hdb_property`
# MAGIC Fetched with the data.gov.sg download API (the same two-step download as `03_load_static`) and saved unchanged, all values as text.

# COMMAND ----------

def get_json(url, tries=5):
    for attempt in range(tries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=60)
            body = r.json()
        except Exception:
            time.sleep(3 * (attempt + 1)); continue
        if r.status_code == 429 or body.get("code") == 24:
            time.sleep(4 * (attempt + 1)); continue
        r.raise_for_status()
        return body
    raise RuntimeError(f"Gave up after {tries} tries: {url}")

meta = get_json(f"https://api-open.data.gov.sg/v1/public/api/datasets/{DATASET_ID}/poll-download")
csv_path = f"{STATIC_DIR}/hdb_property_information.csv"
with open(csv_path, "wb") as fh:
    fh.write(requests.get(meta["data"]["url"], timeout=120).content)

loaded_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
(spark.read.option("header", True).option("inferSchema", False).csv(csv_path)
 .withColumn("_source_dataset_id", F.lit(DATASET_ID)).withColumn("_loaded_at", F.lit(loaded_at).cast("timestamp"))
 .write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(BRONZE))
spark.sql(f"COMMENT ON TABLE {BRONZE} IS 'HDB Property Information (data.gov.sg {DATASET_ID}): one row per HDB block with year completed, highest floor and flat counts incl. 1-room and 2-room rental flats. Bronze: values as text.'")
print(f"{BRONZE}: {spark.table(BRONZE).count():,} blocks, {spark.table(BRONZE).where('residential = \"Y\"').count():,} residential")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Address matching helpers
# MAGIC `expand` turns HDB's short street names into the full names OneMap uses. `match` applies the strict rule: exact block number and
# MAGIC exact full street name; several distinct coordinates → ambiguous.

# COMMAND ----------

ABBREV = {
    "AVE": "AVENUE", "ST": "STREET", "RD": "ROAD", "DR": "DRIVE", "CRES": "CRESCENT", "NTH": "NORTH", "STH": "SOUTH",
    "CTRL": "CENTRAL", "LOR": "LORONG", "JLN": "JALAN", "KG": "KAMPONG", "BT": "BUKIT", "TG": "TANJONG", "UPP": "UPPER",
    "PK": "PARK", "HTS": "HEIGHTS", "TER": "TERRACE", "CL": "CLOSE", "PL": "PLACE", "GDNS": "GARDENS", "CTR": "CENTRE",
    "MKT": "MARKET", "SQ": "SQUARE", "MT": "MOUNT", "CT": "COURT", "LK": "LINK", "C'WEALTH": "COMMONWEALTH",
    "CWEALTH": "COMMONWEALTH", "BLVD": "BOULEVARD", "HWAY": "HIGHWAY", "GR": "GROVE", "VW": "VIEW",
}

def expand(street):
    out = []
    for tok in street.upper().split():
        out.append("SAINT" if tok == "ST." else ABBREV.get(tok, tok))
    return " ".join(out)

def norm(s):
    return re.sub(r"[^A-Z0-9 ]", "", (s or "").upper().replace("SAINT", "ST")).strip()

_gate, _next = threading.Lock(), [0.0]

def _wait_turn():
    """Global pace for all threads: at most MAX_RPS requests per second."""
    with _gate:
        now = time.monotonic()
        t = max(now, _next[0])
        _next[0] = t + 1 / MAX_RPS
    time.sleep(max(0.0, t - now))

def search(q, tries=4):
    for attempt in range(tries):
        _wait_turn()
        try:
            r = requests.get(ONEMAP, params={"searchVal": q, "returnGeom": "Y", "getAddrDetails": "Y", "pageNum": 1}, timeout=20)
            if r.status_code == 429:
                time.sleep(5 * (attempt + 1)); continue
            r.raise_for_status()
            return r.json().get("results") or []
        except Exception:
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"OneMap search failed: {q}")

def match(blk, street):
    full = expand(street)
    results = search(f"{blk} {full}")
    if not any(r.get("BLK_NO") == blk for r in results):
        results += search(f"{blk} {street}")          # some names are only found in short form
    hits = [r for r in results if r.get("BLK_NO", "").upper() == blk.upper() and norm(r.get("ROAD_NAME")) == norm(full)]
    if not hits:
        return {"match_status": "unmatched", "candidates": len(results)}
    pts = [(float(r["LATITUDE"]), float(r["LONGITUDE"])) for r in hits]
    spread_km = max(((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5 * 111 for a in pts for b in pts)
    if spread_km > 0.15:                                  # same block + street at clearly different places → don't guess
        return {"match_status": "ambiguous", "candidates": len(hits)}
    best = sorted(hits, key=lambda r: r.get("POSTAL") in (None, "", "NIL"))[0]
    return {"match_status": "matched", "candidates": len(hits), "street_full": best["ROAD_NAME"], "postal": best.get("POSTAL"),
            "onemap_address": best.get("ADDRESS"), "latitude": float(best["LATITUDE"]), "longitude": float(best["LONGITUDE"])}

print(expand("BEDOK NTH AVE 4"), "|", expand("C'WEALTH DR"), "|", expand("ST. GEORGE'S RD"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Geocode residential blocks not yet in the cache → `silver_hdb_block_geocode`
# MAGIC Blocks with 1- or 2-room rental flats go first (Block Radar ranks those), then the rest. A few lookups run at once, but all
# MAGIC threads share one pace limit (`MAX_RPS`). Progress is printed every batch. Network or OneMap errors on a block are recorded as
# MAGIC `error` and retried on the next run.

# COMMAND ----------

spark.sql(f"""CREATE TABLE IF NOT EXISTS {CACHE} (
  blk_no STRING, street STRING, street_full STRING, postal STRING, onemap_address STRING, latitude DOUBLE, longitude DOUBLE,
  match_status STRING COMMENT 'matched / ambiguous / unmatched / error', candidates INT, geocoded_at TIMESTAMP, source STRING)
COMMENT 'Cached OneMap locations for HDB residential blocks (written by 08_load_hdb_blocks). Only exact block-number + full-street matches are accepted.'""")

done = spark.sql(f"SELECT blk_no, street FROM {CACHE} WHERE match_status <> 'error'")
todo = (spark.table(BRONZE).where("residential = 'Y'")
        .groupBy("blk_no", "street")
        .agg(F.max(F.coalesce(F.col("1room_rental").cast("int"), F.lit(0)) + F.coalesce(F.col("2room_rental").cast("int"), F.lit(0))).alias("rental"))
        .join(done, ["blk_no", "street"], "left_anti")
        .orderBy(F.col("rental").desc(), "street", "blk_no").select("blk_no", "street").toPandas())
if MAX_BLOCKS:
    todo = todo.head(MAX_BLOCKS)
print(f"Blocks to geocode this run: {len(todo):,}")
spark.sql(f"DELETE FROM {CACHE} WHERE match_status = 'error'")

schema = "blk_no STRING, street STRING, street_full STRING, postal STRING, onemap_address STRING, latitude DOUBLE, longitude DOUBLE, match_status STRING, candidates INT, geocoded_at TIMESTAMP, source STRING"
def geocode(rec):
    try:
        m = match(rec.blk_no.strip(), rec.street.strip())
    except Exception:
        m = {"match_status": "error", "candidates": 0}
    return (rec.blk_no, rec.street, m.get("street_full"), m.get("postal"), m.get("onemap_address"), m.get("latitude"), m.get("longitude"),
            m["match_status"], int(m.get("candidates", 0)), datetime.datetime.now(datetime.timezone.utc), "OneMap search API (SLA)")

recs, started = list(todo.itertuples(index=False)), time.time()
with ThreadPoolExecutor(WORKERS) as pool:
    for b in range(0, len(recs), BATCH):
        rows = list(pool.map(geocode, recs[b:b + BATCH]))
        spark.createDataFrame(rows, schema).write.mode("append").saveAsTable(CACHE)
        print(f"{b + len(rows):,}/{len(recs):,} done ({(time.time() - started) / 60:.1f} min)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Match quality
# MAGIC How many residential blocks were placed, and how many could not be (these are listed in the app so volunteers know they are missing).

# COMMAND ----------

display(spark.sql(f"""SELECT match_status, count(*) AS blocks FROM {CACHE} GROUP BY match_status ORDER BY blocks DESC"""))
