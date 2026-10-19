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
# MAGIC | `app_welfare_residents` | The residents a volunteer team checks on. **Here: fictional demo residents only.** |
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
rows = [(rid, name, blk, street, f"{unit} (demo)", "(demo)", f"+65 0000 {i:04d} (demo)", note, True)
        for i, (rid, name, blk, street, unit, note) in enumerate(demo, start=1)]
spark.sql(f"DELETE FROM {S}.app_welfare_residents WHERE demo = true")
(spark.createDataFrame(rows, "resident_id STRING, name STRING, block STRING, street STRING, unit STRING, postal STRING, phone STRING, notes STRING, demo BOOLEAN")
 .selectExpr("*", "current_timestamp() AS created_at").write.mode("append").saveAsTable(f"{S}.app_welfare_residents"))

if dbutils.widgets.get("reset_events") == "yes":
    spark.sql(f"DELETE FROM {S}.app_welfare_events")

email = dbutils.widgets.get("coordinator_email").strip().lower()
spark.sql(f"DELETE FROM {S}.app_volunteers WHERE lower(email) = '{email}'")
spark.sql(f"INSERT INTO {S}.app_volunteers VALUES ('{email}', 'coordinator', current_timestamp())")
display(spark.sql(f"SELECT resident_id, name, block, street, unit, phone, demo FROM {S}.app_welfare_residents ORDER BY resident_id"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Give the website access
# MAGIC The app's service principal can read residents and volunteers (via the schema-wide SELECT grant) and may **add** events (MODIFY on the
# MAGIC events table only). Run once after creating the app; replace the id if the app is re-created.

# COMMAND ----------

APP_SP = "ed28dd47-4fc7-4926-b5b1-f76c47888390"   # heatguard-web service principal (client id)
spark.sql(f"GRANT MODIFY ON TABLE {S}.app_welfare_events TO `{APP_SP}`")
print("Granted MODIFY on app_welfare_events to the heatguard-web app.")
