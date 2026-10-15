# Databricks notebook source
# MAGIC %md
# MAGIC # 04 · HeatGuard pipeline (Lakeflow Declarative Pipeline)
# MAGIC
# MAGIC **What this notebook is:** the source code of the **`heatguard-pipeline`** pipeline. It is not run cell by cell. Instead, the pipeline
# MAGIC (Jobs & Pipelines → `heatguard-pipeline`) reads the whole notebook, works out which table depends on which, and builds them in the right order.
# MAGIC
# MAGIC **Why a declarative pipeline:** we only describe *what* each table should contain. Databricks takes care of the order,
# MAGIC incremental loading of new files, retries, and — most importantly for us — **data-quality expectations** (rules that drop
# MAGIC or flag bad rows and count them) and **lineage** (a diagram showing how every number on the check-in list traces back to NEA and Census data).
# MAGIC
# MAGIC ### The medallion layers
# MAGIC
# MAGIC | Layer | Purpose | Tables |
# MAGIC |---|---|---|
# MAGIC | **Bronze** | Exactly what the APIs sent, so we can always re-process from the source | `bronze_wbgt`, `bronze_forecast_24h`, `bronze_psi`, `bronze_pm25`, `bronze_air_temperature`, `bronze_humidity` (plus the Census, map and cool-space bronze tables written by `03_load_static`) |
# MAGIC | **Silver** | Clean, typed, de-duplicated: one row per reading or place. Bad rows are dropped here and counted | `silver_wbgt`, `silver_wbgt_stations`, `silver_wbgt_daily_peak`, `silver_psi`, `silver_pm25`, `silver_haze_regions`, `silver_forecast_24h`, `silver_forecast_periods`, `silver_air_temperature`, `silver_humidity`, `silver_subzones`, `silver_cool_spaces`, `silver_census_subzone`, `silver_census_planning_area` |
# MAGIC | **Gold** | Business-ready tables the app, Genie and the model use | `gold_forecast_features`, `gold_subzone_station_weights`, `gold_subzone_profile`, `gold_subzone_conditions`, `gold_checkin_list`, `gold_day_outlook`, `gold_replay_list`, `gold_replay_summary`, `gold_wbgt_station_latest`, `gold_haze_latest`, `gold_daily_summary`, `gold_score_weights`, `gold_rulebook` |
# MAGIC
# MAGIC ### How the pieces fit together
# MAGIC 1. `02_backfill` and `01_ingest_live` drop JSON files into the `raw` volume → **bronze**.
# MAGIC 2. **Silver** cleans them. **`gold_forecast_features`** turns the clean data into one row per station per day for the model.
# MAGIC 3. `05_forecast_model` trains the model; `06_score_forecast` writes tomorrow's forecast to `ml_wbgt_forecast`.
# MAGIC 4. The next pipeline run blends that forecast into each subzone and produces **`gold_checkin_list`** (areas in priority tiers: Act / Check in / Routine)
# MAGIC    and **`gold_day_outlook`** (one headline for the day). **`gold_replay_*`** run the same logic on past test days to show what HeatGuard would have said.
# MAGIC
# MAGIC If no forecast exists yet, the list falls back to the latest **observed** afternoon peak and says so in the `heat_basis` column.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Settings and helper functions
# MAGIC
# MAGIC All the numbers that shape the results live here, in one place, so they are easy to find, explain and change:
# MAGIC
# MAGIC - **Heat-stress bands**: NEA's own WBGT cut-offs (Low < 31 °C, Moderate 31–32.9 °C, High ≥ 33 °C). We measured these from the data on 11 Oct and they match NEA's labels on every reading.
# MAGIC - **PSI bands**: NEA's haze bands (Good ≤ 50, Moderate ≤ 100, Unhealthy ≤ 200, Very unhealthy ≤ 300, Hazardous above).
# MAGIC - **Afternoon window (12:00–17:59)**: heat stress peaks in the afternoon, and this is when seniors are most at risk outdoors. "Afternoon peak" is the value we forecast.
# MAGIC - **Risk score weights**: how much heat, haze, vulnerability and distance to a cool space each count. These are published to the `gold_score_weights` table so the app can show them; nothing is hidden.
# MAGIC
# MAGIC The helper functions convert timestamps to Singapore time, assign bands, and measure distances on the earth's surface (`st_distancesphere`).

# COMMAND ----------

import dlt
from pyspark.sql import functions as F, Window as W

CATALOG, SCHEMA = "workspace", "heatguard"
RAW = f"/Volumes/{CATALOG}/{SCHEMA}/raw"
ML_FORECAST_TABLE = f"{CATALOG}.{SCHEMA}.ml_wbgt_forecast"   # written by 06_score_forecast

def static(name):
    """Tables written by 03_load_static (not managed by this pipeline)."""
    return spark.read.table(f"{CATALOG}.{SCHEMA}.{name}")

# NEA heat-stress bands (WBGT, °C), measured from the data on 11 Oct: Low < 31, Moderate 31–32.9, High ≥ 33
WBGT_MODERATE, WBGT_HIGH = 31.0, 33.0
# NEA PSI bands (24-hour PSI)
PSI_BANDS = [(50, "Good"), (100, "Moderate"), (200, "Unhealthy"), (300, "Very unhealthy")]

AFTERNOON_HOURS = (12, 17)       # 12:00–17:59 SGT: when heat stress peaks and outreach matters
MIN_AFTERNOON_READINGS = 12      # of 24 possible 15-minute readings; fewer and the day's peak is unreliable
NEAREST_STATIONS = 3             # stations blended per subzone (inverse-distance weighting)
ACTIVE_STATION_DAYS = 7          # a station counts as active if it reported in the last 7 days of data
MIN_SENIORS = 50                 # subzones with fewer residents aged 65+ are left out of the ranking
FAR_FROM_COOL_SPACE_KM = 2.0     # at or beyond this distance, the access score is at its maximum
FORECAST_CUTOFF_SGT = "18:30"    # the model only uses NEA forecasts issued by 6:30 pm the day before (when we publish)
RAIN_PATTERN = "(?i)shower|rain|thunder|drizzle"

# Risk = 100 × hazard × exposure (both 0–1).
#   hazard   = how dangerous the day is: 0.5 × P(peak ≥ 31 °C) + 0.5 × min(1, P(peak ≥ 33 °C) / 0.5), plus up to 0.3 for haze
#   exposure = who would be affected: 0.7 × vulnerability score + 0.3 × distance to the nearest cool space
# Multiplying means a cool day scores low everywhere, and the same area moves up the list on a hot day.
P_HIGH_FULL = 0.5                 # a 50% chance of High heat counts as the full High-heat part of the hazard
HAZE_IN_HAZARD = 0.3              # haze adds up to 0.3 to the hazard (nothing at PSI 50, full at PSI 200)
OBSERVED_HAZARD = {"High": 0.9, "Moderate": 0.45, "Low": 0.15}   # heat hazard used only when no forecast exists
EXPOSURE_WEIGHTS = {"vulnerability": 0.7, "access": 0.3}
CHECKIN_EXPOSURE_PCTL = 0.75      # 'Check in' = Moderate heat in the top quarter of areas by exposure
TIERS = {"Act": 1, "Check in": 2, "Routine": 3}

SCORE_WEIGHTS = [   # published to gold_score_weights for the app and Genie
    ("hazard", "p_moderate_plus", 0.5, "Chance tomorrow's afternoon peak reaches Moderate heat stress (WBGT 31 °C or more), from the forecast model"),
    ("hazard", "p_high", 0.5, "Chance it reaches High heat stress (WBGT 33 °C or more); a 50% chance or more counts in full"),
    ("hazard", "haze", HAZE_IN_HAZARD, "Haze adds to the danger: nothing at PSI 50 (Good), the full 0.3 at PSI 200 (Very unhealthy)"),
    ("exposure", "vulnerability", EXPOSURE_WEIGHTS["vulnerability"], "Census vulnerability score of the area (seniors, small flats, living alone, daily-activity difficulty)"),
    ("exposure", "access", EXPOSURE_WEIGHTS["access"], f"Distance to the nearest Community Club or library: nothing at the door, full at {FAR_FROM_COOL_SPACE_KM:g} km or more"),
]
# Vulnerability = weighted sum of percentile ranks among in-scope subzones
VULNERABILITY_WEIGHTS = {
    "pct_65_plus":       (0.30, "Share of residents aged 65+ (subzone)"),
    "pop_65_plus":       (0.20, "Number of residents aged 65+ (subzone)"),
    "pct_1_2_room":      (0.20, "Share of residents in 1–2 room HDB flats (subzone)"),
    "pa_pct_one_person": (0.15, "Share of one-person households (planning area; national rate where not published)"),
    "pa_pct_difficulty": (0.15, "Share of households with a member who has difficulty with daily activities (planning area; national rate where not published)"),
}

def local_parts(iso_col):
    """Source timestamps are ISO strings in SGT (+08:00): take the local date/hour straight from the text."""
    c = F.col(iso_col)
    return {
        "reading_ts": c.cast("timestamp"),
        "date_sgt": F.to_date(F.substring(c, 1, 10)),
        "hour_sgt": F.substring(c, 12, 2).cast("int"),
        "time_sgt": F.substring(c, 12, 5),
    }

def wbgt_band(col):
    return (F.when(col >= WBGT_HIGH, "High").when(col >= WBGT_MODERATE, "Moderate")
             .when(col.isNotNull(), "Low"))

def psi_band(col):
    expr = F.when(col.isNull(), None)
    for upper, label in PSI_BANDS:
        expr = expr.when(col <= upper, label)
    return expr.otherwise("Hazardous")

def clamp01(col):
    return F.greatest(F.lit(0.0), F.least(F.lit(1.0), col))

def distance_km(lon1, lat1, lon2, lat2):
    return F.expr(f"st_distancesphere(st_point({lon1}, {lat1}), st_point({lon2}, {lat2})) / 1000")

def nearest_region(df, lon_col, lat_col):
    """Name of the nearest NEA region (north/south/east/west/central label point) for each row."""
    regions = spark.read.table("silver_haze_regions").select(
        F.col("region").alias("_region"), F.col("latitude").alias("_r_lat"), F.col("longitude").alias("_r_lon"))
    key = [c for c in df.columns]
    return (df.crossJoin(regions)
            .withColumn("_d", distance_km(lon_col, lat_col, "_r_lon", "_r_lat"))
            .groupBy(*key).agg(F.min_by("_region", "_d").alias("region")))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Bronze: raw files → streaming tables
