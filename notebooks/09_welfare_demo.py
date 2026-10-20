# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "6"
# ///
# MAGIC %md
# MAGIC # 09 · Welfare checklist: tables and DEMO residents
# MAGIC
# MAGIC **What this sets up** for the website's *Welfare checks* page:
# MAGIC
# MAGIC | Table | What it holds |
# MAGIC |---|---|
# MAGIC | `app_welfare_residents` | The residents a volunteer team checks on, with the area (URA subzone) their block is in. **Here: fictional demo residents only.** |
# MAGIC | `app_welfare_events` | Every change, appended and never overwritten (completed, unchecked, unsuccessful attempt, remark, follow-up on/off) — the audit trail |
# MAGIC | `app_volunteers` | Who may open welfare checks (`volunteer` or `coordinator`) — checked on every request by the app |
# MAGIC
# MAGIC **Privacy:** the DAISI rules forbid personal data, and real resident details would need proper consent, access control and security
# MAGIC review. So this notebook creates **clearly labelled, made-up residents** ("Demo Resident A", phone numbers starting `+65 0000`, which
# MAGIC are not valid Singapore numbers). It is a **prototype**: before real use, resident data would come from the AAC's own system, with
# MAGIC row-level access per centre.
# MAGIC
# MAGIC Safe to re-run: tables are created if missing; demo residents are replaced; **events are never deleted** unless `reset_events` = yes.

# COMMAND ----------

dbutils.widgets.dropdown("reset_events", "no", ["no", "yes"], "Delete all welfare events (demo reset)")
dbutils.widgets.text("coordinator_email", "yubrajb2907@gmail.com", "Coordinator email to allow")
S = "workspace.heatguard"

spark.sql(f"""CREATE TABLE IF NOT EXISTS {S}.app_welfare_residents (
  resident_id STRING, name STRING, block STRING, street STRING, unit STRING, postal STRING, phone STRING, notes STRING, demo BOOLEAN, created_at TIMESTAMP)
COMMENT 'Residents for the welfare checklist. DEMO: all rows are fictional.'""")
spark.sql(f"""CREATE TABLE IF NOT EXISTS {S}.app_welfare_events (
  event_id STRING, client_event_id STRING, resident_id STRING, action STRING, outcome STRING, remark STRING, by_email STRING, at TIMESTAMP)
COMMENT 'Append-only history of welfare-check actions (audit trail). Never updated in place.'""")
spark.sql(f"""CREATE TABLE IF NOT EXISTS {S}.app_volunteers (email STRING, role STRING, added_at TIMESTAMP)
COMMENT 'Who may open welfare checks in the HeatGuard website (role: volunteer or coordinator).'""")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Demo residents (fictional)
# MAGIC Placed at HDB blocks around Telok Blangah so the demo matches the example centre (Radin Mas CC). Unit numbers, names and phone
# MAGIC numbers are invented and marked as demo.

# COMMAND ----------

demo = [
    ("demo-01", "Demo Resident A", "51", "Telok Blangah Crescent", "#03-101", "Lives alone; uses a walking stick"),
    ("demo-02", "Demo Resident B", "51", "Telok Blangah Crescent", "#07-114", "Heart condition"),
    ("demo-03", "Demo Resident C", "52", "Telok Blangah Crescent", "#02-121", ""),
    ("demo-04", "Demo Resident D", "52", "Telok Blangah Crescent", "#10-133", "Prefers phone calls in Mandarin"),
    ("demo-05", "Demo Resident E", "55", "Telok Blangah Drive", "#04-205", "Lives alone"),
    ("demo-06", "Demo Resident F", "55", "Telok Blangah Drive", "#11-219", ""),
    ("demo-07", "Demo Resident G", "56", "Telok Blangah Drive", "#05-301", "Lung condition; keeps inhaler at home"),
    ("demo-08", "Demo Resident H", "57", "Telok Blangah Drive", "#08-322", ""),
    ("demo-09", "Demo Resident I", "59", "Telok Blangah Way", "#06-410", "Lives alone; hard of hearing — knock loudly"),
    ("demo-10", "Demo Resident J", "60", "Telok Blangah Way", "#09-418", ""),
    ("demo-11", "Demo Resident K", "61", "Telok Blangah Way", "#12-427", "Prefers Malay"),
    ("demo-12", "Demo Resident L", "62", "Telok Blangah Way", "#01-431", "Daughter visits on weekends"),
]
import time

