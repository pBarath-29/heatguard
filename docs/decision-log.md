# HeatGuard — decision log

Shared record of what we learned, what we decided and why, and open questions (requested by the DAISI organisers). Newest entries at the top of each section.

## Decisions

| Date | Decision | Why | Alternatives considered |
|---|---|---|---|
| 14 Oct 2026 | Pipeline `heatguard-pipeline` (Lakeflow, serverless, triggered; source `notebooks/04_pipeline.py`): bronze via Auto Loader → silver with expectations → gold ranked list | One declarative pipeline gives lineage, data-quality metrics and incremental loads with little code | Plain notebooks writing tables |
| 14 Oct 2026 | Heat at subzone level = inverse-distance blend (power 2) of the **3 nearest active WBGT stations** to the subzone centroid; nearest-station distance kept as a confidence signal (max 6.8 km) | 30 stations vs 332 subzones; blending smooths single-station noise without inventing detail | Nearest station only; kriging |
| 14 Oct 2026 | Haze at subzone level = PSI of the **nearest NEA haze region** label (5 regions) | Haze is only published for 5 regions; we don't pretend to finer detail | URA regions (don't match NEA's 5) |
| 14 Oct 2026 | Risk score = 100 × (0.35 heat + 0.15 haze + 0.35 vulnerability + 0.15 access). Heat 0→1 over WBGT 29–34 °C; haze 0→1 over PSI 50–200; access 0→1 over 0–2 km to the nearest CC/library. Vulnerability = weighted percentile ranks (65+ share 0.30, 65+ count 0.20, 1–2 room share 0.20, one-person households 0.15, daily-activity difficulty 0.15). Weights published in `gold_score_weights` | Transparent and adjustable; every row shows its main driver and a plain-English reason | Multiplicative score; ML-learned weights (no outcome data) |
| 14 Oct 2026 | Ranking covers subzones with **≥ 50 residents aged 65+** (216 of 332); planning-area Census rates fall back to the national rate where not published (19 of 216, flagged `pa_data_published = false`) | Avoids tiny or empty subzones topping the list on shares alone | Rank all 332 |
| 14 Oct 2026 | Added haze data: NEA **PSI** and **PM2.5** (hourly, 5 regions) to the live job and the backfill (`raw/psi/`, `raw/pm25/`) | Mentor (Loy, 13 Oct) suggested haze; haze plus heat adds to the strain on seniors, and both are cheap to collect (1 call per day of history). Reverses the 23 Sep decision to drop PM2.5. Haze will be a **factor in the risk score** (not just a warning flag); weighting still to design, at region level (5 regions) | Leave haze out (23 Sep decision); haze as a warning flag only |
| 11 Oct 2026 | **Paused** the live ingestion schedule for now (job kept, unpause when needed) | Save Free Edition quota while building the pipeline; history is already loaded | Keep running every 15 min |
| 11 Oct 2026 | Live ingestion job `heatguard-live-ingest` (job 1098458350267132) runs `01_ingest_live` every 15 min (Asia/Singapore), serverless, 1 retry, no overlapping runs | WBGT updates every 15 min; keeps "Now" tab and forecast inputs fresh; shows judges a real live stream | 30- or 60-min schedule if Free Edition quota becomes a problem |
| 11 Oct 2026 | Skip temperature/humidity history backfill (step 14) for now | Model mainly needs WBGT history + NEA forecast, which we have; saves quota. Live job still collects temperature/humidity going forward | Backfill 2023–2024 yearly files |
| 11 Oct 2026 | Ingest directly from data.gov.sg inside Databricks (scheduled job), no external poller | Day-1 check passed: live APIs, history (`?date=`), datastore and S3 file downloads all reachable from Free Edition serverless | Laptop / GitHub Actions poller uploading to a volume |
| 11 Oct 2026 | Advisory wording model: `databricks-meta-llama-3-3-70b-instruct` (fallback `databricks-gpt-oss-120b`) | Available on our Free Edition workspace; strong multilingual instruction-following | Other listed endpoints (Llama 4 Maverick, Qwen, Gemma) |
| 11 Oct 2026 | Demo workspace = shared team Google account; catalog `workspace`, schema `heatguard`, volume `raw` | One shared workspace keeps all demo assets in one place | Separate workspaces per member |
| 29 Sep 2026 | Actions come from a fixed rulebook; the LLM only rewrites the wording | No data exists on which outreach actions reduce heat illness, so an AI choosing actions would be guessing; rules are transparent and easy for coordinators to adjust | LLM-chosen actions |
| 29 Sep 2026 | Outputs are area-level only (subzone); no personal data | Competition rules forbid personal data; coordinators already hold client lists, so HeatGuard says *where and when* and the team's own list says *who* | Block- or person-level targeting |
| 29 Sep 2026 | Cool spaces = Community Clubs + public libraries | Both are air-conditioned and have location datasets on data.gov.sg; parks and hawker centres are outdoors and hot at 2–4 pm | Parks, hawker centres, the 2016 Senior Activity Centre layer |
| 29 Sep 2026 | Use Census 2020 at its real granularity: 65+ and dwelling type by subzone; one-person households and daily-activity difficulty by planning area (all ages) | Those are the only open tables; we state the limit instead of overclaiming "seniors living alone per subzone" | HDB elderly data (town-level, ends 2018) |
| 23 Sep 2026 | Main heat signal = NEA WBGT (30 stations, 15-min, Feb 2025+) with NEA's own Low / Moderate / High bands | Official heat-stress measure; reusing NEA's bands aids adoption | Air temperature only (16 stations) |
| 23 Sep 2026 | Dropped PM2.5 from the core design | Hourly, 5 regions only; adds little to heat risk | Second live stream (kept as optional) |
| 23 Sep 2026 | Chose problem B1 HeatGuard | Strongest data fit, policy timing (Year of Climate Adaptation, super-aged 2026), originality; see `reports/DAISI problem statement selection.md` | A1 SilverWatch (runner-up) |

