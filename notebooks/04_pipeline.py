# Databricks notebook source
# MAGIC %md
# MAGIC # 04 · HeatGuard pipeline (Lakeflow Declarative Pipeline)
# MAGIC
# MAGIC This notebook is the source of the **`heatguard-pipeline`** pipeline. Don't run it cell by cell; start the pipeline instead.
# MAGIC
# MAGIC | Layer | Tables | What happens |
# MAGIC |---|---|---|
# MAGIC | **Bronze** | `bronze_wbgt`, `bronze_forecast_24h`, `bronze_psi`, `bronze_pm25`, `bronze_air_temperature`, `bronze_humidity` | Auto Loader picks up new JSON Lines files from the `raw` volume (backfill + live job). Kept as received. |
# MAGIC | **Silver** | `silver_wbgt`, `silver_wbgt_stations`, `silver_wbgt_daily_peak`, `silver_psi`, `silver_pm25`, `silver_haze_regions`, `silver_forecast_24h`, `silver_forecast_periods`, `silver_air_temperature`, `silver_humidity`, `silver_subzones`, `silver_cool_spaces`, `silver_census_subzone`, `silver_census_planning_area` | One row per reading / place, typed, de-duplicated, with **expectations** that drop bad rows and count them. |
# MAGIC | **Gold** | `gold_subzone_station_weights`, `gold_subzone_profile`, `gold_subzone_conditions`, `gold_checkin_list`, `gold_score_weights`, `gold_rulebook` | Stations → subzones, distance to the nearest cool space, vulnerability score, and the ranked check-in list with reasons and actions. |
# MAGIC
# MAGIC The Census bronze tables, subzone map and cool spaces come from `03_load_static` (regular tables, read here by full name).
# MAGIC
# MAGIC **Heat input (for now):** the latest observed afternoon peak WBGT. The forecast model replaces it with tomorrow's predicted peak.

# COMMAND ----------

import dlt
from pyspark.sql import functions as F, Window as W

CATALOG, SCHEMA = "workspace", "heatguard"
RAW = f"/Volumes/{CATALOG}/{SCHEMA}/raw"

def static(name):
    """Tables written by 03_load_static (not managed by this pipeline)."""
    return spark.read.table(f"{CATALOG}.{SCHEMA}.{name}")

# NEA heat-stress bands (WBGT, °C), measured from the data on 11 Oct: Low < 31, Moderate 31–32.9, High ≥ 33
WBGT_MODERATE, WBGT_HIGH = 31.0, 33.0
# NEA PSI bands (24-hour PSI)
PSI_BANDS = [(50, "Good"), (100, "Moderate"), (200, "Unhealthy"), (300, "Very unhealthy")]

AFTERNOON_HOURS = (12, 17)       # 12:00–17:59 SGT: when heat stress peaks and outreach matters
NEAREST_STATIONS = 3             # stations blended per subzone (inverse-distance weighting)
ACTIVE_STATION_DAYS = 7          # a station counts as active if it reported in the last 7 days of data
MIN_SENIORS = 50                 # subzones with fewer residents aged 65+ are left out of the ranking
FAR_FROM_COOL_SPACE_KM = 2.0     # at or beyond this distance, the access score is at its maximum

# Risk score = 100 × weighted sum of four 0–1 components (shown on the dashboard via gold_score_weights)
SCORE_WEIGHTS = {
    "heat":          (0.35, "Afternoon WBGT: 0 at 29 °C, 1 at 34 °C and above"),
    "haze":          (0.15, "24-hour PSI: 0 at 50 (Good) or below, 1 at 200 (Very unhealthy) and above"),
    "vulnerability": (0.35, "Census vulnerability score of the subzone (see VULNERABILITY_WEIGHTS)"),
    "access":        (0.15, f"Distance to the nearest Community Club or library: 0 at the door, 1 at {FAR_FROM_COOL_SPACE_KM:g} km or more"),
}
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

# COMMAND ----------

# MAGIC %md
# MAGIC ## Bronze: raw files → streaming tables (Auto Loader)
# MAGIC Explicit schemas keep history and live files (slightly different top-level fields) in one table. Numbers stay as text until silver.

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
# MAGIC ## Silver: weather and haze

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
@dlt.expect("enough_afternoon_readings", "afternoon_readings >= 12")
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

