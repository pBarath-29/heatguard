DATASETS YOU PLAN TO USE
========================

All from data.gov.sg (dataset ID in brackets):

Heat hazard (live + history)
1. Wet Bulb Globe Temperature (WBGT) Observations, NEA: live API, 30 stations, every 15 min, history from Feb 2025. Our forecast target and live heat signal [d_87884af1f85d702d4f74c6af13b4853d]
2. Air Temperature across Singapore, NEA: live API + yearly historical files 2016–2024, used as model features and for longer training history [d_66b77726bbae1b33f218db60ff5861f0]
3. Relative Humidity across Singapore, NEA: live API + historical files [d_2d3b0c4da128a9a59efca806441e1429]
4. 24-hour Weather Forecast and 4-day Weather Outlook, NEA: NEA's own forecast as a model input [d_ce2eb1e307bda31993c533285834ef2b, d_f131f6e343bf8168e4057a04c4326a0a]

Who lives there (vulnerability)
5. Census of Population 2020: Resident Population by Planning Area/Subzone, Age Group and Sex, SingStat: seniors 65+ per subzone [d_d95ae740c0f8961a0b10435836660ce0]
6. Census of Population 2020: Resident Population by Planning Area/Subzone and Type of Dwelling, SingStat: share in 1–2-room flats [d_7f243956483d5901f237e6f87b096636]
7. Census of Population 2020: Resident Households by Planning Area and Household Size, SingStat: one-person households [d_0ef47f84a0776b27010b242038ea2c6b]
8. Census of Population 2020: Resident Households by Planning Area and Presence of a Member with Difficulty in Basic Activities, SingStat [d_0145fb635a7112d530c4edb0e814b8a9]

Map and cool spaces
9. Master Plan 2019 Subzone Boundary, URA: map shapes for ~330 subzones [d_8594ae9ff96d0c708bc2af633048edfb]
10. Community Clubs, People's Association: air-conditioned cool rest spots [d_f706de1427279e61fe41e89e24d440fa]
11. Libraries, NLB: air-conditioned public spaces [d_27b8dae65d9ca1539e14d09578b17cbf]

Known limits (stated openly): Census 2020 is the latest subzone-level source; one-person households and daily-activity difficulty are all-ages and planning-area level only; heat stress is measured at 30 stations, so subzone values are interpolated.


INTENDED DATABRICKS ARCHITECTURE
================================

One end-to-end pipeline on Databricks Free Edition:

1. Ingestion: a scheduled Lakeflow Job calls NEA's live data.gov.sg APIs (WBGT, temperature, humidity, forecasts) every 15 minutes and lands raw JSON in a Unity Catalog Volume. Auto Loader incrementally loads it into bronze Delta tables. Historical files (2016–2024) and Census/URA/CC/library files are loaded once.

2. Transformation: a Lakeflow Declarative Pipeline builds silver and gold Delta tables. Data-quality expectations drop missing, duplicate and physically impossible readings. Spatial SQL and H3 functions map station readings to subzones (distance-weighted) and compute each subzone's distance to the nearest Community Club or library.

3. Machine learning: MLflow tracks a next-day peak heat-stress forecast per station (gradient-boosted model on recent readings plus NEA's forecast), always compared against a "tomorrow = today" baseline. A transparent vulnerability score per subzone uses published weights. Priority = NEA heat band × vulnerability.

4. Analytics and AI: an AI/BI dashboard with three tabs (Now: live heat stress; Tomorrow: subzone risk map and ranked check-in list with reason and suggested action; Why here?: drivers of each area's rank and past forecast accuracy). A Genie space lets coordinators ask plain-English questions. A Foundation Model API step rewrites the rule-based action into a ready-to-send advisory (wording only; it never decides the action).

5. Governance: Unity Catalog holds all tables with lineage from raw API call to final list, documented sources and known gaps. Outputs are area-level only, with no personal data.

Built to fit Free Edition limits: one Lakeflow pipeline, one serverless SQL warehouse.