# MAGIC
# MAGIC **What it does:** Auto Loader watches each folder in the `raw` volume and loads every new `.jsonl` file exactly once.
# MAGIC Backfill files (`history_*.jsonl`) and live files (`live_*.jsonl`) land in the same table.
# MAGIC
# MAGIC **Why explicit schemas:** history and live files carry slightly different extra fields (`fetched_for_date` vs `fetched_at`), and some
# MAGIC numbers arrive as text (e.g. WBGT `"NA"`). Declaring the schema up front keeps both kinds of file in one table and stops a single
# MAGIC odd file from breaking the load. Numbers stay as text here; they are converted (and checked) in silver.
# MAGIC
# MAGIC Every row also records which file it came from (`_file`) and when it was loaded (`_ingested_at`), so any value can be traced back to its source file.

# COMMAND ----------

SCHEMAS = {
    "wbgt": """source STRING, fetched_at STRING, fetched_for_date STRING, datetime STRING,
        item STRUCT<type: STRING, isStationData: BOOLEAN, readings: ARRAY<STRUCT<
            station: STRUCT<id: STRING, name: STRING, townCenter: STRING>,
            location: STRUCT<latitude: STRING, longitude: STRING>, wbgt: STRING, heatStress: STRING>>>""",
    "forecast_24h": """source STRING, fetched_at STRING, fetched_for_date STRING, date STRING, updatedTimestamp STRING, timestamp STRING,
        general STRUCT<forecast: STRUCT<code: STRING, text: STRING>,
            relativeHumidity: STRUCT<high: STRING, low: STRING>, temperature: STRUCT<high: STRING, low: STRING>,
            validPeriod: STRUCT<start: STRING, `end`: STRING, text: STRING>,
            wind: STRUCT<direction: STRING, speed: STRUCT<high: STRING, low: STRING>>>,
        periods ARRAY<STRUCT<timePeriod: STRUCT<start: STRING, `end`: STRING, text: STRING>,
            regions: MAP<STRING, STRUCT<code: STRING, text: STRING>>>>""",
    "psi": """source STRING, fetched_at STRING, fetched_for_date STRING, date STRING, updatedTimestamp STRING, timestamp STRING,
        regionMetadata ARRAY<STRUCT<name: STRING, labelLocation: STRUCT<latitude: STRING, longitude: STRING>>>,
        readings MAP<STRING, MAP<STRING, STRING>>""",
    "station_series": """source STRING, fetched_at STRING, readingType STRING, readingUnit STRING, timestamp STRING,
        stations ARRAY<STRUCT<id: STRING, deviceId: STRING, name: STRING, location: STRUCT<latitude: STRING, longitude: STRING>>>,
        data ARRAY<STRUCT<stationId: STRING, value: STRING>>""",
}

def raw_stream(folder, schema):
    return (spark.readStream.format("cloudFiles")
            .option("cloudFiles.format", "json")
            .option("pathGlobFilter", "*.jsonl")
            .schema(SCHEMAS[schema])
            .load(f"{RAW}/{folder}/")
            .withColumn("_file", F.col("_metadata.file_path"))
            .withColumn("_ingested_at", F.current_timestamp()))

def bronze(folder, schema, comment):
    @dlt.table(name=f"bronze_{folder}", comment=comment)
    def _t():
        return raw_stream(folder, schema)