@dlt.table(comment="NEA 24-hour forecast: one row per issued forecast (temperature, humidity, wind and outlook for the whole island).")
@dlt.expect_or_drop("has_valid_period", "valid_start_ts IS NOT NULL")
def silver_forecast_24h():
    return (spark.read.table("bronze_forecast_24h")
            .select(F.coalesce("timestamp", "updatedTimestamp").cast("timestamp").alias("issued_ts"),
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

@dlt.table(comment="NEA 24-hour forecast by period (about 6 hours) and region: outlook code and text.")
def silver_forecast_periods():
    return (spark.read.table("bronze_forecast_24h")
            .select(F.coalesce("timestamp", "updatedTimestamp").cast("timestamp").alias("issued_ts"),
                    F.explode("periods").alias("p"))
            .select("issued_ts",
                    F.col("p.timePeriod.start").cast("timestamp").alias("period_start_ts"),
                    F.col("p.timePeriod.end").cast("timestamp").alias("period_end_ts"),
                    F.col("p.timePeriod.text").alias("period_text"),
                    F.explode("p.regions").alias("region", "o"))
            .select("issued_ts", "period_start_ts", "period_end_ts", "period_text", "region",
                    F.col("o.code").alias("forecast_code"), F.col("o.text").alias("forecast_text"))
            .dropDuplicates(["issued_ts", "period_start_ts", "region"]))

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

@dlt.table(comment="Air temperature (°C): one row per station per minute-level reading collected by the live job.")
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
# MAGIC ## Gold: subzone profile, conditions and the ranked check-in list

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
                         F.round(F.min("d"), 2).alias("cool_space_km"),
                         F.count(F.when(F.col("d") <= 1.0, True)).alias("cool_spaces_within_1km")))

    nearest_station = (spark.read.table("gold_subzone_station_weights").where("station_rank = 1")
                       .select("subzone_name", F.col("station_name").alias("nearest_wbgt_station"),
                               F.col("distance_km").alias("nearest_wbgt_station_km")))

    regions = spark.read.table("silver_haze_regions")
    haze_region = (sz.select("subzone_name", "centroid_latitude", "centroid_longitude")
                   .crossJoin(regions.select("region", F.col("latitude").alias("r_lat"), F.col("longitude").alias("r_lon")))
                   .withColumn("d", distance_km("centroid_longitude", "centroid_latitude", "r_lon", "r_lat"))
                   .groupBy("subzone_name").agg(F.min_by("region", "d").alias("haze_region")))

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

@dlt.table(comment="Latest conditions per subzone: heat (inverse-distance blend of the nearest WBGT stations) for the latest reading and the latest afternoon peak, plus haze for the subzone's NEA region.")
def gold_subzone_conditions():
    weights = spark.read.table("gold_subzone_station_weights")
    wbgt = spark.read.table("silver_wbgt")

    latest_ts = wbgt.agg(F.max("reading_ts").alias("ts"))
    latest = (wbgt.join(latest_ts, wbgt.reading_ts == latest_ts.ts)
              .select("station_id", F.col("wbgt_c").alias("v"), F.col("reading_ts").alias("latest_reading_ts")))

    peaks = spark.read.table("silver_wbgt_daily_peak").where("afternoon_readings >= 12")
    peak_day = peaks.agg(F.max("date_sgt").alias("d"))
    peak = (peaks.join(peak_day, peaks.date_sgt == peak_day.d)
            .select("station_id", F.col("afternoon_peak_wbgt_c").alias("v"), F.col("date_sgt").alias("peak_date_sgt")))

    def blend(values, name, extra):
        # Re-normalise weights over stations that actually reported
        j = weights.join(values, "station_id")
        return (j.groupBy("subzone_name")
                .agg((F.sum(F.col("weight") * F.col("v")) / F.sum("weight")).alias(name),
                     F.max(extra).alias(extra)))

    heat = (blend(latest, "wbgt_latest_c", "latest_reading_ts")
            .join(blend(peak, "wbgt_afternoon_peak_c", "peak_date_sgt"), "subzone_name", "full")
            .withColumn("wbgt_latest_c", F.round("wbgt_latest_c", 1))
            .withColumn("wbgt_afternoon_peak_c", F.round("wbgt_afternoon_peak_c", 1))
            .withColumn("heat_band_latest", wbgt_band(F.col("wbgt_latest_c")))
            .withColumn("heat_band_afternoon_peak", wbgt_band(F.col("wbgt_afternoon_peak_c"))))

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

@dlt.table(comment="Score weights used by gold_checkin_list and the vulnerability score (shown on the dashboard).")
def gold_score_weights():
    rows = ([("risk_score", k, w, d) for k, (w, d) in SCORE_WEIGHTS.items()]
            + [("vulnerability_score", k, w, d) for k, (w, d) in VULNERABILITY_WEIGHTS.items()])
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