import requests

def block_location(blk, street):
    """OneMap location of an HDB block (exact block number + street only), used to find the resident's area. Not stored."""
    for attempt in range(5):                         # OneMap answers "429 too many requests" to quick bursts: wait and retry
        time.sleep(1.5 * (attempt + 1))
        r = requests.get("https://www.onemap.gov.sg/api/common/elastic/search",
                         params={"searchVal": f"{blk} {street}", "returnGeom": "Y", "getAddrDetails": "Y", "pageNum": 1}, timeout=20)
        if r.status_code == 200:
            res = r.json(); break
    else:
        return (None, None)
    hits = [h for h in res.get("results", []) if h.get("BLK_NO") == blk and h.get("ROAD_NAME", "").upper() == street.upper()]
    return (float(hits[0]["LATITUDE"]), float(hits[0]["LONGITUDE"])) if hits else (None, None)

rows = [(rid, name, blk, street, f"{unit} (demo)", "(demo)", f"+65 0000 {i:04d} (demo)", note, True, *block_location(blk, street))
        for i, (rid, name, blk, street, unit, note) in enumerate(demo, start=1)]
cols = "resident_id STRING, name STRING, block STRING, street STRING, unit STRING, postal STRING, phone STRING, notes STRING, demo BOOLEAN, lat DOUBLE, lon DOUBLE"
spark.createDataFrame(rows, cols).createOrReplaceTempView("demo_residents")
# The URA subzone that contains each block, so each area page can show the seniors who live there (coordinates are dropped)
placed = spark.sql(f"""SELECT d.* EXCEPT (lat, lon), s.subzone_name FROM demo_residents d
                       LEFT JOIN {S}.silver_subzones s ON d.lat IS NOT NULL AND st_contains(st_geomfromgeojson(s.geometry_geojson), st_point(d.lon, d.lat, 4326))""")

if "subzone_name" not in spark.table(f"{S}.app_welfare_residents").columns:
    spark.sql(f"ALTER TABLE {S}.app_welfare_residents ADD COLUMNS (subzone_name STRING COMMENT 'URA subzone the block is in (from its OneMap location)')")
spark.sql(f"DELETE FROM {S}.app_welfare_residents WHERE demo = true")
placed.selectExpr("*", "current_timestamp() AS created_at").write.mode("append").option("mergeSchema", "true").saveAsTable(f"{S}.app_welfare_residents")

if dbutils.widgets.get("reset_events") == "yes":
    spark.sql(f"DELETE FROM {S}.app_welfare_events")

email = dbutils.widgets.get("coordinator_email").strip().lower()
spark.sql(f"DELETE FROM {S}.app_volunteers WHERE lower(email) = '{email}'")
spark.sql(f"INSERT INTO {S}.app_volunteers VALUES ('{email}', 'coordinator', current_timestamp())")
display(spark.sql(f"SELECT resident_id, name, block, street, unit, subzone_name, demo FROM {S}.app_welfare_residents ORDER BY resident_id"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Give the website access
# MAGIC The app's service principal can read residents and volunteers (via the schema-wide SELECT grant) and may **add** events (MODIFY on the
# MAGIC events table only). Run once after creating the app; replace the id if the app is re-created.

# COMMAND ----------

APP_SP = "ed28dd47-4fc7-4926-b5b1-f76c47888390"   # heatguard-web service principal (client id)
spark.sql(f"GRANT MODIFY ON TABLE {S}.app_welfare_events TO `{APP_SP}`")
print("Granted MODIFY on app_welfare_events to the heatguard-web app.")
