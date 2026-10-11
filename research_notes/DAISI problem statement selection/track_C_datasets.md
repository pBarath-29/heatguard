# Track C (Liveable & Inclusive City): Data Availability and Feasibility (C1 FlatFair, C2 MoveEasy, C3 KopilamAI)

Method note: I checked every dataset below directly against the live data.gov.sg APIs on 23 Sep 2026. I pulled the full catalogue (4,629 datasets) from `api-production.data.gov.sg/v2/public/api/datasets`, then downloaded each key file with `api-open.data.gov.sg/v1/public/api/datasets/<id>/poll-download` and profiled it in Python. Row counts, attribute names and last-update dates therefore come from the downloaded files, not from dataset page descriptions. The unauthenticated data.gov.sg download API gave repeated **HTTP 429 (Too Many Requests)** errors after a few calls, so ingestion code needs retry/backoff logic, or the team should register for an API key. Dataset page URLs follow the pattern `https://data.gov.sg/datasets/<id>/view`.

## C1 FlatFair: resale data, income benchmarks, geocoding, saturation

### Takeaway
C1 has the best data of the three problems. The resale dataset is large (241,031 rows), clean, updated daily and complete through Sep 2026. Official income-by-dwelling-type and median-price-by-town tables close the affordability-index gap with no extra work. The main risk is that the idea is very saturated: dozens of GitHub and Kaggle HDB price predictors and dashboards already exist. To stand out, a team would need something beyond them, such as the affordability index, a fair-value estimator, or Databricks-native governance and a production pipeline.