@dlt.table(comment="Ranked check-in list: in-scope subzones (≥ 50 residents aged 65+) ranked by risk score (heat, haze, vulnerability, access to cool spaces), with the reason and the rulebook action. "
                   "Heat basis for now: latest observed afternoon peak WBGT (to be replaced by tomorrow's forecast).")
@dlt.expect("has_heat", "heat_component IS NOT NULL")
def gold_checkin_list():
    p = spark.read.table("gold_subzone_profile").where("in_scope")
    c = spark.read.table("gold_subzone_conditions").drop("haze_region")
    rules = spark.read.table("gold_rulebook")
    heat_rules = rules.where("trigger = 'heat'").select(F.col("level").alias("heat_band"), F.col("action").alias("heat_action"))
    haze_rules = rules.where("trigger = 'haze'").select(F.col("level").alias("psi_band"), F.col("action").alias("haze_action"))

    df = (p.join(c, "subzone_name", "left")
          .withColumn("heat_wbgt_c", F.col("wbgt_afternoon_peak_c"))
          .withColumn("heat_band", F.col("heat_band_afternoon_peak"))
          .withColumn("heat_basis", F.concat(F.lit("Observed afternoon peak on "), F.date_format("peak_date_sgt", "d MMM yyyy")))
          .withColumn("heat_component", F.round(clamp01((F.col("heat_wbgt_c") - 29) / 5), 4))
          .withColumn("haze_component", F.round(clamp01((F.col("psi_twenty_four_hourly") - 50) / 150), 4))
          .withColumn("haze_component", F.coalesce("haze_component", F.lit(0.0)))
          .withColumn("access_component", F.round(clamp01(F.col("cool_space_km") / FAR_FROM_COOL_SPACE_KM), 4)))
    df = df.withColumn("vulnerability_component", F.col("vulnerability_score"))
    contrib = {k: F.lit(w) * F.col(f"{k}_component") for k, (w, _) in SCORE_WEIGHTS.items()}
    df = df.withColumn("risk_score", F.round(100 * sum(contrib.values()), 1))

    # Main driver = the component contributing most points
    drivers = F.array(*[F.struct(v.alias("pts"), F.lit(k).alias("name")) for k, v in contrib.items()])
    df = df.withColumn("main_driver", F.array_max(drivers)["name"])

    pct = lambda col: F.concat(F.round(F.col(col) * 100, 0).cast("int").cast("string"), F.lit("%"))
    df = df.withColumn("reason", F.concat_ws(" · ",
        F.concat(F.lit("Heat: WBGT "), F.col("heat_wbgt_c").cast("string"), F.lit(" °C ("), F.col("heat_band"), F.lit(")")),
        F.concat(F.lit("Seniors: "), F.format_number("pop_65_plus", 0), F.lit(" aged 65+ ("), pct("pct_65_plus"), F.lit(" of residents)")),
        F.when(F.col("pct_1_2_room") >= 0.05, F.concat(pct("pct_1_2_room"), F.lit(" in 1–2 room HDB flats"))),
        F.concat(F.lit("Nearest cool space: "), F.col("nearest_cool_space"), F.lit(" ("), F.col("cool_space_km").cast("string"), F.lit(" km)")),
        F.concat(F.lit("Haze: PSI "), F.col("psi_twenty_four_hourly").cast("int").cast("string"), F.lit(" ("), F.col("psi_band"), F.lit(")"))))

    df = (df.join(heat_rules, "heat_band", "left").join(haze_rules, "psi_band", "left")
            .withColumn("action", F.concat_ws(" ", "heat_action", "haze_action"))
            .withColumn("rank", F.row_number().over(W.orderBy(F.col("risk_score").desc_nulls_last(), F.col("pop_65_plus").desc()))))
    return df.select(
        "rank", "subzone_name", "planning_area", "risk_score", "main_driver", "reason", "action",
        "heat_wbgt_c", "heat_band", "heat_basis", "psi_twenty_four_hourly", "psi_band", "pm25_one_hourly",
        "pop_65_plus", "pct_65_plus", "pop_75_plus", "pct_1_2_room", "pa_pct_one_person", "pa_pct_difficulty", "pa_data_published",
        "vulnerability_score", "nearest_cool_space", "nearest_cool_space_type", "cool_space_km",
        "nearest_wbgt_station", "nearest_wbgt_station_km", "haze_region",
        "heat_component", "haze_component", "vulnerability_component", "access_component",
        "centroid_latitude", "centroid_longitude")
