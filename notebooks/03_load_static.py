# Databricks notebook source
# MAGIC %md
# MAGIC # 03 · Load the fixed datasets (bronze)
# MAGIC
# MAGIC **What this notebook does:** downloads the datasets that don't change day to day — who lives where (Census 2020), the subzone map, and the
# MAGIC cool spaces seniors can go to — and saves each as a **bronze** table in `workspace.heatguard`.
# MAGIC
# MAGIC | Bronze table | data.gov.sg dataset | Level of detail |
# MAGIC |---|---|---|
# MAGIC | `bronze_census_age` | Census 2020: population by planning area/subzone, age group and sex | subzone |
# MAGIC | `bronze_census_dwelling` | Census 2020: population by planning area/subzone and type of dwelling | subzone |
# MAGIC | `bronze_census_household_size` | Census 2020: resident households by planning area and household size | planning area (30 largest only) |
# MAGIC | `bronze_census_daily_activity` | Census 2020: households with a member who has difficulty with basic activities | planning area (30 largest only) |
# MAGIC | `bronze_subzones` | URA Master Plan 2019 subzone boundaries | 332 subzones |
# MAGIC | `bronze_community_clubs` | People's Association Community Clubs | 125 points |
# MAGIC | `bronze_libraries` | NLB public libraries | 27 points |
# MAGIC
# MAGIC **Bronze** means "as close to the source as possible": Census values stay as text (e.g. `"-"` for zero) and are cleaned in the pipeline's
# MAGIC silver layer, so the original is always available to check against. Safe to re-run: each run replaces these tables.
# MAGIC
# MAGIC **Why these datasets:** Census age and dwelling type are the only open data describing *where vulnerable seniors live* at subzone level.
# MAGIC Community Clubs and libraries are free and air-conditioned, unlike parks and hawker centres, which are outdoors and hot in the afternoon.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Settings
# MAGIC
# MAGIC Each dataset is identified by its data.gov.sg dataset ID. Downloaded files go to `raw/static/` in the volume, so the exact files used are kept.

# COMMAND ----------

import json, re, time, datetime
import requests

CATALOG, SCHEMA = "workspace", "heatguard"
STATIC_DIR = f"/Volumes/{CATALOG}/{SCHEMA}/raw/static"
dbutils.fs.mkdirs(STATIC_DIR)

API_KEY = dbutils.secrets.get(scope="heatguard", key="datagov_api_key")
HEADERS = {"x-api-key": API_KEY}

DATASETS = {
    "census_age":             ("d_d95ae740c0f8961a0b10435836660ce0", "Census 2020: resident population by planning area/subzone, age group and sex"),
    "census_dwelling":        ("d_7f243956483d5901f237e6f87b096636", "Census 2020: resident population by planning area/subzone and type of dwelling"),
    "census_household_size":  ("d_0ef47f84a0776b27010b242038ea2c6b", "Census 2020: resident households by planning area and household size"),
    "census_daily_activity":  ("d_0145fb635a7112d530c4edb0e814b8a9", "Census 2020: resident households by planning area and presence of a member with difficulty in basic activities"),
    "subzones":               ("d_8594ae9ff96d0c708bc2af633048edfb", "URA Master Plan 2019 subzone boundaries"),
    "community_clubs":        ("d_f706de1427279e61fe41e89e24d440fa", "People's Association Community Clubs (locations)"),
    "libraries":              ("d_27b8dae65d9ca1539e14d09578b17cbf", "NLB public libraries (locations)"),
}

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Download the files into the `raw` volume
# MAGIC
# MAGIC data.gov.sg serves dataset files in two steps: the API's `poll-download` call returns a temporary link, and the file itself is downloaded
# MAGIC from that link (Amazon S3). The file extension (`.csv` or `.geojson`) is taken from the link. Rate limits are retried with a growing wait.

# COMMAND ----------

def get_json(url, tries=5):
    """GET with retry on data.gov.sg rate limiting (HTTP 429 or code 24)."""
    for attempt in range(tries):
        r = requests.get(url, headers=HEADERS, timeout=60)
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        if r.status_code == 429 or body.get("code") == 24:
            time.sleep(3 * (attempt + 1))
            continue
        r.raise_for_status()
        return body
    raise RuntimeError(f"Still rate limited after {tries} tries: {url}")

def download(name, dataset_id):
    meta = get_json(f"https://api-open.data.gov.sg/v1/public/api/datasets/{dataset_id}/poll-download")
    url = meta["data"]["url"]
    ext = re.search(r"\.(\w+)\?", url).group(1).lower()
    content = requests.get(url, timeout=120).content
    path = f"{STATIC_DIR}/{name}.{ext}"
    with open(path, "wb") as fh:
        fh.write(content)
    return path