## What we learned

- 14 Oct 2026: **First pipeline run.** Expectations dropped 2,883 `NA` and 74 implausible (< 20 °C) WBGT readings out of 1,018,725; NEA's band matched our cut-offs on every row; 36 station-days had fewer than 12 afternoon readings (flagged). All 332 subzones matched the Census by name; 152 cool spaces (125 CCs + 27 libraries). First ranked list: 216 subzones, top = Telok Blangah Rise (Bukit Merah).
- 14 Oct 2026: **There is a haze episode right now:** 24-hour PSI above 100 ("Unhealthy") somewhere in Singapore every day since 5 Oct, peaking at 192 on 9 Oct. 1,532 region-hours of Unhealthy PSI in the history; never Very unhealthy.

- 14 Oct 2026: **Haze backfill complete.** PSI and PM2.5: 636 of 636 days each (16 Jan 2025 → 13 Oct 2026), no gaps; 24 hourly records per day for 5 regions (north, south, east, west, central). Run took ~32 min on serverless.

- 11 Oct 2026: **Backfill complete.** WBGT: 633 days (16 Jan 2025 → 10 Oct 2026), ~1.01M station readings. 24-hour forecast: 632 days (missing 2025-07-20).
  - **NEA heat-stress bands, measured from the data:** Low < 31.0 °C, Moderate 31.0–32.9 °C, High ≥ 33.0 °C. We use these exact cut-offs.
  - **High is rare:** 2,056 High readings (0.2%), 40,175 Moderate (4%). Peaks Apr–Jun and Sep–Oct; highest 36.6 °C (Sep 2026). The model must handle this imbalance.
  - **Messy data found:** 2,879 readings (0.3%) have `NA` instead of a value; 21 days have fewer than 96 records (first day 16 Jan 2025 has only 2); one reading as low as 14.3 °C. Pipeline quality checks must drop these.
  - **Network grew** from 8 stations (Jan 2025) → 15 (Sep 2025) → 20 (Jan 2026) → 27 (Apr 2026) → 30 (Aug 2026). Older history covers fewer places.

- 11 Oct 2026: WBGT history on the API starts **16 Jan 2025** (not Feb 2025 as first thought); days with no data return error code 17 ("Data not found"), which the backfill treats as empty. Only **8 stations** reported in early 2025 vs **30** today, so early history covers fewer places.
- 11 Oct 2026: Census "household size" and "daily-activity difficulty" tables cover only the **30 largest planning areas** (plus a national total), not all 55. Age and dwelling-type tables cover all subzones; "-" in them means zero.
- 11 Oct 2026: Static layers: 332 subzones (MP2019), 125 Community Clubs, 27 public libraries. CC/library details sit inside an HTML table in the GeoJSON `Description` field and must be unpacked.

- 11 Oct 2026: Day-1 setup check (notebook `00_setup`): all data.gov.sg endpoints OK (WBGT live + history, air temperature, humidity, 24-hour forecast, datastore, S3 file download); H3, `st_point` and `st_distancesphere` work on serverless; 12 serving endpoints available (Llama 3.3 70B, Llama 4 Maverick, GPT-OSS 20B/120B, Qwen, Gemma, DeepSeek, embedding models).
- 23 Sep 2026: Several datasets in the brief differ from their descriptions (16 temperature stations, not ~50; PM2.5 hourly by 5 regions; HDB elderly data is town-level and ends 2018).
- 23 Sep 2026: The data.gov.sg API allows only 3–4 rapid calls without a key; an API key is needed for backfill.

## Challenges and open questions

- [x] Can Databricks Free Edition serverless reach `api-open.data.gov.sg`? **Yes (11 Oct)**
- [x] Which Foundation Model API model is available on Free Edition? **12 endpoints; using Llama 3.3 70B (11 Oct)**
- [x] Get a data.gov.sg API key and store it as a Databricks secret: **Production key created 11 Oct; stored as secret `heatguard/datagov_api_key` via Databricks CLI (profile `heatguard`); header `x-api-key` confirmed (15/15 rapid calls OK)**
- [ ] Validate the action rulebook against NEA heat-stress advisory guidance and, ideally, an AAC coordinator
- [ ] Is SingStat's June 2025 planning-area population file downloadable, to refresh Census 2020?