bronze("wbgt", "wbgt", "NEA Wet Bulb Globe Temperature: one row per 15-minute record with all station readings (data.gov.sg real-time API). Bronze: as received.")
bronze("forecast_24h", "forecast_24h", "NEA 24-hour forecast: one row per issued forecast (data.gov.sg real-time API). Bronze: as received.")
bronze("psi", "psi", "NEA Pollutant Standards Index (haze): one row per hour with all measures for 5 regions (data.gov.sg real-time API). Bronze: as received.")
bronze("pm25", "psi", "NEA PM2.5 (haze): one row per hour for 5 regions (data.gov.sg real-time API). Bronze: as received.")
bronze("air_temperature", "station_series", "NEA air temperature: one row per timestamp with all station values (data.gov.sg real-time API). Bronze: as received.")
bronze("humidity", "station_series", "NEA relative humidity: one row per timestamp with all station values (data.gov.sg real-time API). Bronze: as received.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Silver: WBGT readings (the main heat signal)
# MAGIC
# MAGIC **What it does:** each bronze row holds one 15-minute snapshot with ~30 stations inside it. We "explode" it into **one row per station per 15 minutes**,
# MAGIC convert text to numbers, attach Singapore date and hour, and remove duplicates (the same reading can arrive from both the backfill and the live job).
# MAGIC
# MAGIC **Data-quality expectations** (results visible on the pipeline graph):
# MAGIC | Rule | Action | Why |
# MAGIC |---|---|---|
# MAGIC | `has_station` | drop | A reading we can't place on the map is useless |
# MAGIC | `numeric_reading` | drop | NEA sends `"NA"` when a sensor is down (~2,900 readings, 0.3%) |
# MAGIC | `plausible_range` (20–40 °C) | drop | Singapore WBGT never realistically goes below 20 °C; 74 readings as low as 14.3 °C are sensor faults |
# MAGIC | `matches_nea_band` | flag only | Checks that our band cut-offs agree with NEA's own label. They agree on every row, which confirms the cut-offs |

# COMMAND ----------

@dlt.table(comment="WBGT heat stress: one row per station per 15 minutes, de-duplicated across backfill and live files. "
                   "Bands: Low < 31 °C, Moderate 31–32.9 °C, High ≥ 33 °C (NEA).")
@dlt.expect_or_drop("has_station", "station_id IS NOT NULL")
@dlt.expect_or_drop("numeric_reading", "wbgt_c IS NOT NULL")
@dlt.expect_or_drop("plausible_range", "wbgt_c IS NULL OR wbgt_c BETWEEN 20 AND 40")
@dlt.expect("matches_nea_band", "heat_stress_nea IS NULL OR heat_stress_nea = heat_band")
def silver_wbgt():
    r = (spark.read.table("bronze_wbgt")
         .select("datetime", "source", F.explode("item.readings").alias("r")))
    t = local_parts("datetime")
    out = r.select(
        F.col("r.station.id").alias("station_id"),
        F.col("r.station.name").alias("station_name"),
        F.col("r.station.townCenter").alias("town_center"),
        F.expr("try_cast(r.location.latitude AS DOUBLE)").alias("latitude"),
        F.expr("try_cast(r.location.longitude AS DOUBLE)").alias("longitude"),
        *[v.alias(k) for k, v in t.items()],
        F.expr("try_cast(r.wbgt AS DOUBLE)").alias("wbgt_c"),
        F.when(F.col("r.heatStress") != "NA", F.col("r.heatStress")).alias("heat_stress_nea"),
        "source",
    )
    return (out.dropDuplicates(["station_id", "reading_ts"])
               .withColumn("heat_band", wbgt_band(F.col("wbgt_c"))))

# COMMAND ----------

# MAGIC %md
# MAGIC ### WBGT stations and daily afternoon peaks
# MAGIC
# MAGIC **`silver_wbgt_stations`** — one row per station with its latest location and when it last reported. The network grew from 8 stations
# MAGIC (Jan 2025) to 30 (Aug 2026), and stations occasionally go offline, so a station is **active** only if it reported in the last 7 days of data.
# MAGIC Only active stations are used to estimate heat for subzones.
# MAGIC
# MAGIC **`silver_wbgt_daily_peak`** — one row per station per day with the **highest WBGT between 12:00 and 17:59**. This is the number the
# MAGIC forecast model predicts for tomorrow, because it captures the worst heat seniors face on a given day. A day needs at least
# MAGIC 12 of the 24 possible afternoon readings for its peak to be trusted; days with fewer are flagged by the `enough_afternoon_readings` expectation.

# COMMAND ----------

@dlt.table(comment="WBGT stations: latest known location, first/last reading, and whether the station is active (reported in the last 7 days of data).")
def silver_wbgt_stations():
    latest = (spark.read.table("silver_wbgt")
              .groupBy("station_id")
              .agg(F.max_by("station_name", "reading_ts").alias("station_name"),
                   F.max_by("town_center", "reading_ts").alias("town_center"),
                   F.max_by("latitude", "reading_ts").alias("latitude"),
                   F.max_by("longitude", "reading_ts").alias("longitude"),
                   F.min("reading_ts").alias("first_reading_ts"),
                   F.max("reading_ts").alias("last_reading_ts"),
                   F.count("*").alias("readings")))
    newest = latest.agg(F.max("last_reading_ts").alias("newest"))
    return (latest.crossJoin(newest)
            .withColumn("is_active", F.col("last_reading_ts") >= F.col("newest") - F.expr(f"INTERVAL {ACTIVE_STATION_DAYS} DAYS"))
            .drop("newest"))

@dlt.table(comment="Daily afternoon (12:00–17:59 SGT) peak WBGT per station: the value the forecast model predicts for tomorrow.")
@dlt.expect("enough_afternoon_readings", f"afternoon_readings >= {MIN_AFTERNOON_READINGS}")
def silver_wbgt_daily_peak():
    a, b = AFTERNOON_HOURS
    return (spark.read.table("silver_wbgt")
            .groupBy("station_id", "date_sgt")
            .agg(F.max(F.when(F.col("hour_sgt").between(a, b), F.col("wbgt_c"))).alias("afternoon_peak_wbgt_c"),
                 F.count(F.when(F.col("hour_sgt").between(a, b), True)).alias("afternoon_readings"),
                 F.max("wbgt_c").alias("daily_max_wbgt_c"),
                 F.count("*").alias("readings"))
            .withColumn("afternoon_peak_band", wbgt_band(F.col("afternoon_peak_wbgt_c"))))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Silver: haze (PSI and PM2.5)
# MAGIC
# MAGIC **What it does:** NEA publishes haze for 5 regions (north, south, east, west, central) every hour. Each bronze row stores
# MAGIC *measure → region → value*. We reshape it into **one row per region per hour** with one column per measure
# MAGIC (24-hour PSI, 24-hour PM2.5, PM10, ozone, and so on) and attach NEA's PSI band.
# MAGIC
# MAGIC **Expectations:** PSI and PM2.5 must be present and inside the physically possible range (PSI 0–500), otherwise the row is dropped.
# MAGIC
# MAGIC **`silver_haze_regions`** keeps the 5 regions' label locations. We use them to assign every subzone and weather station to its nearest region,
# MAGIC because haze is only published at that level — we deliberately don't pretend to finer detail.

# COMMAND ----------

PSI_MEASURES = ["psi_twenty_four_hourly", "pm25_twenty_four_hourly", "pm10_twenty_four_hourly",
                "pm25_sub_index", "pm10_sub_index", "o3_sub_index", "so2_sub_index", "co_sub_index",
                "o3_eight_hour_max", "no2_one_hour_max", "so2_twenty_four_hourly", "co_eight_hour_max"]

def region_hourly(table, measures):
    """Bronze haze rows (measure → region → value) to one row per region per hour, one column per measure."""
    long = (spark.read.table(table)
            .select("timestamp", F.explode("readings").alias("measure", "by_region"))
            .select("timestamp", "measure", F.explode("by_region").alias("region", "value"))
            .withColumn("value", F.expr("try_cast(value AS DOUBLE)")))
    t = local_parts("timestamp")
    # Conditional aggregation instead of pivot (pivot is not supported in declarative pipelines)
    return (long.groupBy("timestamp", "region")
            .agg(*[F.max(F.when(F.col("measure") == m, F.col("value"))).alias(m) for m in measures])
            .select("region", *[v.alias(k) for k, v in t.items()], *measures))

@dlt.table(comment="Haze: hourly Pollutant Standards Index and pollutant measures for NEA's 5 regions. PSI bands: Good ≤ 50, Moderate ≤ 100, Unhealthy ≤ 200, Very unhealthy ≤ 300, Hazardous > 300.")
@dlt.expect_or_drop("has_psi", "psi_twenty_four_hourly IS NOT NULL")
@dlt.expect_or_drop("plausible_psi", "psi_twenty_four_hourly BETWEEN 0 AND 500")
def silver_psi():
    return (region_hourly("bronze_psi", PSI_MEASURES)
            .withColumn("psi_band", psi_band(F.col("psi_twenty_four_hourly"))))

@dlt.table(comment="Haze: hourly PM2.5 (µg/m³, 1-hour) for NEA's 5 regions.")
@dlt.expect_or_drop("has_pm25", "pm25_one_hourly IS NOT NULL")
@dlt.expect_or_drop("plausible_pm25", "pm25_one_hourly BETWEEN 0 AND 1000")
def silver_pm25():
    return region_hourly("bronze_pm25", ["pm25_one_hourly"])

@dlt.table(comment="NEA's 5 haze regions (north, south, east, west, central) with their label locations.")
def silver_haze_regions():
    return (spark.read.table("bronze_psi")
            .select(F.explode("regionMetadata").alias("m"))
            .select(F.col("m.name").alias("region"),
                    F.expr("try_cast(m.labelLocation.latitude AS DOUBLE)").alias("latitude"),
                    F.expr("try_cast(m.labelLocation.longitude AS DOUBLE)").alias("longitude"))
            .dropDuplicates(["region"]))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Silver: NEA 24-hour forecasts
# MAGIC
# MAGIC **What it does:** NEA issues its 24-hour forecast several times a day (most often around 5 am, 11 am, 5:30 pm and 11:30 pm).
# MAGIC We keep two views of it:
# MAGIC - **`silver_forecast_24h`** — one row per issued forecast with the island-wide numbers: temperature range, humidity range, wind and an overall outlook.
# MAGIC - **`silver_forecast_periods`** — one row per issue × time period (about 6 hours each) × region, with the outlook text (e.g. "Thundery Showers").
# MAGIC
# MAGIC **Why we keep the issue time in Singapore time:** the model must only use forecasts that existed *before* we publish tomorrow's list
# MAGIC (6:30 pm). Using a forecast issued later would be "peeking at the future" and make the model look better than it really is.

# COMMAND ----------

@dlt.table(comment="NEA 24-hour forecast: one row per issued forecast (temperature, humidity, wind and outlook for the whole island).")
@dlt.expect_or_drop("has_valid_period", "valid_start_ts IS NOT NULL")
def silver_forecast_24h():
    return (spark.read.table("bronze_forecast_24h")
            .withColumn("_issued", F.coalesce("timestamp", "updatedTimestamp"))
            .select(F.col("_issued").cast("timestamp").alias("issued_ts"),
                    F.to_date(F.substring("_issued", 1, 10)).alias("issued_date_sgt"),
                    F.substring("_issued", 12, 5).alias("issued_time_sgt"),
                    F.col("updatedTimestamp").cast("timestamp").alias("updated_ts"),
                    F.col("general.validPeriod.start").cast("timestamp").alias("valid_start_ts"),
                    F.col("general.validPeriod.end").cast("timestamp").alias("valid_end_ts"),
                    F.col("general.validPeriod.text").alias("valid_period_text"),
                    F.expr("try_cast(general.temperature.low AS INT)").alias("temp_low_c"),
                    F.expr("try_cast(general.temperature.high AS INT)").alias("temp_high_c"),
                    F.expr("try_cast(general.relativeHumidity.low AS INT)").alias("rh_low_pct"),
                    F.expr("try_cast(general.relativeHumidity.high AS INT)").alias("rh_high_pct"),
                    F.col("general.wind.direction").alias("wind_direction"),
                    F.expr("try_cast(general.wind.speed.low AS INT)").alias("wind_speed_low_kmh"),
                    F.expr("try_cast(general.wind.speed.high AS INT)").alias("wind_speed_high_kmh"),
                    F.col("general.forecast.code").alias("forecast_code"),
                    F.col("general.forecast.text").alias("forecast_text"))
            .dropDuplicates(["issued_ts", "valid_start_ts"]))

@dlt.table(comment="NEA 24-hour forecast by period (about 6 hours) and region: outlook code and text, with the issue and period times in Singapore time.")
def silver_forecast_periods():
    return (spark.read.table("bronze_forecast_24h")
            .withColumn("_issued", F.coalesce("timestamp", "updatedTimestamp"))
            .select(F.col("_issued").cast("timestamp").alias("issued_ts"),
                    F.to_date(F.substring("_issued", 1, 10)).alias("issued_date_sgt"),
                    F.substring("_issued", 12, 5).alias("issued_time_sgt"),
                    F.explode("periods").alias("p"))
            .select("issued_ts", "issued_date_sgt", "issued_time_sgt",
                    F.col("p.timePeriod.start").cast("timestamp").alias("period_start_ts"),
                    F.to_date(F.substring("p.timePeriod.start", 1, 10)).alias("period_date_sgt"),
                    F.substring("p.timePeriod.start", 12, 2).cast("int").alias("period_start_hour_sgt"),
                    F.col("p.timePeriod.end").cast("timestamp").alias("period_end_ts"),
                    F.col("p.timePeriod.text").alias("period_text"),
                    F.explode("p.regions").alias("region", "o"))
            .select("issued_ts", "issued_date_sgt", "issued_time_sgt", "period_start_ts", "period_date_sgt",
                    "period_start_hour_sgt", "period_end_ts", "period_text", "region",
                    F.col("o.code").alias("forecast_code"), F.col("o.text").alias("forecast_text"))
            .dropDuplicates(["issued_ts", "period_start_ts", "region"]))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Silver: air temperature and humidity
# MAGIC
# MAGIC **What it does:** one row per station per reading, with the station's name and location attached. These come only from the live job
# MAGIC (we decided on 11 Oct not to backfill them, to save quota), so they are used for context in the app rather than by the model.
# MAGIC Readings outside physically possible ranges (15–45 °C, 0–100 %) are dropped.

# COMMAND ----------

def station_series(table):
    rows = spark.read.table(table)
    stations = (rows.select(F.explode("stations").alias("s"))
                .select(F.col("s.id").alias("station_id"), F.col("s.name").alias("station_name"),
                        F.expr("try_cast(s.location.latitude AS DOUBLE)").alias("latitude"),
                        F.expr("try_cast(s.location.longitude AS DOUBLE)").alias("longitude"))
                .dropDuplicates(["station_id"]))
    t = local_parts("timestamp")
    values = (rows.select("timestamp", F.explode("data").alias("d"))
              .select(F.col("d.stationId").alias("station_id"), *[v.alias(k) for k, v in t.items()],
                      F.expr("try_cast(d.value AS DOUBLE)").alias("value"))
              .dropDuplicates(["station_id", "reading_ts"]))
    return values.join(stations, "station_id", "left")

@dlt.table(comment="Air temperature (°C): one row per station per reading collected by the live job.")
@dlt.expect_or_drop("plausible_temperature", "air_temp_c BETWEEN 15 AND 45")
def silver_air_temperature():
    return station_series("bronze_air_temperature").withColumnRenamed("value", "air_temp_c")

@dlt.table(comment="Relative humidity (%): one row per station per reading collected by the live job.")
@dlt.expect_or_drop("plausible_humidity", "humidity_pct BETWEEN 0 AND 100")
def silver_humidity():
    return station_series("bronze_humidity").withColumnRenamed("value", "humidity_pct")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Silver: places and people
# MAGIC
# MAGIC **`silver_subzones`** — the 332 URA subzones with their planning area, URA region and **centre point** (centroid of the boundary).
# MAGIC Distances to stations and cool spaces are measured from this point. The pipeline *fails* if any subzone has no centre point,
# MAGIC because every later step depends on it.
# MAGIC
# MAGIC **`silver_cool_spaces`** — the 125 Community Clubs and 27 public libraries in one table. Both are free, air-conditioned and open to seniors,
# MAGIC unlike parks or hawker centres, which are outdoors and hot in the afternoon. Points outside Singapore's bounding box are dropped.
# MAGIC
# MAGIC **`silver_census_subzone`** — Census 2020 numbers per subzone: residents, residents aged 65+ and 75+, and residents in 1–2 room HDB flats
# MAGIC (a common proxy for lower income and less likely to have air-conditioning). In the Census files `"-"` means zero.
# MAGIC Subzones are matched to the Census by name; all 332 match.
# MAGIC
# MAGIC **`silver_census_planning_area`** — one-person households and households with a member who has difficulty with daily activities.
# MAGIC The Census only publishes these for the **30 largest planning areas**, so we keep the national rate in a `NATIONAL` row and use it
# MAGIC where an area's own rate is missing (and flag that in the output). We state this limit rather than overclaim.

# COMMAND ----------

@dlt.table(comment="URA Master Plan 2019 subzones with planning area, URA region and centre point (centroid of the boundary).")
@dlt.expect_or_fail("has_centroid", "centroid_latitude IS NOT NULL AND centroid_longitude IS NOT NULL")
def silver_subzones():
    return (static("bronze_subzones")
            .withColumn("_c", F.expr("st_centroid(st_geomfromgeojson(geometry_geojson))"))
            .select("subzone_name", "subzone_code", "planning_area", "planning_area_code",
                    F.col("region").alias("ura_region"),
                    F.expr("st_y(_c)").alias("centroid_latitude"),
                    F.expr("st_x(_c)").alias("centroid_longitude"),
                    "geometry_geojson"))

@dlt.table(comment="Cool spaces: air-conditioned public places seniors can go to (People's Association Community Clubs and NLB public libraries).")
@dlt.expect_or_drop("has_name", "name IS NOT NULL")
@dlt.expect_or_drop("in_singapore", "latitude BETWEEN 1.15 AND 1.48 AND longitude BETWEEN 103.6 AND 104.1")
def silver_cool_spaces():
    def layer(table, kind):
        return static(table).select("name", F.lit(kind).alias("space_type"), "latitude", "longitude", "postal_code", "street")
    return layer("bronze_community_clubs", "Community Club").unionByName(layer("bronze_libraries", "Public library"))

def census_int(col):
    """Census values are text; '-' means zero."""
    return F.when(F.trim(F.col(col)) == "-", F.lit(0)).otherwise(F.expr(f"try_cast(replace(`{col}`, ',', '') AS INT)"))

@dlt.table(comment="Census 2020 by subzone: residents, residents aged 65+ and 75+, and residents in 1–2 room HDB flats, with shares.")
@dlt.expect("seniors_within_total", "pop_65_plus <= pop_total")
@dlt.expect("matched_all_subzones", "subzone_name IS NOT NULL")
def silver_census_subzone():
    age = static("bronze_census_age").select(
        F.upper(F.trim("Number")).alias("key"),
        census_int("Total_Total").alias("pop_total"),
        sum(census_int(c) for c in ["Total_65_69", "Total_70_74", "Total_75_79", "Total_80_84", "Total_85_89", "Total_90andOver"]).alias("pop_65_plus"),
        sum(census_int(c) for c in ["Total_75_79", "Total_80_84", "Total_85_89", "Total_90andOver"]).alias("pop_75_plus"))
    dwelling = static("bronze_census_dwelling").select(
        F.upper(F.trim("Number")).alias("key"),
        census_int("HDBDwellings_1_and2_RoomFlats1").alias("pop_1_2_room"),
        census_int("HDBDwellings_3_RoomFlats").alias("pop_3_room"))
    subzones = spark.read.table("silver_subzones").select("subzone_name", "planning_area", F.col("subzone_name").alias("key"))
    def share(n, d):
        return F.when(F.col(d) > 0, F.round(F.col(n) / F.col(d), 4))
    return (subzones.join(age, "key", "left").join(dwelling, "key", "left").drop("key")
            .withColumn("pct_65_plus", share("pop_65_plus", "pop_total"))
            .withColumn("pct_75_plus", share("pop_75_plus", "pop_total"))
            .withColumn("pct_1_2_room", share("pop_1_2_room", "pop_total")))

@dlt.table(comment="Census 2020 by planning area (only the 30 largest are published): one-person households and households with a member who has difficulty with daily activities. Row 'NATIONAL' holds the Singapore-wide rates.")
@dlt.expect("shares_valid", "pct_one_person BETWEEN 0 AND 1 AND pct_difficulty BETWEEN 0 AND 1")
def silver_census_planning_area():
    hh = static("bronze_census_household_size").select(
        F.upper(F.trim("Number")).alias("planning_area"),
        census_int("Total").alias("households"), census_int("1Person").alias("one_person_households"))
    da = static("bronze_census_daily_activity").select(
        F.upper(F.trim("Number")).alias("planning_area"),
        census_int("HouseholdswithAtLeastOneMemberUnabletoPerform_withALotofDifficu").alias("households_with_difficulty"))
    return (hh.join(da, "planning_area", "inner")
            .where(F.col("planning_area") != "OTHERS")
            .withColumn("planning_area", F.when(F.col("planning_area") == "TOTAL", "NATIONAL").otherwise(F.col("planning_area")))
            .withColumn("pct_one_person", F.round(F.col("one_person_households") / F.col("households"), 4))
            .withColumn("pct_difficulty", F.round(F.col("households_with_difficulty") / F.col("households"), 4)))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Gold: model features (one row per station per day)
# MAGIC
# MAGIC **What it does:** builds the table the forecast model learns from. Each row is a station on day *d* and describes what we know
# MAGIC at 6:30 pm that day; the **target** is the same station's afternoon peak on day *d + 1*.
# MAGIC
# MAGIC | Feature group | Columns | Why it should help |
# MAGIC |---|---|---|
# MAGIC | Recent heat at the station | `peak_d`, `peak_d1`, `peak_d2`, `peak_mean_7d`, `peak_max_7d`, `daily_max_d` | Weather is persistent: a hot day is usually followed by another |
# MAGIC | Station's usual level | `station_mean_to_date`, `station_offset` | Some sites (e.g. open stadiums) run hotter than others. Uses only days *before* d, so no peeking. The offset is how much hotter or cooler than the network average the station usually is |
# MAGIC | Island-wide heat | `network_mean_peak_d`, `network_max_peak_d`, `network_mean_7d` | Smooths out a single station's noise or missing day |
# MAGIC | Today vs normal | `anom_d` | Today's peak minus the 7-day average: is today unusually hot or cool? |
# MAGIC | Baseline | `baseline_7d_c` | The 7-day average (falling back to today, then the island average). The model predicts the *change* from this baseline |
# MAGIC | Season | `doy_sin`, `doy_cos`, `target_month` | Singapore's hottest months are Apr–Jun and Sep–Oct (the day of year is encoded as a circle so 31 Dec sits next to 1 Jan) |
# MAGIC | NEA's forecast for tomorrow | `nea_temp_high_c`, `nea_temp_low_c`, `nea_rh_high_pct`, `nea_rh_low_pct`, `nea_wind_high_kmh`, `nea_rain_expected`, `nea_region_afternoon_rain` | NEA's own outlook, issued by 6:30 pm. Afternoon showers cut the peak |
# MAGIC | Haze | `psi_24h_d` | Haze episodes in Singapore come with dry, hot spells, so haze levels carry information about the weather pattern |
# MAGIC | Location | `latitude`, `longitude` | Coastal vs inland differences |
# MAGIC
# MAGIC Gaps in a station's record are handled correctly: "yesterday" means exactly the previous calendar day, not the previous row.
# MAGIC Rows for the latest day have no target yet — those are the rows `06_score_forecast` predicts.

# COMMAND ----------

@dlt.table(comment="Forecast model features: one row per WBGT station per day (what is known by 6:30 pm SGT) with the target = the station's afternoon peak WBGT the next day.")
@dlt.expect("has_recent_heat", "peak_d IS NOT NULL OR peak_mean_7d IS NOT NULL")
def gold_forecast_features():
    peaks = (spark.read.table("silver_wbgt_daily_peak")
             .withColumn("peak", F.when(F.col("afternoon_readings") >= MIN_AFTERNOON_READINGS, F.col("afternoon_peak_wbgt_c")))
             .withColumn("day_n", F.datediff(F.col("date_sgt"), F.lit("2025-01-01"))))
    w = W.partitionBy("station_id").orderBy("day_n")
    at = lambda k: F.max("peak").over(w.rangeBetween(k, k))
    df = (peaks
          .withColumn("peak_d", F.col("peak"))
          .withColumn("peak_d1", at(-1))
          .withColumn("peak_d2", at(-2))
          .withColumn("peak_mean_7d", F.avg("peak").over(w.rangeBetween(-6, 0)))
          .withColumn("peak_max_7d", F.max("peak").over(w.rangeBetween(-6, 0)))
          .withColumn("station_mean_to_date", F.avg("peak").over(w.rangeBetween(W.unboundedPreceding, -1)))
          .withColumn("network_mean_peak_d", F.avg("peak").over(W.partitionBy("date_sgt")))
          .withColumn("network_max_peak_d", F.max("peak").over(W.partitionBy("date_sgt")))
          .withColumn("network_mean_7d", F.avg("peak_mean_7d").over(W.partitionBy("date_sgt")))
          .withColumn("anom_d", F.col("peak_d") - F.col("peak_mean_7d"))
          .withColumn("station_offset", F.col("station_mean_to_date") - F.avg("station_mean_to_date").over(W.partitionBy("date_sgt")))
          .withColumn("baseline_7d_c", F.coalesce("peak_mean_7d", "peak_d", "network_mean_peak_d"))
          .withColumn("target_peak_wbgt_c", at(1))
          .withColumn("target_date", F.date_add("date_sgt", 1))
          .withColumn("target_month", F.month("target_date"))
          .withColumn("doy_sin", F.sin(2 * 3.141592653589793 * F.dayofyear("target_date") / 365.25))
          .withColumn("doy_cos", F.cos(2 * 3.141592653589793 * F.dayofyear("target_date") / 365.25))
          .withColumnRenamed("date_sgt", "feature_date")
          .withColumnRenamed("daily_max_wbgt_c", "daily_max_d"))

    stations = spark.read.table("silver_wbgt_stations").select("station_id", "station_name", "latitude", "longitude")
    station_region = nearest_region(stations, "longitude", "latitude")

    # NEA forecast for the target day: latest issue on the day before, by the cut-off, that covers the target day's afternoon
    periods = (spark.read.table("silver_forecast_periods")
               .where((F.col("period_start_hour_sgt") == 12)
                      & (F.col("issued_date_sgt") == F.date_sub("period_date_sgt", 1))
                      & (F.col("issued_time_sgt") <= FORECAST_CUTOFF_SGT)))
    chosen = periods.groupBy(F.col("period_date_sgt").alias("target_date")).agg(F.max("issued_ts").alias("chosen_ts"))
    region_fc = (periods.join(chosen, (periods.period_date_sgt == chosen.target_date) & (periods.issued_ts == chosen.chosen_ts))
                 .select("target_date", "region", "chosen_ts",
                         F.col("forecast_text").alias("nea_region_afternoon_text"),
                         F.col("forecast_text").rlike(RAIN_PATTERN).cast("int").alias("nea_region_afternoon_rain")))
    general = (spark.read.table("silver_forecast_24h")
               .groupBy(F.col("issued_ts").alias("chosen_ts"))
               .agg(F.first("temp_high_c").alias("nea_temp_high_c"), F.first("temp_low_c").alias("nea_temp_low_c"),
                    F.first("rh_high_pct").alias("nea_rh_high_pct"), F.first("rh_low_pct").alias("nea_rh_low_pct"),
                    F.first("wind_speed_high_kmh").alias("nea_wind_high_kmh"),
                    F.first("forecast_text").alias("nea_forecast_text")))
    nea = (region_fc.join(general, "chosen_ts", "left")
           .withColumn("nea_rain_expected", F.col("nea_forecast_text").rlike(RAIN_PATTERN).cast("int"))
           .withColumnRenamed("chosen_ts", "nea_issued_ts"))

    # Haze in the station's region on day d (latest reading up to 6 pm)
    psi = (spark.read.table("silver_psi").where(F.col("hour_sgt") <= 18)
           .groupBy(F.col("date_sgt").alias("feature_date"), "region")
           .agg(F.max_by("psi_twenty_four_hourly", "reading_ts").alias("psi_24h_d")))

    return (df.join(station_region.select("station_id", "station_name", "latitude", "longitude", "region"), "station_id", "left")
            .join(nea, ["target_date", "region"], "left")
            .join(psi, ["feature_date", "region"], "left")
            .select("station_id", "station_name", "region", "latitude", "longitude", "feature_date", "target_date",
                    "peak_d", "peak_d1", "peak_d2", "peak_mean_7d", "peak_max_7d", "daily_max_d", "station_mean_to_date",
                    "network_mean_peak_d", "network_max_peak_d", "network_mean_7d", "anom_d", "station_offset",
                    "baseline_7d_c", "target_month", "doy_sin", "doy_cos",
                    "nea_issued_ts", "nea_temp_high_c", "nea_temp_low_c", "nea_rh_high_pct", "nea_rh_low_pct",
                    "nea_wind_high_kmh", "nea_forecast_text", "nea_rain_expected",
                    "nea_region_afternoon_text", "nea_region_afternoon_rain", "psi_24h_d",
                    "afternoon_readings", "target_peak_wbgt_c"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Gold: from 30 stations to 332 subzones
# MAGIC
# MAGIC **What it does:** heat is measured at ~30 stations, but people live in 332 subzones. For each subzone we take its
# MAGIC **3 nearest active stations** and blend their values, giving closer stations more say (weight ∝ 1 / distance², known as
# MAGIC inverse-distance weighting). A station 1 km away counts 4× as much as one 2 km away.
# MAGIC
# MAGIC **Why 3 stations rather than 1:** one station can have a bad day (sensor fault, local shade). Blending smooths that out without
# MAGIC pretending to more detail than 30 stations can give. We also keep the distance to the nearest station so the app can show how
# MAGIC close the measurement really is (the furthest subzone is about 7 km from a station).

# COMMAND ----------

@dlt.table(comment=f"For each subzone, its {NEAREST_STATIONS} nearest active WBGT stations and inverse-distance weights (power 2) used to estimate heat at the subzone centre.")
def gold_subzone_station_weights():
    sz = spark.read.table("silver_subzones").select("subzone_name", "centroid_latitude", "centroid_longitude")
    st = (spark.read.table("silver_wbgt_stations").where("is_active")
          .select("station_id", "station_name", F.col("latitude").alias("st_lat"), F.col("longitude").alias("st_lon")))
    d = (sz.crossJoin(st)
         .withColumn("distance_km", F.round(distance_km("centroid_longitude", "centroid_latitude", "st_lon", "st_lat"), 3))
         .withColumn("station_rank", F.row_number().over(W.partitionBy("subzone_name").orderBy("distance_km")))
         .where(F.col("station_rank") <= NEAREST_STATIONS)
         .withColumn("_inv", 1 / F.pow(F.greatest(F.col("distance_km"), F.lit(0.2)), 2)))
    return (d.withColumn("weight", F.round(F.col("_inv") / F.sum("_inv").over(W.partitionBy("subzone_name")), 4))
             .select("subzone_name", "station_id", "station_name", "station_rank", "distance_km", "weight"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Gold: subzone profile and vulnerability score
# MAGIC
# MAGIC **What it does:** one row per subzone that brings together who lives there and how far they are from help:
# MAGIC - **People** (Census 2020): residents aged 65+, share aged 65+ and 75+, share in 1–2 room flats, and the planning area's
# MAGIC   one-person-household and daily-activity-difficulty rates (national rate where not published, flagged in `pa_data_published`).
# MAGIC - **Nearest cool space**: name, type and straight-line distance from the subzone centre, plus how many are within 1 km.
# MAGIC - **Nearest WBGT station** and **haze region**.
# MAGIC
# MAGIC **Vulnerability score (0–1):** for each of the 5 indicators we compute the subzone's **percentile rank** among in-scope subzones
# MAGIC (0 = lowest, 1 = highest), then take a weighted sum (weights in the settings cell). Percentile ranks put indicators measured in
# MAGIC different units (people, percentages) on the same 0–1 scale and stop one extreme value from dominating.
# MAGIC
# MAGIC **In scope:** subzones with at least 50 residents aged 65+. Industrial areas, nature reserves and near-empty subzones would otherwise
# MAGIC top the list on percentages alone (e.g. 3 seniors out of 5 residents = 60%).

# COMMAND ----------

@dlt.table(comment="One row per subzone: who lives there (Census 2020), nearest cool space, nearest WBGT station and haze region, and the vulnerability score (0–1) with its parts.")
@dlt.expect("has_cool_space", "nearest_cool_space IS NOT NULL")
def gold_subzone_profile():
    sz = spark.read.table("silver_subzones")
    census = spark.read.table("silver_census_subzone").drop("planning_area")
    pa = spark.read.table("silver_census_planning_area")
    national = pa.where("planning_area = 'NATIONAL'").select(F.col("pct_one_person").alias("nat_one"), F.col("pct_difficulty").alias("nat_diff"))

    cool = spark.read.table("silver_cool_spaces")
    nearest_cool = (sz.select("subzone_name", "centroid_latitude", "centroid_longitude").crossJoin(cool)
                    .withColumn("d", distance_km("centroid_longitude", "centroid_latitude", "longitude", "latitude"))
                    .groupBy("subzone_name")
                    .agg(F.min_by("name", "d").alias("nearest_cool_space"),
                         F.min_by("space_type", "d").alias("nearest_cool_space_type"),
                         F.min_by("street", "d").alias("nearest_cool_space_street"),
                         F.min_by("postal_code", "d").alias("nearest_cool_space_postal"),
                         F.round(F.min("d"), 2).alias("cool_space_km"),
                         F.count(F.when(F.col("d") <= 1.0, True)).alias("cool_spaces_within_1km")))

    nearest_station = (spark.read.table("gold_subzone_station_weights").where("station_rank = 1")
                       .select("subzone_name", F.col("station_name").alias("nearest_wbgt_station"),
                               F.col("distance_km").alias("nearest_wbgt_station_km")))

    haze_region = (nearest_region(sz.select("subzone_name", "centroid_latitude", "centroid_longitude"),
                                  "centroid_longitude", "centroid_latitude")
                   .select("subzone_name", F.col("region").alias("haze_region")))

    p = (sz.select("subzone_name", "subzone_code", "planning_area", "ura_region", "centroid_latitude", "centroid_longitude")
         .join(census, "subzone_name", "left")
         .join(pa.select("planning_area", F.col("pct_one_person").alias("pa_pct_one_person_raw"),
                         F.col("pct_difficulty").alias("pa_pct_difficulty_raw")), "planning_area", "left")
         .crossJoin(national)
         .withColumn("pa_data_published", F.col("pa_pct_one_person_raw").isNotNull())
         .withColumn("pa_pct_one_person", F.coalesce("pa_pct_one_person_raw", "nat_one"))
         .withColumn("pa_pct_difficulty", F.coalesce("pa_pct_difficulty_raw", "nat_diff"))
         .drop("pa_pct_one_person_raw", "pa_pct_difficulty_raw", "nat_one", "nat_diff")
         .join(nearest_cool, "subzone_name", "left")
         .join(nearest_station, "subzone_name", "left")
         .join(haze_region, "subzone_name", "left")
         .withColumn("in_scope", F.coalesce(F.col("pop_65_plus"), F.lit(0)) >= MIN_SENIORS))

    # Vulnerability: weighted percentile ranks, computed among in-scope subzones only
    scoped = p.where("in_scope")
    for col in VULNERABILITY_WEIGHTS:
        scoped = scoped.withColumn(f"pr_{col}", F.round(F.percent_rank().over(W.orderBy(col)), 4))
    scoped = scoped.withColumn("vulnerability_score", F.round(
        sum(F.lit(w) * F.col(f"pr_{c}") for c, (w, _) in VULNERABILITY_WEIGHTS.items()), 4))
    keep = ["subzone_name"] + [f"pr_{c}" for c in VULNERABILITY_WEIGHTS] + ["vulnerability_score"]
    return p.join(scoped.select(*keep), "subzone_name", "left")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Gold: conditions per subzone (forecast, latest observation, haze)
# MAGIC
# MAGIC **What it does:** for every subzone, blends the station values with the weights above to give:
# MAGIC - **Tomorrow's forecast** afternoon peak and the chance of Moderate-or-higher and High heat — from `ml_wbgt_forecast`, written by
# MAGIC   `06_score_forecast`. Used only if it is a genuine forecast (its date is after the latest observed day). A subzone is on
# MAGIC   **High-heat alert** when its blended chance of High reaches the model's alert threshold.
# MAGIC - **Latest observed** WBGT (the most recent 15-minute reading) and the **latest afternoon peak** (the fallback when no forecast exists).
# MAGIC - **Latest haze** (24-hour PSI and PM2.5) for the subzone's NEA region. There is no official haze forecast, so we carry the latest value forward and label it as such.
# MAGIC
# MAGIC If a nearby station didn't report, the weights are re-scaled over the stations that did, so one missing station doesn't distort the value.

# COMMAND ----------

@dlt.table(comment="Conditions per subzone: tomorrow's forecast afternoon peak WBGT (when available), latest observed WBGT and afternoon peak (inverse-distance blend of the nearest stations), and latest haze for the subzone's NEA region.")
def gold_subzone_conditions():
    weights = spark.read.table("gold_subzone_station_weights")
    wbgt = spark.read.table("silver_wbgt")

    latest_ts = wbgt.agg(F.max("reading_ts").alias("ts"))
    latest = (wbgt.join(latest_ts, wbgt.reading_ts == latest_ts.ts)
              .select("station_id", F.col("wbgt_c").alias("v"), F.col("reading_ts").alias("latest_reading_ts")))

    peaks = spark.read.table("silver_wbgt_daily_peak").where(f"afternoon_readings >= {MIN_AFTERNOON_READINGS}")
    peak_day = peaks.agg(F.max("date_sgt").alias("d"))
    peak = (peaks.join(peak_day, peaks.date_sgt == peak_day.d)
            .select("station_id", F.col("afternoon_peak_wbgt_c").alias("v"), F.col("date_sgt").alias("peak_date_sgt")))

    def blend(values, name, extra, more=()):
        # Re-normalise weights over stations that actually reported
        j = weights.join(values, "station_id")
        aggs = [(F.sum(F.col("weight") * F.col("v")) / F.sum("weight")).alias(name), F.max(extra).alias(extra)]
        aggs += [(F.sum(F.col("weight") * F.col(m)) / F.sum("weight")).alias(m) for m in more]
        return j.groupBy("subzone_name").agg(*aggs)

    heat = (blend(latest, "wbgt_latest_c", "latest_reading_ts")
            .join(blend(peak, "wbgt_afternoon_peak_c", "peak_date_sgt"), "subzone_name", "full"))

    # ml_wbgt_forecast always exists (created empty by 00_setup / 06_score_forecast); while empty, the list falls back to observed heat
    fc = spark.read.table(ML_FORECAST_TABLE)
    newest = fc.agg(F.max("target_date").alias("t"))
    fc = (fc.join(newest, fc.target_date == newest.t)
          .join(peak_day, F.col("target_date") > F.col("d"))          # only a genuine forecast (after the latest observed day)
          .select("station_id", F.col("predicted_peak_wbgt_c").alias("v"), "target_date",
                  "prob_moderate_plus", "prob_high", "high_alert_threshold", "model_version"))
    fc_sz = (blend(fc, "wbgt_forecast_c", "target_date", more=("prob_moderate_plus", "prob_high"))
             .crossJoin(fc.groupBy().agg(F.max("model_version").alias("forecast_model_version"),
                                         F.max("high_alert_threshold").alias("high_alert_threshold")))
             .withColumn("high_alert", F.col("prob_high") >= F.col("high_alert_threshold")))
    heat = heat.join(fc_sz.withColumnRenamed("target_date", "forecast_target_date"), "subzone_name", "left")

    for c in ["wbgt_latest_c", "wbgt_afternoon_peak_c", "wbgt_forecast_c"]:
        heat = heat.withColumn(c, F.round(c, 1))
    heat = (heat.withColumn("prob_moderate_plus", F.round("prob_moderate_plus", 3))
                .withColumn("prob_high", F.round("prob_high", 3))
                .withColumn("heat_band_latest", wbgt_band(F.col("wbgt_latest_c")))
                .withColumn("heat_band_afternoon_peak", wbgt_band(F.col("wbgt_afternoon_peak_c")))
                .withColumn("heat_band_forecast", wbgt_band(F.col("wbgt_forecast_c"))))

    psi = spark.read.table("silver_psi")
    psi_latest = (psi.join(psi.agg(F.max("reading_ts").alias("ts")), F.col("reading_ts") == F.col("ts"))
                  .select(F.col("region").alias("haze_region"), "psi_twenty_four_hourly", "pm25_twenty_four_hourly", "psi_band",
                          F.col("reading_ts").alias("psi_reading_ts")))
    pm = spark.read.table("silver_pm25")
    pm_latest = (pm.join(pm.agg(F.max("reading_ts").alias("ts")), F.col("reading_ts") == F.col("ts"))
                 .select(F.col("region").alias("haze_region"), "pm25_one_hourly"))

    regions = spark.read.table("gold_subzone_profile").select("subzone_name", "haze_region")
    return (regions.join(heat, "subzone_name", "left")
            .join(psi_latest, "haze_region", "left")
            .join(pm_latest, "haze_region", "left"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Gold: score weights and the action rulebook
# MAGIC
# MAGIC **`gold_score_weights`** publishes the weights from the settings cell as a table (`score` = hazard, exposure or vulnerability_score),
# MAGIC so the app and Genie can show exactly how the risk score is built.
# MAGIC
# MAGIC **`gold_rulebook`** holds the fixed actions for each heat band and haze band. **Actions come from this table, never from an AI model**:
# MAGIC there is no data on which outreach actions reduce heat illness, so an AI choosing actions would be guessing. The language model in the
# MAGIC app only rewrites the wording (e.g. into a friendly message or another language). The wording is a draft, to be checked against NEA's
# MAGIC heat-stress and haze advisories and, ideally, by an Active Ageing Centre coordinator.

# COMMAND ----------

@dlt.table(comment="Score weights used by gold_checkin_list and the vulnerability score (shown in the app).")
def gold_score_weights():
    rows = SCORE_WEIGHTS + [("vulnerability_score", k, w, d) for k, (w, d) in VULNERABILITY_WEIGHTS.items()]
    return spark.createDataFrame(rows, "score STRING, component STRING, weight DOUBLE, description STRING")

RULEBOOK = [
    # (trigger, level, action) — draft; to be checked against NEA heat-stress and haze advisories
    ("heat", "High", "Call or visit before 11 am. Advise staying indoors from 11 am to 4 pm, drinking water regularly, and going to the nearest cool space if the home is hot. Prioritise seniors living alone."),
    ("heat", "Moderate", "Phone check-in, starting with seniors living alone. Remind them to avoid outdoor activity from 12 pm to 4 pm and keep hydrated."),
    ("heat", "Low", "Routine check-ins. No heat-specific action needed."),
    ("haze", "Unhealthy", "Advise keeping windows closed and cutting outdoor activity. Check that seniors with heart or lung conditions have their medication."),
    ("haze", "Very unhealthy", "Advise staying indoors with windows closed. Check on seniors with heart or lung conditions first; suggest a cool space with air-conditioning."),
    ("haze", "Hazardous", "Advise staying indoors with windows closed. Check on seniors with heart or lung conditions first; suggest a cool space with air-conditioning."),
]

@dlt.table(comment="Action rulebook: fixed actions by heat-stress band and haze (PSI) band. The LLM only rewrites the wording; it never chooses actions. Draft, to be checked against NEA guidance.")
def gold_rulebook():
    return spark.createDataFrame(RULEBOOK, "trigger STRING, level STRING, action STRING")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Gold: scoring and priority tiers (shared by the live list and the replay)
# MAGIC
# MAGIC **Why the score multiplies:** an earlier version *added* heat, haze, vulnerability and distance. Because heat varies little between areas
# MAGIC and vulnerability never changes, that list looked almost the same every day — "many vulnerable seniors" topped it whatever the weather.
# MAGIC The risk score is now **hazard × exposure**:
# MAGIC
# MAGIC | Part | What it measures | How |
# MAGIC |---|---|---|
# MAGIC | **Hazard** (0–1) | How dangerous the day is | 0.5 × chance of Moderate-or-higher heat + 0.5 × chance of High heat (full at 50%), from the forecast model, plus up to 0.3 for haze. With no forecast: a fixed value per observed band |
# MAGIC | **Exposure** (0–1) | Who would be affected | 0.7 × Census vulnerability score + 0.3 × distance to the nearest cool space |
# MAGIC
# MAGIC On a cool day every area scores low; on a hot day the most exposed areas rise to the top. The forecast now drives the list.
# MAGIC
# MAGIC **Priority tiers** — what a coordinator actually needs to know:
# MAGIC | Tier | Rule | Action (from the rulebook) |
# MAGIC |---|---|---|
# MAGIC | **Act** | High heat forecast, or High-heat alert (a meaningful chance of High) | High-heat action: call or visit before 11 am |
# MAGIC | **Check in** | Moderate heat forecast **and** among the most exposed quarter of areas | Moderate-heat action: phone check-in |
# MAGIC | **Routine** | Everything else | Routine check-ins |
# MAGIC
# MAGIC Haze actions are added whenever the area's PSI is Unhealthy or worse. Within each tier, areas are ordered by risk score.

# COMMAND ----------

def blend_stations(values, value_cols, keys=()):
    """Station values → subzone values with the inverse-distance weights (re-normalised over stations that reported)."""
    w = spark.read.table("gold_subzone_station_weights").select("subzone_name", "station_id", "weight")
    j = w.join(values, "station_id")
    aggs = [(F.sum(F.col("weight") * F.col(c)) / F.sum(F.when(F.col(c).isNotNull(), F.col("weight")))).alias(c) for c in value_cols]
    return j.groupBy("subzone_name", *keys).agg(*aggs)

def score_and_tier(df, partition=()):
    """Adds hazard, exposure, risk_score, tier, action_band and main_driver. Expects heat_is_forecast, heat_band, high_alert,
    prob_moderate_plus, prob_high, psi_twenty_four_hourly, psi_band, vulnerability_score and cool_space_km."""
    obs = F.create_map(*[x for k, v in OBSERVED_HAZARD.items() for x in (F.lit(k), F.lit(v))])
    heat_hazard = F.when(F.col("heat_is_forecast"),
                         0.5 * F.col("prob_moderate_plus") + 0.5 * F.least(F.lit(1.0), F.col("prob_high") / P_HIGH_FULL)
                         ).otherwise(obs[F.col("heat_band")])
    df = (df.withColumn("action_band", F.when(F.col("high_alert"), F.lit("High")).otherwise(F.col("heat_band")))
            .withColumn("heat_hazard", F.round(F.coalesce(heat_hazard, F.lit(0.0)), 4))
            .withColumn("haze_component", F.coalesce(F.round(clamp01((F.col("psi_twenty_four_hourly") - 50) / 150), 4), F.lit(0.0)))
            .withColumn("haze_hazard", F.round(HAZE_IN_HAZARD * F.col("haze_component"), 4))
            .withColumn("hazard", F.round(F.least(F.lit(1.0), F.col("heat_hazard") + F.col("haze_hazard")), 4))
            .withColumn("access_component", F.round(clamp01(F.col("cool_space_km") / FAR_FROM_COOL_SPACE_KM), 4))
            .withColumn("exposure", F.round(EXPOSURE_WEIGHTS["vulnerability"] * F.col("vulnerability_score")
                                            + EXPOSURE_WEIGHTS["access"] * F.col("access_component"), 4))
            .withColumn("exposure_pctl", F.round(F.percent_rank().over(W.partitionBy(*partition).orderBy("exposure")), 4))
            .withColumn("risk_score", F.round(100 * F.col("hazard") * F.col("exposure"), 1)))
    severe_haze = F.col("psi_band").isin("Very unhealthy", "Hazardous")
    df = (df.withColumn("tier", F.when(F.col("action_band") == "High", "Act")
                                 .when(((F.col("action_band") == "Moderate") | severe_haze) & (F.col("exposure_pctl") >= CHECKIN_EXPOSURE_PCTL), "Check in")
                                 .otherwise("Routine"))
            .withColumn("tier_order", F.create_map(*[x for k, v in TIERS.items() for x in (F.lit(k), F.lit(v))])[F.col("tier")])
            .withColumn("main_driver", F.when(F.col("tier") == "Act", "heat")
                                        .when(F.col("haze_hazard") > F.col("heat_hazard"), "haze")
                                        .when(EXPOSURE_WEIGHTS["access"] * F.col("access_component") > EXPOSURE_WEIGHTS["vulnerability"] * F.col("vulnerability_score"), "access")
                                        .otherwise("vulnerability"))
            .withColumn("rank", F.row_number().over(W.partitionBy(*partition).orderBy(
                "tier_order", F.col("risk_score").desc_nulls_last(), F.col("pop_65_plus").desc()))))
    return df

# COMMAND ----------

# MAGIC %md
# MAGIC ## Gold: the ranked check-in list
# MAGIC
# MAGIC **What it does:** the table coordinators act on. For every in-scope subzone (≥ 50 residents aged 65+):
# MAGIC 1. **Heat** — tomorrow's forecast afternoon peak and the chance of Moderate and High heat when available, otherwise the latest observed peak
# MAGIC    (`heat_basis` says which).
# MAGIC 2. **Hazard, exposure, risk score and tier** — see the cell above.
# MAGIC 3. **Reason** — one plain-English line with the real numbers, and the **action** from the rulebook for the tier and haze level.
# MAGIC
# MAGIC The `has_heat` expectation flags any subzone without a heat value (e.g. all its nearby stations offline).

# COMMAND ----------

@dlt.table(comment="Ranked check-in list: in-scope subzones (≥ 50 residents aged 65+) with tier (Act / Check in / Routine), risk score = 100 × hazard × exposure, "
                   "the reason and the rulebook action. Heat basis: tomorrow's model forecast when available, otherwise the latest observed afternoon peak.")
@dlt.expect("has_heat", "heat_band IS NOT NULL")
def gold_checkin_list():
    p = spark.read.table("gold_subzone_profile").where("in_scope")
    c = spark.read.table("gold_subzone_conditions").drop("haze_region")
    rules = spark.read.table("gold_rulebook")
    heat_rules = rules.where("trigger = 'heat'").select(F.col("level").alias("rule_level"), F.col("action").alias("heat_action"))
    haze_rules = rules.where("trigger = 'haze'").select(F.col("level").alias("psi_band"), F.col("action").alias("haze_action"))

    is_fc = F.col("wbgt_forecast_c").isNotNull()
    df = (p.join(c, "subzone_name", "left")
          .withColumn("heat_is_forecast", is_fc)
          .withColumn("heat_wbgt_c", F.coalesce("wbgt_forecast_c", "wbgt_afternoon_peak_c"))
          .withColumn("heat_band", wbgt_band(F.col("heat_wbgt_c")))
          .withColumn("high_alert", F.coalesce(is_fc & F.col("high_alert"), F.lit(False)))
          .withColumn("for_date", F.when(is_fc, F.col("forecast_target_date")).otherwise(F.col("peak_date_sgt")))
          .withColumn("heat_basis", F.when(is_fc, F.concat(F.lit("Forecast for "), F.date_format("forecast_target_date", "EEE d MMM yyyy"),
                                                              F.lit(" (model v"), F.col("forecast_model_version"), F.lit(")")))
                                     .otherwise(F.concat(F.lit("Observed afternoon peak on "), F.date_format("peak_date_sgt", "EEE d MMM yyyy")))))
    df = score_and_tier(df)

    pct = lambda col: F.concat(F.round(F.col(col) * 100, 0).cast("int").cast("string"), F.lit("%"))
    df = df.withColumn("reason", F.concat_ws(" · ",
        F.when(F.col("high_alert") & (F.col("heat_band") != "High"),
               F.concat(F.lit("High heat possible ("), F.round(F.col("prob_high") * 100, 0).cast("int").cast("string"), F.lit("% chance)"))),
        F.concat(F.when(is_fc, F.lit("Forecast heat: WBGT ")).otherwise(F.lit("Heat: WBGT ")),
                 F.col("heat_wbgt_c").cast("string"), F.lit(" °C ("), F.col("heat_band"), F.lit(")")),
        F.concat(F.lit("Seniors: "), F.format_number("pop_65_plus", 0), F.lit(" aged 65+ ("), pct("pct_65_plus"), F.lit(" of residents)")),
        F.when(F.col("exposure_pctl") >= CHECKIN_EXPOSURE_PCTL, F.lit("Among the most exposed quarter of areas")),
        F.concat(F.lit("Nearest cool space: "), F.col("nearest_cool_space"), F.lit(" ("), F.col("cool_space_km").cast("string"), F.lit(" km)")),
        F.concat(F.lit("Haze: PSI "), F.col("psi_twenty_four_hourly").cast("int").cast("string"), F.lit(" ("), F.col("psi_band"), F.lit(")"))))

    df = (df.withColumn("rule_level", F.when(F.col("tier") == "Act", "High").when(F.col("tier") == "Check in", "Moderate").otherwise("Low"))
            .join(heat_rules, "rule_level", "left").join(haze_rules, "psi_band", "left")
            .withColumn("action", F.concat_ws(" ", "heat_action", "haze_action")))
    return df.select(
        "rank", "tier", "subzone_name", "planning_area", "ura_region", "risk_score", "hazard", "exposure", "exposure_pctl",
        "main_driver", "reason", "action",
        "heat_wbgt_c", "heat_band", "high_alert", "action_band", "heat_is_forecast", "heat_basis", "for_date", "prob_moderate_plus", "prob_high",
        "wbgt_latest_c", "latest_reading_ts", "wbgt_afternoon_peak_c", "peak_date_sgt",
        "psi_twenty_four_hourly", "psi_band", "pm25_one_hourly", "psi_reading_ts",
        "pop_total", "pop_65_plus", "pct_65_plus", "pop_75_plus", "pct_75_plus", "pct_1_2_room",
        "pa_pct_one_person", "pa_pct_difficulty", "pa_data_published",
        "vulnerability_score", "nearest_cool_space", "nearest_cool_space_type", "nearest_cool_space_street",
        "nearest_cool_space_postal", "cool_space_km", "cool_spaces_within_1km",
        "nearest_wbgt_station", "nearest_wbgt_station_km", "haze_region",
        "heat_hazard", "haze_hazard", "haze_component", "access_component",
        "centroid_latitude", "centroid_longitude")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Gold: the day outlook (one line for the coordinator)
# MAGIC
# MAGIC **What it does:** sums the list up into the single message a coordinator needs first — *is tomorrow a day to act, and for how many seniors?*
# MAGIC
# MAGIC | Level | When | Headline |
# MAGIC |---|---|---|
# MAGIC | **High-heat risk** | at least one area in **Act** | "High-heat risk on Thu 15 Oct in 3 areas — 4,430 seniors…" |
# MAGIC | **Take care** | no Act areas, at least one **Check in** area | "Moderate heat on … check in on N high-exposure areas" |
# MAGIC | **Normal** | neither | "No heat risk … routine check-ins only" |

# COMMAND ----------

@dlt.table(comment="Day outlook: one row summarising the check-in list — level (High-heat risk / Take care / Normal), headline, and the number of areas and seniors in each tier.")
def gold_day_outlook():
    df = spark.read.table("gold_checkin_list")
    agg = df.agg(
        F.max("for_date").alias("for_date"), F.max("heat_basis").alias("heat_basis"), F.max(F.col("heat_is_forecast").cast("int")).cast("boolean").alias("is_forecast"),
        F.count("*").alias("total_areas"), F.sum("pop_65_plus").alias("total_seniors"),
        *[x for t in TIERS for x in (F.count(F.when(F.col("tier") == t, True)).alias(f"{t.lower().replace(' ', '')}_areas"),
                                    F.coalesce(F.sum(F.when(F.col("tier") == t, F.col("pop_65_plus"))), F.lit(0)).alias(f"{t.lower().replace(' ', '')}_seniors"))],
        F.round(F.max("prob_high"), 3).alias("max_prob_high"), F.round(F.max("heat_wbgt_c"), 1).alias("hottest_heat_c"),
        F.max("psi_twenty_four_hourly").alias("worst_psi"), F.max_by("psi_band", "psi_twenty_four_hourly").alias("worst_psi_band"))
    day = F.date_format("for_date", "EEE d MMM")
    plural = lambda n, word: F.concat(F.col(n).cast("string"), F.lit(f" {word}"), F.when(F.col(n) == 1, F.lit("")).otherwise(F.lit("s")))
    return (agg
        .withColumn("level", F.when(F.col("act_areas") > 0, "High-heat risk").when(F.col("checkin_areas") > 0, "Take care").otherwise("Normal"))
        .withColumn("headline", F.when(F.col("act_areas") > 0, F.concat(
                F.lit("High-heat risk on "), day, F.lit(" in "), plural("act_areas", "area"), F.lit(" — "), F.format_number("act_seniors", 0),
                F.lit(" seniors aged 65+ live there. Call or visit them before 11 am.")))
            .when(F.col("checkin_areas") > 0, F.concat(
                F.lit("Moderate heat on "), day, F.lit(". Check in on "), plural("checkin_areas", "high-exposure area"), F.lit(" ("),
                F.format_number("checkin_seniors", 0), F.lit(" seniors aged 65+).")))
            .otherwise(F.concat(F.lit("No heat risk on "), day, F.lit(". Routine check-ins only.")))))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Gold: replay — what HeatGuard would have said on past days
# MAGIC
# MAGIC **What it does:** runs exactly the same scoring and tiers on every day of the forecast model's **test period** (Jul–Oct 2026), using the
# MAGIC forecasts that the model trained *before July* made the evening before (`ml_backtest_predictions`, written by `05_forecast_model`). It then
# MAGIC compares each area's tier with what actually happened at its nearest weather station.
# MAGIC
# MAGIC This answers the question judges and coordinators will ask: *"On a real hot day, would HeatGuard have pointed us to the right places?"*
# MAGIC - **`gold_replay_list`** — one row per day per area: forecast, tier, risk score, and the afternoon peak actually measured nearby.
# MAGIC - **`gold_replay_summary`** — one row per day: areas and seniors in Act / Check in, areas that actually reached High, and how many were caught.
# MAGIC
# MAGIC Notes: station weights use today's station network (stations that did not report on a day are left out of that day's blend); haze is the
# MAGIC 24-hour PSI known by 6 pm the evening before.

# COMMAND ----------

@dlt.table(comment="Replay of the check-in list on every test-period day (Jul–Oct 2026) using the forecasts made the evening before, with the afternoon peak actually measured at each area's nearest station.")
def gold_replay_list():
    bt = spark.read.table(f"{CATALOG}.{SCHEMA}.ml_backtest_predictions")
    threshold = spark.read.table(f"{CATALOG}.{SCHEMA}.ml_model_evaluation").agg(F.max("alert_threshold").alias("thr"))
    preds = bt.select("station_id", "target_date", "feature_date", F.col("predicted_peak_wbgt_c").alias("heat_wbgt_c"),
                      "prob_moderate_plus", "prob_high", F.col("actual_peak_wbgt_c").alias("actual_c"))
    sz = blend_stations(preds, ["heat_wbgt_c", "prob_moderate_plus", "prob_high"], keys=("target_date", "feature_date"))
    nearest = (spark.read.table("gold_subzone_station_weights").where("station_rank = 1").select("subzone_name", "station_id")
               .join(preds.select("station_id", "target_date", "actual_c"), "station_id")
               .select("subzone_name", "target_date", F.col("actual_c").alias("actual_peak_nearest_c")))
    psi = (spark.read.table("silver_psi").where(F.col("hour_sgt") <= 18)
           .groupBy(F.col("date_sgt").alias("feature_date"), F.col("region").alias("haze_region"))
           .agg(F.max_by("psi_twenty_four_hourly", "reading_ts").alias("psi_twenty_four_hourly")))
    p = spark.read.table("gold_subzone_profile").where("in_scope").select(
        "subzone_name", "planning_area", "pop_65_plus", "vulnerability_score", "cool_space_km", "haze_region", "centroid_latitude", "centroid_longitude")
    df = (p.join(sz, "subzone_name").join(nearest, ["subzone_name", "target_date"], "left").join(psi, ["feature_date", "haze_region"], "left")
            .crossJoin(threshold)
            .withColumn("heat_wbgt_c", F.round("heat_wbgt_c", 1))
            .withColumn("heat_is_forecast", F.lit(True))
            .withColumn("heat_band", wbgt_band(F.col("heat_wbgt_c")))
            .withColumn("high_alert", F.coalesce(F.col("prob_high") >= F.col("thr"), F.lit(False)))
            .withColumn("psi_band", psi_band(F.col("psi_twenty_four_hourly"))))
    df = score_and_tier(df, partition=("target_date",))
    return (df.withColumn("actual_band_nearest", wbgt_band(F.col("actual_peak_nearest_c")))
              .withColumn("actually_high", F.coalesce(F.col("actual_band_nearest") == "High", F.lit(False)))
              .select("target_date", "rank", "tier", "subzone_name", "planning_area", "pop_65_plus", "risk_score", "hazard", "exposure",
                      "heat_wbgt_c", "heat_band", "prob_moderate_plus", "prob_high", "high_alert", "psi_twenty_four_hourly", "psi_band",
                      "actual_peak_nearest_c", "actual_band_nearest", "actually_high", "centroid_latitude", "centroid_longitude"))

@dlt.table(comment="Replay summary per test-period day: areas and seniors in Act / Check in, areas whose nearest station actually reached High heat, and how many of those HeatGuard put in Act or Check in the evening before.")
def gold_replay_summary():
    r = spark.read.table("gold_replay_list")
    flagged = F.col("tier").isin("Act", "Check in")
    return (r.groupBy("target_date").agg(
                F.count("*").alias("areas"),
                F.count(F.when(F.col("tier") == "Act", True)).alias("act_areas"),
                F.coalesce(F.sum(F.when(F.col("tier") == "Act", F.col("pop_65_plus"))), F.lit(0)).alias("act_seniors"),
                F.count(F.when(F.col("tier") == "Check in", True)).alias("checkin_areas"),
                F.count(F.when(F.col("actually_high"), True)).alias("high_areas"),
                F.coalesce(F.sum(F.when(F.col("actually_high"), F.col("pop_65_plus"))), F.lit(0)).alias("high_seniors"),
                F.count(F.when(F.col("actually_high") & (F.col("tier") == "Act"), True)).alias("high_areas_in_act"),
                F.count(F.when(F.col("actually_high") & flagged, True)).alias("high_areas_flagged"),
                F.coalesce(F.sum(F.when(F.col("actually_high") & flagged, F.col("pop_65_plus"))), F.lit(0)).alias("high_seniors_flagged"),
                F.round(F.max("actual_peak_nearest_c"), 1).alias("hottest_actual_c"))
            .withColumn("share_high_areas_flagged", F.round(F.col("high_areas_flagged") / F.col("high_areas"), 3)))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Gold: summaries for the app and Genie
# MAGIC
# MAGIC Small, ready-to-read tables so the app loads quickly and Genie answers questions without scanning a million rows:
# MAGIC - **`gold_wbgt_station_latest`** — each active station's most recent reading and today's peak so far (the app's "Now" view).
# MAGIC - **`gold_haze_latest`** — the latest PSI and PM2.5 for each of the 5 regions.
# MAGIC - **`gold_daily_summary`** — one row per day: hottest station peak, how many stations reached Moderate / High, and the worst PSI.
# MAGIC   Used for trend charts and questions like "how many High heat days were there in September?".

# COMMAND ----------

@dlt.table(comment="Latest WBGT reading for each active station, with today's peak so far and band (the app's 'Now' view).")
def gold_wbgt_station_latest():
    wbgt = spark.read.table("silver_wbgt")
    st = spark.read.table("silver_wbgt_stations").where("is_active").select("station_id")
    latest = (wbgt.join(st, "station_id")
              .groupBy("station_id")
              .agg(F.max_by("station_name", "reading_ts").alias("station_name"),
                   F.max_by("town_center", "reading_ts").alias("town_center"),
                   F.max_by("latitude", "reading_ts").alias("latitude"),
                   F.max_by("longitude", "reading_ts").alias("longitude"),
                   F.max("reading_ts").alias("latest_reading_ts"),
                   F.max_by("time_sgt", "reading_ts").alias("latest_time_sgt"),
                   F.max_by("date_sgt", "reading_ts").alias("latest_date_sgt"),
                   F.max_by("wbgt_c", "reading_ts").alias("wbgt_c")))
    today = (wbgt.join(latest.select("station_id", F.col("latest_date_sgt").alias("date_sgt")), ["station_id", "date_sgt"])
             .groupBy("station_id").agg(F.max("wbgt_c").alias("peak_so_far_today_c")))
    return (latest.join(today, "station_id", "left")
            .withColumn("heat_band", wbgt_band(F.col("wbgt_c")))
            .withColumn("peak_so_far_band", wbgt_band(F.col("peak_so_far_today_c"))))

@dlt.table(comment="Latest haze reading for each of NEA's 5 regions: 24-hour PSI and band, 24-hour PM2.5 and 1-hour PM2.5.")
def gold_haze_latest():
    psi = spark.read.table("silver_psi")
    pm = spark.read.table("silver_pm25")
    last_psi = psi.groupBy("region").agg(F.max("reading_ts").alias("reading_ts"))
    last_pm = pm.groupBy("region").agg(F.max("reading_ts").alias("reading_ts"))
    p = psi.join(last_psi, ["region", "reading_ts"]).select("region", "reading_ts", "date_sgt", "time_sgt",
                                                             "psi_twenty_four_hourly", "pm25_twenty_four_hourly", "psi_band")
    m = pm.join(last_pm, ["region", "reading_ts"]).select("region", "pm25_one_hourly")
    regions = spark.read.table("silver_haze_regions")
    return p.join(m, "region", "left").join(regions, "region", "left")

@dlt.table(comment="One row per day (SGT): island-wide afternoon heat (hottest and average station peak, stations at Moderate/High) and haze (worst and average 24-hour PSI).")
def gold_daily_summary():
    peaks = (spark.read.table("silver_wbgt_daily_peak").where(f"afternoon_readings >= {MIN_AFTERNOON_READINGS}")
             .groupBy("date_sgt")
             .agg(F.count("*").alias("stations_reporting"),
                  F.round(F.max("afternoon_peak_wbgt_c"), 1).alias("hottest_peak_wbgt_c"),
                  F.round(F.avg("afternoon_peak_wbgt_c"), 2).alias("avg_peak_wbgt_c"),
                  F.count(F.when(F.col("afternoon_peak_wbgt_c") >= WBGT_MODERATE, True)).alias("stations_moderate_or_high"),
                  F.count(F.when(F.col("afternoon_peak_wbgt_c") >= WBGT_HIGH, True)).alias("stations_high")))
    haze = (spark.read.table("silver_psi").groupBy("date_sgt")
            .agg(F.max("psi_twenty_four_hourly").alias("worst_psi_24h"),
                 F.round(F.avg("psi_twenty_four_hourly"), 1).alias("avg_psi_24h")))
    return (peaks.join(haze, "date_sgt", "full")
            .withColumn("hottest_band", wbgt_band(F.col("hottest_peak_wbgt_c")))
            .withColumn("worst_psi_band", psi_band(F.col("worst_psi_24h")))
            .withColumn("month", F.date_format("date_sgt", "yyyy-MM")))