files = {}
for name, (dataset_id, _) in DATASETS.items():
    files[name] = download(name, dataset_id)
    print(f"{name:24} → {files[name]}")
    time.sleep(0.5)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Census tables (CSV → bronze, values kept as text)
# MAGIC
# MAGIC Each Census CSV is saved as-is, with every value as text (`inferSchema = False`), so nothing is silently converted or lost.
# MAGIC Two tracking columns are added to every bronze table: `_source_dataset_id` (which data.gov.sg dataset it came from) and `_loaded_at`
# MAGIC (when). A table comment records the source in Unity Catalog, so anyone browsing the catalog can see where the data came from.
# MAGIC
# MAGIC Note how the Census files are laid out: the first column (`Number`) holds the area name — `"Total"` for Singapore, `"<Planning area> - Total"`
# MAGIC for planning areas, and the subzone name for subzones. The pipeline matches subzone rows to the URA map by name (all 332 match).

# COMMAND ----------

from pyspark.sql import functions as F

LOADED_AT = datetime.datetime.now(datetime.timezone.utc).isoformat()

def save_bronze(df, name, comment):
    table = f"{CATALOG}.{SCHEMA}.bronze_{name}"
    (df.withColumn("_source_dataset_id", F.lit(DATASETS[name][0]))
       .withColumn("_loaded_at", F.lit(LOADED_AT).cast("timestamp"))
       .write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(table))
    spark.sql(f"COMMENT ON TABLE {table} IS '{comment.replace(chr(39), chr(39)*2)} (data.gov.sg {DATASETS[name][0]}). Bronze: raw values as text.'")
    print(f"{table}: {spark.table(table).count():,} rows")

for name in ["census_age", "census_dwelling", "census_household_size", "census_daily_activity"]:
    df = spark.read.option("header", True).option("inferSchema", False).csv(files[name])
    save_bronze(df, name, DATASETS[name][1])

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Map layers (GeoJSON → bronze)
# MAGIC
# MAGIC - **Subzones:** each boundary is kept as GeoJSON text alongside its subzone, planning area and URA region names. The pipeline turns it into a
# MAGIC   geometry with `st_geomfromgeojson` to find each subzone's centre point.
# MAGIC - **Community Clubs and libraries:** the useful details (name, postal code, street) are hidden inside an HTML table in the `Description` field —
# MAGIC   a leftover from the KML format. `html_attributes` unpacks that table into proper columns; the full set of attributes is also kept as JSON.

# COMMAND ----------

def read_geojson(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)["features"]

def html_attributes(description):
    """Turn the KML-style '<th>KEY</th> <td>value</td>' table into a dict."""
    pairs = re.findall(r"<th>(.*?)</th>\s*<td>(.*?)</td>", description or "", flags=re.S)
    return {k.strip(): (v.strip() or None) for k, v in pairs}

# Subzones
rows = []
for f in read_geojson(files["subzones"]):
    p = f["properties"]
    rows.append({
        "subzone_name": p.get("SUBZONE_N"), "subzone_code": p.get("SUBZONE_C"),
        "planning_area": p.get("PLN_AREA_N"), "planning_area_code": p.get("PLN_AREA_C"),
        "region": p.get("REGION_N"), "geometry_geojson": json.dumps(f["geometry"]),
    })
save_bronze(spark.createDataFrame(rows), "subzones", DATASETS["subzones"][1])

# Community Clubs and libraries (points)
def points_table(name):
    out = []
    for f in read_geojson(files[name]):
        attrs = html_attributes(f["properties"].get("Description"))
        lon, lat = f["geometry"]["coordinates"][:2]
        out.append({"name": attrs.get("NAME"), "longitude": float(lon), "latitude": float(lat),
                    "postal_code": attrs.get("ADDRESSPOSTALCODE"),
                    "street": attrs.get("ADDRESSSTREETNAME"),
                    "attributes_json": json.dumps(attrs)})
    return spark.createDataFrame(out)

for name in ["community_clubs", "libraries"]:
    save_bronze(points_table(name), name, DATASETS[name][1])

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Quick check
# MAGIC
# MAGIC Counts per map layer and how many rows have a name. Expected: 332 subzones, 125 Community Clubs and 27 libraries, all named.
# MAGIC Any row without a name would be dropped by the pipeline's `has_name` expectation (and counted there).

# COMMAND ----------

display(spark.sql(f"""
  SELECT 'community_clubs' AS layer, count(*) AS n, count(name) AS with_name FROM {CATALOG}.{SCHEMA}.bronze_community_clubs
  UNION ALL SELECT 'libraries', count(*), count(name) FROM {CATALOG}.{SCHEMA}.bronze_libraries
  UNION ALL SELECT 'subzones', count(*), count(subzone_name) FROM {CATALOG}.{SCHEMA}.bronze_subzones
"""))
display(spark.table(f"{CATALOG}.{SCHEMA}.bronze_community_clubs").limit(5))