### Cited Findings
- **Resale dataset `d_8b84c4ee58e3cfc0ece0d773c8ca6abc` exists.** Its official name is "Resale flat prices based on registration date from Jan-2017 onwards". It is managed by HDB, in CSV format (~23.8 MB). Coverage runs from 2017-01 to 2026-09, and it was last updated 2026-09-23 (it refreshes more or less daily). — [data.gov.sg metadata API](https://api-production.data.gov.sg/v2/public/api/datasets/d_8b84c4ee58e3cfc0ece0d773c8ca6abc/metadata)
- **Row count and columns:** the datastore API reports `total: 241031` rows. There are 11 columns: `month` (YYYY-MM), `town`, `flat_type`, `block`, `street_name`, `storey_range` (bands such as "10 TO 12"), `floor_area_sqm`, `flat_model`, `lease_commence_date`, `remaining_lease`, `resale_price`. — [datastore_search API](https://data.gov.sg/api/action/datastore_search?resource_id=d_8b84c4ee58e3cfc0ece0d773c8ca6abc&limit=2)
- **My profiling of the full download** found:
  - 26 towns, 21 flat models and 9,749 unique block+street addresses.
  - No nulls in any column.
  - Flat-type mix: 4-room 102,428; 5-room 58,969; 3-room 57,264; Executive 17,129; 2-room 5,063; Multi-gen 90; 1-room 88.
  - Yearly volume ranges from 20.5k (2017) to 29.1k (2021); 2026 has 18,964 rows up to September.
  - `floor_area_sqm` and `lease_commence_date` are typed as Text and need casting.
  - `remaining_lease` comes in two formats: "49 years 10 months" in 221,250 rows and "NN years" in 19,781 rows. This mixed format is a real "schema evolution" cleaning task that can be shown in the pipeline.
  - Town-month cells: 3,039 in total, of which 62 have fewer than 5 transactions (Central Area, Marine Parade and Bukit Timah are thin: Bukit Timah has only 588 rows over 9.7 years).
  - Town × flat_type × month cells: 13,251, of which 3,665 have fewer than 5 transactions.

  — [data.gov.sg dataset page](https://data.gov.sg/datasets/d_8b84c4ee58e3cfc0ece0d773c8ca6abc/view)
- **The data has no geocoordinates, only block and street name.** Geocoding would require OneMap. When I tested OneMap Search (`/api/common/elastic/search`) without a token on 23 Sep 2026, it still returned lat/long but added the warning "Authentication token missing. Please create an account and generate or renew your API Token." Enforcement appears to be imminent or partial. — [OneMap auth docs](https://www.onemap.gov.sg/apidocs/authentication); [Shesh's blog on OneMap](https://www.sheshbabu.com/posts/exploring-singapore-onemap-api/)
- OneMap tokens come from POST `getToken` with an email and password, and each token is valid for 3 days. — [OneMap getToken wrapper docs](https://rdrr.io/cran/onemapsgapi/man/get_token.html)
- **Alternative to geocoding: `HDB Property Information` (`d_17f5382f26140b1fdae0ba2ef6239d2f`).** It has 13,357 rows, one per block (blk_no, street, max_floor_lvl, year_completed, `market_hawker` Y/N flag, dwelling-unit counts by flat type, town code), but no coordinates. `HDB Existing Building` (`d_16b157c52ed637edd6ba1232e026258d`, GeoJSON, updated 2026-06) holds building footprints that could be joined on block and street to get centroids. I did not download that layer. — [HDB Property Information](https://data.gov.sg/datasets/d_17f5382f26140b1fdae0ba2ef6239d2f/view); [HDB Existing Building](https://data.gov.sg/datasets/d_16b157c52ed637edd6ba1232e026258d/view)
- **Income benchmark, national by dwelling type:** "Average Monthly Household Employment Income (Excluding Employer CPF Contributions) Among Resident Employed Households by Type of Dwelling, 2000 - 2025" (`d_ce5d8bb5c34f6b78b5b2f1fab09ccbce`). It is annual, with columns HDB 1-2 room, 3-room, 4-room, 5-room/Exec, Condo and Landed. 2025 values: 1-2 room 3,976; 3-room 7,570; 4-room 11,097; 5-room/Exec 13,887. It maps directly onto the resale `flat_type`, so a price-to-income ratio by flat type and year is easy to build. A variant including employer CPF is `d_917a2a8bb57d96d48bafc3ab0baa2b6e`. — [data.gov.sg](https://data.gov.sg/datasets/d_ce5d8bb5c34f6b78b5b2f1fab09ccbce/view)
- The 4-room figure of about $11,097 in 2025 is corroborated by secondary reporting, which puts the national median household income from work (excluding employer CPF) at $10,591 in 2025. — [Dollars and Sense](https://dollarsandsense.sg/much-money-singapore-households-really-earn-based-flat-types-household-members/)
- **Income benchmark, by planning area:** only census-year snapshots exist. "Resident Households by Planning Area of Residence and Monthly Household Income from Work (Census of Population 2020)" (`d_4e150bbd35c3145ea43019212c7b46c2`) gives household counts in income bands per planning area. The earlier equivalent is GHS 2015 (`d_e2e2421777b5c2b6aff5db721d3dfabc`). Neither has an annual series by town. — [Census 2020 table](https://data.gov.sg/datasets/d_4e150bbd35c3145ea43019212c7b46c2/view)
- **Other useful HDB tables:**
  - "Median Resale Prices for Registered Applications by Town and Flat Type" (`d_b51323a474ba789fb4cc3db58a3116d4`): quarterly, 2007-Q2 to 2026-Q2, 12,012 rows. Missing values appear as "na" and "-". This gives a longer history for training the forecast.
  - "HDB Resale Price Index (1Q2009=100), Quarterly" (`d_14f63e595975691e7c24a27ae4c07c79`): 1990-Q1 onwards.
  - Older transaction files go back to 1990: `d_ea9ed51da2787afaf8e51f827c304208` (2015–2016), `d_2d5ff9ea31397b66239f245f57751537` (Mar 2012–2014), `d_43f493c6c50d54243cc1eab0df142d6a` (2000–Feb 2012) and `d_ebc5ab87086db484f88045b47411ebc5` (1990–1999).

  — [Median resale by town](https://data.gov.sg/datasets/d_b51323a474ba789fb4cc3db58a3116d4/view); [RPI](https://data.gov.sg/datasets/d_14f63e595975691e7c24a27ae4c07c79/view)
- **BTO supply (stretch goal):** I found no BTO launch or supply dataset in the data.gov.sg catalogue (searches for "bto" and "building under construction" returned 0 hits). HDB Property Information's `year_completed` field is the only proxy. — [data.gov.sg catalogue API](https://api-production.data.gov.sg/v2/public/api/datasets)
- **Saturation (Kaggle):** there are multiple HDB resale datasets and notebooks (for example "Singapore Resale Flat Prices (2017-2024)"), an HDB Resale Price Prediction Kaggle competition, and many regression notebooks. — [Kaggle dataset](https://www.kaggle.com/datasets/darrylljk/singapore-hdb-resale-flat-prices-2017-2024); [Kaggle competition](https://www.kaggle.com/competitions/hdb-resale-price-prediction); [Kaggle notebook](https://www.kaggle.com/code/davegn/prediction-of-resale-hdb-prices-regression-model)
- **Saturation (GitHub):**
  - Many predictor repos, including coursework (NUS CS5228, GA DSI projects).
  - A Streamlit app with R² 0.96 and $20k MAE.
  - An existing interactive dashboard covering 311,424 transactions (2012–2025) with a budget-driven "where can I buy" tool.
  - A repo on "resale price drivers and 2031 forecast" that explicitly frames affordability.

  — [tanfiona/HDBResalePrice](https://github.com/tanfiona/HDBResalePrice); [teyang-lau/HDB_Resale_Prices](https://github.com/teyang-lau/HDB_Resale_Prices); [jeremydevdesign/sg-hdb-resale-dashboard](https://github.com/jeremydevdesign/sg-hdb-resale-dashboard); [chetankish 2031 forecast](https://github.com/chetankish/singapore-hdb-resale-price-drivers-2031-forecast); [eeshawn11 dashboard](https://github.com/eeshawn11/HDB_Resale_Dashboard)

### Inferences
- **Every "winning demo" item can be built from open data:**
  - Dashboard: the resale CSV alone.
  - 6-month town-level forecast: monthly town median series, 117 months per town (2017-01 to 2026-09), extendable back to 1990 or to 2007 via the quarterly medians.
  - Affordability index: resale price ÷ (annual income by flat type × 12), from `d_ce5d8bb5…`.
  - Pipeline story: mixed `remaining_lease` formats, text-typed numerics and thin cells.
- **Forecasting at town × flat_type is noisy,** because 28% of monthly cells have fewer than 5 transactions. Forecasting at town level (as the brief asks) or by quarter is more robust. Seasonal naive, Prophet or LightGBM models run fine on serverless compute because the data is small.
- **Scale is not an issue:** 241k rows is tiny for a 2X-Small SQL warehouse and serverless notebooks.
- **The 2024 flat classification change (Standard/Plus/Prime) is not visible in the resale data.** There is no classification column, and the first Plus/Prime flats will not reach MOP and resale for years. I did not verify this directly; it is an inference from the unchanged schema. Teams should not promise a classification-impact analysis.
- **Differentiation is essential** given the saturation. A plain "predict price" demo will look like the many GA/Kaggle projects. Better angles: a fair-value estimator with prediction intervals, an income-anchored affordability index, and Unity Catalog lineage plus DLT expectations.

### Gaps
- No annual income series at town or planning-area level (only Census 2020 and GHS 2015 snapshots), so the affordability index is national by flat type unless the team uses the 2020 planning-area income distribution.
- I could not verify how strictly OneMap now enforces tokens on Search; the tokenless call worked on 23 Sep 2026 but carried a warning.
- I did not verify the contents of the "HDB Annual Report 2025" (a PDF, not a dataset) or the problem statement's "Total Population by Planning Area" (see C3).
- I found no evidence of prior DAISI or Databricks hackathon winners on this topic, only general GitHub and Kaggle saturation.

## C2 MoveEasy: polyclinics, AAC locations, bus/MRT, cycling, ridership, elderly density

### Takeaway
C2 has the weakest data of the three, and the gaps hit its core demo items directly:
- **AAC locations:** the brief lists an MSF dataset, but on data.gov.sg it exists only as national annual counts. The only point layer is a stale 2016 "Eldercare Services" file of senior activity centres and nursing homes.
- **Polyclinics:** no complete current polyclinic layer exists; the MOH vaccination-polyclinic file has only 8 points.
- **Elderly population:** "HDB Elderly Population" stops at 2018 and is by HDB town, not planning area.
- **Ridership:** national annual figures only.

Transport geometry, on the other hand, is excellent and needs no key: 5,205 bus stops, 613 MRT exits, 8,523 cycling segments and the MP25 cycling layer. C2 is buildable only if the team spends real time assembling AAC and polyclinic locations from other sources (maps.gov.sg, OneMap themes or AIC listings, then geocoding).

### Cited Findings
- **Cycling Path Network (GEOJSON), `d_8f468b25193f64be8a16fa7d8f60f553`, LTA.** It is current (last updated 2026-07-14). My download has 8,523 features (8,520 LineStrings and 3 MultiLineStrings), totalling about 433 km. Attributes: `CYL_PATH` (town name, 35 values), `AGENCY_MAINT`, `SHAPE_1.LEN`. Coordinates are WGS84 lon/lat. — [data.gov.sg](https://data.gov.sg/datasets/d_8f468b25193f64be8a16fa7d8f60f553/view)
- **Related cycling layer:** "HDB Cycling Paths Under-Construction (GEOJSON)" (`d_9e363d0eb7910dc7f53c44e4fe654586`, updated 2026-09-04). — [data.gov.sg](https://data.gov.sg/datasets/d_9e363d0eb7910dc7f53c44e4fe654586/view)
- **MP25 cycling layer exists.** "Master Plan 2025 SDCP Cycling Network layer" (`d_8fd4e04e7058ee19521d123caf28a855`, URA, GeoJSON, ~12 MB) has 4,567 features. Attribute `PRP_STATUS` is PLANNED (3,828) or EXISTING (739), which directly supports the "MP25 overlay of future gains" stretch goal. The MP25 Park Connector Line layer is `d_cebde179d5cd6b85be36d618c8fe3b85`. — [data.gov.sg](https://data.gov.sg/datasets/d_8fd4e04e7058ee19521d123caf28a855/view)
- **Bus stops are on data.gov.sg, no key needed.** "LTA Bus Stop" (`d_3f172c6feb3f4f92a2f47d93eed2908a`, GeoJSON, updated 2026-09-20) has 5,205 points with `BUS_STOP_NUM` and `BUS_ROOF_NUM`. It has no stop names or served routes; those come from the LTA DataMall `BusStops` and `BusRoutes` APIs, which need an AccountKey. — [data.gov.sg](https://data.gov.sg/datasets/d_3f172c6feb3f4f92a2f47d93eed2908a/view); [LTA DataMall API User Guide v6.9](https://datamall.lta.gov.sg/content/dam/datamall/datasets/LTA_DataMall_API_User_Guide.pdf)
- **MRT exits:** "LTA MRT Station Exit (GEOJSON)" (`d_b39d3a0871985372d7e1637193335da5`, updated 2026-09-16) has 613 points with `STATION_NA` and `EXIT_CODE`. MP25 Rail Station layer: `d_2c06c9fe8ae724b5d33efa1f203e2c38`. — [data.gov.sg](https://data.gov.sg/datasets/d_b39d3a0871985372d7e1637193335da5/view)
- **LTA DataMall static geospatial datasets** (bus stop location, train station, train station exit, cycling path, covered linkway) download as SHP zips with no key mentioned. The dynamic APIs need an API AccountKey that is unique to each user. — [LTA DataMall static data](https://datamall.lta.gov.sg/content/datamall/en/static-data.html); [LTA DataMall dynamic data](https://datamall.lta.gov.sg/content/datamall/en/dynamic-data.html)
- **Ridership granularity is national annual only.** "Public Transport Operation And Ridership, Annual" (`d_ba615ec4cc5d9f5b7800ad82057f36f1`, SingStat, 1990–2025) is a wide table with average daily ridership for MRT, LRT and public bus plus rail length and km operated. 2025 average daily ridership: MRT 3,490k; bus 3,841k. It has no route, stop or area breakdown. The LTA equivalent is `d_75248cf2fbf340de6a746dc91ec9223c` (1995–2024). — [data.gov.sg](https://data.gov.sg/datasets/d_ba615ec4cc5d9f5b7800ad82057f36f1/view)
- **Stop-level passenger volume** (the monthly "Passenger Volume by Bus Stops / Origin-Destination" files) is available only through the LTA DataMall API with a key; it is not among the static downloads. — [LTA DataMall static data](https://datamall.lta.gov.sg/content/datamall/en/static-data.html); [LTA API User Guide](https://datamall.lta.gov.sg/content/dam/datamall/datasets/LTA_DataMall_API_User_Guide.pdf)
- **"Senior Activity Centres & Active Ageing Centres" (MSF) is counts only.** On data.gov.sg the only match is "Senior Activity Centres And Active Ageing Centres, Annual" (`d_0f70d7095a527be4ea443a7e30597896`, SingStat), a four-row national table. AAC count: 60 (2021), 119 (2022), 157 (2023), 223 (2024). It has no locations. — [data.gov.sg](https://data.gov.sg/datasets/d_0f70d7095a527be4ea443a7e30597896/view)
- **The only eldercare point layer is stale.** "Eldercare Services" (`d_f0fd1b3643ed8bd34bd403dedd7c1533`, MOH, GeoJSON) has 133 points, all stamped `FMEL_UPD_D` 2016-07-28. Names mix Senior Activity Centres (62) with nursing homes. Attributes are embedded in an HTML `Description` field and need parsing. It predates the AAC rebranding (2021 onward), so it does not represent today's 223+ AACs. — [data.gov.sg](https://data.gov.sg/datasets/d_f0fd1b3643ed8bd34bd403dedd7c1533/view)
- **Polyclinic locations: no complete current layer on data.gov.sg.**
  - "Vaccination_Polyclinics" (`d_b22489c7dc4065b6e7e45f177fdb33be`, MOH) has only 8 points with attributes last stamped Jan 2024.
  - "CHAS Clinics" (`d_548c33ea2d99e29ec63a7cc9edcccedc`) has 1,193 GP and dental points (stamped 2021-09) and is mostly private GPs.
  - HPB "Cervical Screening Centre" (`d_3ca2a28059588f297908b32da4ac3cbe`) and "Breast Screening Centre" (`d_0cdfbf7e277e8bfa1ef79fadf4b71b56`) GeoJSONs (May 2025) may include polyclinics. I did not verify this.
  - MOH "Health Facilities" (`d_e4663ad3f088a46dabd3972dc166402d`) gives only counts (18 polyclinics in 2009–2012).

  — [Vaccination_Polyclinics](https://data.gov.sg/datasets/d_b22489c7dc4065b6e7e45f177fdb33be/view); [CHAS Clinics](https://data.gov.sg/datasets/d_548c33ea2d99e29ec63a7cc9edcccedc/view); [Cervical Screening Centre](https://data.gov.sg/datasets/d_3ca2a28059588f297908b32da4ac3cbe/view)
- **Polyclinic workaround:** maps.gov.sg publishes a curated "List of polyclinics in Singapore" map. It is small enough (roughly 25–30 polyclinics; the exact count was not verified) to hand-geocode through OneMap. — [maps.gov.sg polyclinics](https://maps.gov.sg/polyclinics-singapore)
- **Childcare Centre Listings (ECDA): exists but stale.** "Child Care Services" (`d_5d668e3f544335f8028f546827b773b4`, ECDA) has 1,925 points, but every record carries `FMEL_UPD_D` 2021-12-01 even though the catalogue says it was updated 2026-04-18. `LANDXADDRESSPOINT` is null, but point geometry is present. A separate "Pre-Schools Location" layer also exists (`d_61eefab99958fd70e6aab17320a71f1c`). — [data.gov.sg](https://data.gov.sg/datasets/d_5d668e3f544335f8028f546827b773b4/view)
- **"HDB Elderly Population by Planning Area" does not exist in that form.** The closest is "HDB Elderly and Future Elderly Resident Population by Geographical Distribution" (`d_4180067b350bc9839a4cea487841d5d1`). It has 208 rows covering only the survey years 2003, 2008, 2013 and 2018, by **HDB town/estate** (for example Sengkang, Punggol), not URA planning area. Sibling tables cover ambulant status (`d_995d47e4632e72e4f0a589ed5e51bd36`, 2008–2018) and flat type. — [data.gov.sg](https://data.gov.sg/datasets/d_4180067b350bc9839a4cea487841d5d1/view)
- **Better elderly-density source:** "Resident Population by Planning Area/Subzone of Residence, Age Group and Sex (Census of Population 2020)" (`d_d95ae740c0f8961a0b10435836660ce0`). It has 388 rows (planning areas plus subzones) with 5-year age bands up to 90+, so the 65+ population per planning area and subzone can be computed directly. — [data.gov.sg](https://data.gov.sg/datasets/d_d95ae740c0f8961a0b10435836660ce0/view)
- **Newer figures:** SingStat publishes "Singapore Residents by Planning Area/Subzone, Age Group, Sex and Type of Dwelling, June 2025" (and floor-area variants) as CSV or Excel on singstat.gov.sg. It is not on data.gov.sg, and I could not open the SingStat page directly (it returned 404). — [WebSearch summary citing SingStat](https://www.singstat.gov.sg/find-data/search-by-theme/population/geographic-distribution)
- **Mobility-related census tables:**
  - "Resident Population Aged 65 Years and Over in Resident Households by Type of Dwelling, Mobility Status and Sex" (several vintages, for example `d_c1450d5a545b56f491641015352536a3` for Census 2010) is national, not by area.
  - A "Wheelchair Accessible Bus Services" CSV exists but covers only May 2015 (`d_93a768ea4f271eac5300c38d31be447f`).

  — [data.gov.sg catalogue API](https://api-production.data.gov.sg/v2/public/api/datasets)

### Inferences
- **The core demo metric (distance from each area's elderly centroid to the nearest AAC, polyclinic and cycling path) can only be computed honestly for cycling paths from the listed datasets.** AACs would need either the stale 2016 layer (62 SACs, a misleading comparison against 223 AACs today) or a scraped or manually compiled current list (for example from AIC's "Eldercare Services" locator), which I did not verify as downloadable. Polyclinics need a hand-geocoded list of about 30.
- **"Elderly population centroid" requires subzone-level population.** Planning-area centroids can be population-weighted using Census 2020 subzone 65+ counts with the MP2019 subzone polygons (`d_8594ae9ff96d0c708bc2af633048edfb`). This is a reasonable pipeline, but it means joining census names to polygon names.
- **Geospatial work on Free Edition:** Databricks serverless supports Python libraries such as geopandas and shapely installed via `%pip`, and spatial SQL functions may be available. Nearest-neighbour distance with a few thousand points is trivial compute. The risk is library-install friction, not scale. This is inferred; I did not test it on Free Edition.
- **Ridership adds almost nothing at planning-area level.** The accessibility score will be built from geometry (bus-stop and MRT-exit density per capita, distance to facilities) rather than ridership, unless the team obtains a DataMall key for passenger volume by bus stop.
- **Buildability:** medium to high risk. It is doable in 2 weeks only if data assembly (AAC and polyclinic lists) is time-boxed to the first 3–4 days.

### Gaps
- I could not confirm a current, downloadable AAC location list with coordinates (AIC, MSF or maps.gov.sg).
- I did not count the exact polyclinics on maps.gov.sg, and did not check whether it offers a GeoJSON export.
- I did not verify whether the HPB screening-centre GeoJSONs list all polyclinics.
- I did not verify whether LTA static SHP downloads still work without login in Sep 2026 (the page mentions no key, but I did not test a download).
- I did not look up an MP25 subzone boundary. Only the MP25 Planning Area boundary was confirmed; the latest subzone layer I confirmed is MP2019.

## C3 KopilamAI: hawker GeoJSON, closures, food waste, population

### Takeaway
Hawker locations and stall counts are good: 129 centres with cooked-food stall counts, construction status and completion or upgrading dates. Hawker density per 10,000 residents by planning area is straightforward with the Census 2020 population and the MP25 planning-area polygons. Two of the four demo items, however, are not well supported by the data:
- **Closures:** the "Dates of Hawker Centre Closures" dataset is a **current-year quarterly cleaning schedule** plus recent "other works" (repairs and redecoration, 2024–2026). It is not a historical record of permanent closures, and data.gov.sg exposes only the latest version.
- **Food waste:** available only as national annual totals. There are no hawker-level or area-level figures, so a "food waste estimation model tied to hawker activity" must be an allocation model built on assumptions, not a trained model.

### Cited Findings
- **Hawker Centres (GEOJSON), `d_4a086da0a5553be1d89383cd90d07ecd`, NEA.** Updated 2026-09-23, 129 Point features (WGS84).
  - Attributes: `NAME`, address fields, `STATUS`, `DESCRIPTION`, `AWARDED_DATE`, `IMPLEMENTATION_DATE`, `EST_ORIGINAL_COMPLETION_DATE`, `HUP_COMPLETION_DATE`, `NUMBER_OF_COOKED_FOOD_STALLS`, `PHOTOURL`, `INFO_ON_CO_LOCATORS`.
  - STATUS: Existing 103, Existing (new) 16, Under Construction 6, Existing (replacement) 3, Interim Centre 1.
  - DESCRIPTION: HUP Standard Upgrading 62, HUP Reconfiguration 20, New Centre 18, HUP Rebuilding 13, New Replacement Centre 8, Opted out of HUP 4, and others.
  - Cooked-food stalls: no nulls, total 6,925, range 0–226.
  - It has **no market-stall counts and no closure dates.**

  — [data.gov.sg](https://data.gov.sg/datasets/d_4a086da0a5553be1d89383cd90d07ecd/view)
- **"Dates of Hawker Centres Closure" (`d_bda4baa634dd1cc7a6c7cad5f19e2d68`, NEA, CSV).** Updated 2026-09-21, 123 rows, one per centre. Coverage in the metadata is 2026-01 to 2026-12.
  - Columns: `q1`–`q4_cleaningstartdate/enddate` with remarks, `other_works_startdate/enddate/remarks`, `latitude_hc`, `longitude_hc`, `no_of_market_stalls`, `no_of_food_stalls`, `status`, `description_myenv`.
  - 47 rows have "other works" dates, ranging from 2024 to 2026 (for example "Repairs and Redecoration", "Hawker Centres Transformation Programme").
  - Every row's status is Existing or Existing (new). There are **no permanent closures.**
  - This file is useful because it adds market-stall counts and lat/long.

  — [data.gov.sg](https://data.gov.sg/datasets/d_bda4baa634dd1cc7a6c7cad5f19e2d68/view)
- **Other hawker datasets:**
  - "NEA Market and Food Centre" (`d_a57a245b3cf3ec76ad36d55393a16e97`): 110 points with `TOTAL_STALLS`, `MP_STALLS`, `CF_STALLS`, `OWNER` and `TYPE`, but last stamped Dec 2014. It is a historical snapshot for a comparison.
  - "List of Government Markets Hawker Centres" (`d_68a42f09f350881996d83f9cd73ab02f`, 2016).
  - "Number of Hawker Stalls Under Government Market and Hawker Centres, Annual" (`d_894e84243d69d55c13b357dbad4e6350`, 1989–2014).
  - "Number of Licensed Hawkers…, Annual" (`d_874cb8683b003051794caaa0c2423ed5`, 1981–2015).
  - HDB Property Information has a `market_hawker` Y/N flag per block.

  — [NEA Market and Food Centre](https://data.gov.sg/datasets/d_a57a245b3cf3ec76ad36d55393a16e97/view); [Stalls annual](https://data.gov.sg/datasets/d_894e84243d69d55c13b357dbad4e6350/view)
- **Waste Disposed & Recycled (Annual), SingStat version (`d_72f8e05d45477a7af0c089ad970519da`).** National totals for 2013–2025 in million tonnes, for example 2025 disposed 3.36 (domestic 1.67, non-domestic 1.69) and recycled 3.66. **No food-waste row.** The NEA version (`d_96d95bfc9867daa138a451950dc7cc4e`) stops at 2014. "Waste Management And Overall Recycling Rates, Annual" is `d_daf568968ab40dc81e7b08887a83c8fa` (2000–2025). No data.gov.sg title contains "food waste". — [data.gov.sg](https://data.gov.sg/datasets/d_72f8e05d45477a7af0c089ad970519da/view)
- **Food-waste figures come from NEA's annual statistics PDF,** "waste-and-recycling-statistics-2015-to-2025" and annex tables. They are national only, with no sector, region or hawker breakdown. Reported: 649,000 t of food waste disposed in 2025 (646,000 t in 2024), and a food-waste recycling rate of about 18% in 2025. — [NEA Waste Statistics](https://www.nea.gov.sg/our-services/waste-management/waste-statistics-and-overall-recycling); [Mothership on recycling rate](https://mothership.sg/2025/07/recycling-rate-50-nea/)
- **Recycling Bins (`d_4dde14826642f49eefff48b7832b90db`, NEA, GeoJSON, ~19 MB):** 12,578 points, but every record is stamped 2017-06-02 (stale). Attributes sit in an HTML `Description` field ("Recycling Bins in HDB Estates", block and postal code). — [data.gov.sg](https://data.gov.sg/datasets/d_4dde14826642f49eefff48b7832b90db/view)
- **Population by planning area.** No annual planning-area population table is on data.gov.sg; the latest there is Census 2020:
  - `d_d95ae740c0f8961a0b10435836660ce0` (age and sex)
  - `d_e7ae90176a68945837ad67892b898466` (ethnicity)
  - `d_7f243956483d5901f237e6f87b096636` (dwelling type)

  The annual series "Singapore Residents By Planning Region, Age Group And Sex" (`d_3c4dc32382bdc23189428af2126dd188`, 2019–2025) covers only the 5 regions. June 2025 planning-area and subzone tables exist on SingStat itself (see C2). — [data.gov.sg Census 2020 PA/SZ](https://data.gov.sg/datasets/d_d95ae740c0f8961a0b10435836660ce0/view); [Planning region annual](https://data.gov.sg/datasets/d_3c4dc32382bdc23189428af2126dd188/view)
- **Planning-area boundaries:** "Master Plan 2025 Planning Area Boundary (No Sea)" (`d_2cc750190544007400b2cfd5d7f53209`, URA, GeoJSON, updated 2026-02-27) has 55 polygons with `PLN_AREA_N`, `PLN_AREA_C` and `REGION_N`. The MP2019 equivalent is `d_4765db0e87b9c86336792efe8a1f7a66`, and MP2019 subzones are `d_8594ae9ff96d0c708bc2af633048edfb`. — [data.gov.sg MP25 PA boundary](https://data.gov.sg/datasets/d_2cc750190544007400b2cfd5d7f53209/view)

### Inferences
- **Density per 10,000 residents and the food-access gap analysis are very feasible.** It is a spatial join of 129 points (or 123 with lat/long in the closures file) to 55 polygons, normalised by Census 2020 or June 2025 population. Distance or 1 km-buffer coverage from HDB blocks improves the gap metric but needs block geocoding.
- **Closures over time, permanent vs temporary, cannot be built from the official file as described.** It records only 2026 cleaning closures and 2024–2026 works. Ways to reconstruct history:
  1. Use `STATUS` and `DESCRIPTION` plus `HUP_COMPLETION_DATE`, `AWARDED_DATE` and `IMPLEMENTATION_DATE` in the GeoJSON (upgrading and rebuilding timeline, new centres since 2011).
  2. Diff the 2014 "NEA Market and Food Centre" snapshot (110) against today's 129 to find additions and removals.
  3. Look for archived versions of the closure CSV on the Wayback Machine or GitHub scrapers (not verified).

  Temporary closures (cleaning and works durations) can still be analysed for 2024–2026.
- **The food-waste model has to be a top-down allocation,** for example national food waste × (hawker stalls in area ÷ national stalls) × a per-capita factor. It should be presented as an estimate with stated assumptions; there is no ground truth to validate against.
- **Buildability:** high for the geospatial density and gap parts; weak for the closure-trend and food-waste parts. Expect judges to probe those two.

### Gaps
- No historical permanent-closure dataset was found. I did not check whether data.gov.sg keeps older versions of `d_bda4…` (the v2 API exposes only the latest version).
- I did not get NEA food-waste tonnage by year from a primary table; the figures come from a news summary. The PDF was not fetched.
- The June 2025 SingStat planning-area file was not downloaded; its exact name and format come from search snippets only.
- Why the GeoJSON has 129 entries against 123 in the closure file (under-construction and interim centres probably explain it) is inferred, not confirmed.

## Supplementary datasets and buildability on Databricks Free Edition (2 weeks, student team)

### Takeaway
Ranked by data readiness: **C1 > C3 > C2**. C1 is the lowest-risk build but the most saturated idea. C3 has good core geospatial data but weak closure and food-waste support. C2 needs the most manual data assembly (AACs, polyclinics) before any analysis can start. All datasets are small (the largest is about 24 MB), so Free Edition compute quotas are not the binding constraint. The binding constraints are data gaps, API rate limits and library installs.

### Cited Findings
- **Free Edition limits** (from the hackathon guidelines file `docs/guidelines/databricks-free-edition_setup_and_limits.txt`): serverless only; one 2X-Small SQL warehouse; up to 5 concurrent job tasks; one active Lakeflow pipeline per type; limited model-serving endpoints (no GPU); 3 Apps; one Lakebase project; no R or Scala. Exceeding a quota can disable compute for the day. — local file (hackathon guidelines)
- **Recommended ingestion** is the datastore API (`https://data.gov.sg/api/action/datastore_search?resource_id=<id>`) or a CSV/GeoJSON download. I observed that the poll-download API throttles with HTTP 429 when called without a key. — local guideline file; [data.gov.sg API](https://data.gov.sg/api/action/datastore_search?resource_id=d_8b84c4ee58e3cfc0ece0d773c8ca6abc&limit=2)
- **Supplementary datasets that close gaps** (all verified in the data.gov.sg catalogue):
  - MP25 Planning Area Boundary: `d_2cc750190544007400b2cfd5d7f53209`
  - MP2019 Subzone Boundary: `d_8594ae9ff96d0c708bc2af633048edfb`
  - MP25 Land Use: `d_a8c3546b26712e35021f3a681d0353ae`
  - Census 2020 PA/SZ age: `d_d95ae740c0f8961a0b10435836660ce0`
  - Census 2020 PA income: `d_4e150bbd35c3145ea43019212c7b46c2`
  - Income by dwelling type, 2000–2025: `d_ce5d8bb5c34f6b78b5b2f1fab09ccbce`
  - HDB Property Information: `d_17f5382f26140b1fdae0ba2ef6239d2f`
  - LTA Bus Stop: `d_3f172c6feb3f4f92a2f47d93eed2908a`
  - LTA MRT Station Exit: `d_b39d3a0871985372d7e1637193335da5`
  - Park Connector Loop (NParks): `d_a69ef89737379f231d2ae93fd1c5707f`
  - Median resale by town (quarterly): `d_b51323a474ba789fb4cc3db58a3116d4`

  — [data.gov.sg catalogue API](https://api-production.data.gov.sg/v2/public/api/datasets)
- **OneMap** gives free geocoding (Search) and routing, but needs an account token (3-day validity). Tokenless Search still returned results with a warning on 23 Sep 2026. — [OneMap authentication](https://www.onemap.gov.sg/apidocs/authentication)
- **LTA DataMall:** static SHP datasets have no key requirement mentioned; dynamic and passenger-volume APIs need an AccountKey. — [LTA static data](https://datamall.lta.gov.sg/content/datamall/en/static-data.html)

### Inferences
- **C1 buildability: high.** 1 day of ingestion and cleaning; 3–4 days on medallion tables with DLT expectations; 3–4 days on the forecast (MLflow-tracked, batch-scored into a table rather than a serving endpoint, which avoids serving limits); 3 days on the AI/BI dashboard and affordability index. Geocoding 9,749 addresses through OneMap is optional; at a polite rate it takes roughly an hour and should be cached. Main risk: judges have seen this many times, so novelty depends on the affordability, fair-value and governance layers.
- **C2 buildability: medium-low.**
  - Days 1–4 go to assembling polyclinic (about 30, from maps.gov.sg and OneMap) and AAC locations. The stale 2016 SAC layer is a fallback, but it must be disclosed.
  - Elderly density comes from Census 2020 or June 2025 SingStat subzone tables, not the HDB 2018 town table.
  - Ridership can only serve as national context.
  - The geospatial computations are light but need geopandas/shapely on serverless.
  - The MP25 cycling overlay stretch goal is well supported (`PRP_STATUS` field).
- **C3 buildability: medium-high for the density and access story, low for closures and food waste.**
  - The density and gap map is achievable in the first week.
  - The closure-trend item must be reframed (upgrading timeline plus 2026 temporary closures).
  - The food-waste model must be an assumption-driven allocation, clearly labelled.
  - The stale recycling-bin layer (2017) weakens the sustainability angle.
  - The idea is also less saturated than C1: I found no prominent GitHub or Kaggle projects in this search, though I did not search for them specifically.
- **No project needs more than notebooks, one DLT pipeline, a SQL warehouse and a dashboard,** so all three fit the Free Edition quotas.

### Gaps
- I did not search GitHub or Kaggle for saturation of C2 (elderly accessibility) or C3 (hawker density) ideas.
- I did not test geopandas or H3/spatial SQL availability on Databricks Free Edition serverless.
- I did not verify MSF or AIC AAC listing downloadability, or SingStat June 2025 planning-area CSV URLs.
