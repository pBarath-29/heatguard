# Cross-cutting selection factors for DAISI Challenge Singapore: originality, policy relevance and Databricks Free Edition fit

Context (from local docs, `docs/guidelines/` and `docs/problem-statements/`):
- Round 1 (6 Oct 2026, 11:59pm SGT, Devpost) is an idea submission: 3-slide PDF (Problem & why it matters / Solution & data / Databricks architecture & impact). No working build is needed yet.
- **Round 1 weights:** Problem fit & social impact 30%, **Solution quality & originality 30% ("a thoughtful approach, not a generic dashboard")**, Data & technical feasibility 25% (named open datasets, credible Databricks architecture, buildable in two weeks), Clarity 15%.
- **Demo Day weights (top 10 teams, 27 Oct 2026):** Social impact 30% ("could realistically be adopted"), **Technical execution on Databricks 30% ("working end-to-end pipeline: ingestion, transformation, governance, analytics or AI")**, UX 20% (non-technical stakeholder could act on it), Data rigour 10% (messy data, honest limitations), Presentation 10%.
- Organiser tips: "a polished end-to-end solution on one dataset beats a half-built solution across many"; "show the pipeline"; "handle messy data"; "make it actionable — who would use this, and what decision does it inform?"; record a fallback for any live step.
- The organiser's recommended workflow is: ingest from data.gov.sg APIs/CSVs with Auto Loader or notebooks, then clean/join with DQ checks and lineage, then MLflow, then an AI/BI dashboard, with governance as a stretch goal.

## 1) Originality and saturation: how over-done is each idea?

### Takeaway
C1 FlatFair (HDB resale price prediction) is by far the most saturated idea. It is a standard student and bootcamp project, with dozens of public GitHub repos, NUS coursework and General Assembly capstones. A2 DengueRadar (dengue plus weather ML) is moderately saturated: there are several GitHub repos, peer-reviewed papers, and NEA's own in-house ML. B1 HeatGuard, A1 SilverWatch and C2 MoveEasy look comparatively fresh as *student data-platform* projects. B2 FloodSense and B3 ZeroWaste sit in the middle. C3 KopilamAI's closure angle overlaps with existing consumer "is hawker closed" apps, but its food-access and vulnerability analysis looks under-done.

### Cited Findings
- **C1 (HDB resale): heavily saturated.** A single GitHub search returns at least 9 dedicated HDB resale price-prediction repos, including a NUS CS3244 module project, a General Assembly DSI "Project 2", Streamlit web apps (R² 0.96, MAE $20k) and a Flask API. — [JosiahMendes](https://github.com/JosiahMendes/HDB-Resale-Price-Prediction); [teyang-lau](https://github.com/teyang-lau/HDB_Resale_Prices); [grrrrnt (NUS CS3244)](https://github.com/grrrrnt/hdb-resale-price-prediction); [ezracalis (GA DSI Project 2)](https://github.com/ezracalis/Singapore-HDB-Price-Prediction); [kohjiaxuan](https://github.com/kohjiaxuan/Predicting-HDB-Price-with-Machine-Learning); [helloitsxinyi (Flask API)](https://github.com/helloitsxinyi/hdb-price-prediction); [zhermin](https://github.com/zhermin/HDB-Resale-Predictor); [JackFongNew](https://github.com/JackFongNew/Singapore-HDB-Resale-Price-Prediction)
- The same resale dataset (Jan 2017 to present) is the one the problem statement names, so judges will almost certainly see several look-alike FlatFair submissions. — local `track-C_liveable-inclusive-city.txt`
- **A2 (Dengue): moderately saturated.** There are several Singapore-specific dengue prediction repos: rainfall/temperature regression, Random Forest with spatial features (bus-stop density, park density), a GA DSI time-series capstone, and one using Google Trends. — [RoninSanta](https://github.com/RoninSanta/Machine_Learning-Dengue_Prediction_Model); [Diegosmiles](https://github.com/Diegosmiles/Predicting_Dengue_Singapore); [ezracalis (GA Project 4)](https://github.com/ezracalis/Dengue-Cases-Prediction); [jaotheboss](https://github.com/jaotheboss/Dengue-Prediction); [Medium/Analytics Vidhya](https://medium.com/analytics-vidhya/diminishing-the-dengue-danger-predicting-future-dengue-outbreaks-using-machine-learning-on-b4dc560219b8)
- There is also a peer-reviewed ML paper on Singapore dengue using meteorological data. — [PMC11055163](https://pmc.ncbi.nlm.nih.gov/articles/PMC11055163/)
- NEA already uses ML with 10 years of cluster, weather, built-environment and demographic data to predict where clusters may form "up to a year in advance". A student forecaster is therefore competing with an incumbent capability. — [GovInsider](https://govinsider.asia/intl-en/article/dr-ng-lee-ching-nea-singapore-dengue-machine-learning)
- **B2 (Flood): the incumbent is strong.** PUB runs an X-band radar rainfall-nowcasting system (with H2i and Furuno) and flood forecasting/monitoring. — [PUB rainfall prediction](https://www.pub.gov.sg/Resources/News%20Room/Featured%20Stories/2020/Rainfall%20prediction); [PUB Flood Forecasting](https://www.pub.gov.sg/Public/KeyInitiatives/Flood-Resilience/Flood-Forecasting-and-Monitoring); [GovInsider](https://govinsider.asia/intl-en/article/pub-yeo-keng-soon-hazel-khoo-exclusive-how-singapore-is-predicting-floods)
- The data.gov.sg Flood Alerts API does not include flood warning notices, which limits the labels available for training. — [data.gov.sg Flood Alerts](https://data.gov.sg/datasets/d_f1404e08587ce555b9ea3f565e2eb9a3/view)
- **B1 (Heat): few public student projects.** The search found mainly research-grade work, such as SUTD NetZeroFutures' URA-funded UHI analysis and the Cooling Singapore programme, plus generic non-Singapore UHI repos. I found no Singapore student repo combining NEA real-time temperature with elderly demographics. — [SUTD CSE_UHI_dataAnalysis](https://github.com/NetZeroFuturesLabSUTD/CSE_UHI_dataAnalysis); [World Bank heat hackathon blog](https://blogs.worldbank.org/en/opendata/hacking-the-heat--how-data-innovations-can-help-cities-face-a-ri)
- **C3 (Hawker): the closure lookup already exists as consumer apps.** Examples are ishawkerclosed.com and HawkerGo, and media outlets publish monthly closure lists. — [Is Hawker Centre Closed?](https://www.ishawkerclosed.com/); [HawkerGo](https://hawkergo.vercel.app/); [SETHLUI 2026 list](https://sethlui.com/hawker-centre-closure-guide-2026-singapore/)
- The NEA "Dates of Hawker Centres Closure" dataset appears to cover mainly scheduled cleaning and repair closures (86 centres closed for spring cleaning in June 2026). It is not clearly a record of permanent closures, so the problem statement's "permanent vs. temporary closure trend" may be thin. — [data.gov.sg dataset](https://data.gov.sg/datasets/d_bda4baa634dd1cc7a6c7cad5f19e2d68/view); [Yahoo](https://sg.style.yahoo.com/86-hawker-centres-markets-closed-020026697.html)
- Singapore health hackathons (HackitRx 2025, NUS HealthHack 2025) cover elderly-care themes, but I found no public outputs on isolation-risk scoring. — [HackitRx](https://hackitrx.devpost.com/); [NUS HealthHack 2025](https://medicine.nus.edu.sg/data/news-healthhack-singapore-2025)

### Inferences
- **Saturation ranking (most to least saturated, my judgement):** C1 >> A2 > B2 ≈ C3 (closure-lookup part) > A3 ≈ B3 > C2 ≈ A1 > B1. Because originality is worth 30% of the Round 1 score, C1 and A2 need a distinctive twist to score well; B1, A1 and C2 start with an advantage.
- The problem statements themselves are public. Many DAISI teams will pick the same "winning demo" bullet list, so within-competition saturation matters more than GitHub saturation. Differentiation will likely come from the user and decision framing (for example "an outreach roster for an AAC coordinator") and the AI layer, not from the choice of topic alone.
- Cross-cutting ideas are rarely done and use shared datasets: heat plus isolation plus AAC access (B1×A1×C2), or hawker access for elderly living alone (C3×A1).

### Gaps
- I could not systematically check Kaggle, or past NUS/NTU/SMU datathons, Lifehack or GovTech Build for Good winners, for each topic. Search returned no specific prior-winner lists. Within-competition saturation is unknowable.
- I did not find specific GitHub counts for A1, A3, B3 or C2. Their "fresh" status is inferred from the absence of search hits, not from exhaustive counts.

## 2) Policy relevance and impact in 2026 Singapore

### Takeaway
Ageing (A1, A3, C2, and B1's elderly angle) and climate adaptation (B1, B2) line up most directly with 2026 national framing: the "super-aged" milestone and the Year of Climate Adaptation, which includes a S$40m heat-resilience programme. Dengue is at a multi-year low in 2025–2026, which weakens A2's urgency story. Waste (B3) is live because the Zero Waste Masterplan is under review and domestic recycling is stuck at 11%.

### Cited Findings
- **Ageing:** Singapore becomes "super-aged" in 2026 (UN definition: 21% aged 65 or older). The Seasia source phrases this as "one in four", which conflicts with the 21% threshold and the problem statement's "1 in 5". — [Seasia.co](https://seasia.co/2026/03/26/singapore-2026-navigating-the-silent-crisis-of-a-super-aged-society); local `track-A` doc
- One-person households aged 65+ more than doubled, from 42,100 (2014) to 87,200 (2024). About 40% of seniors aged 75+ in 2025 lived alone or only with other seniors. — [MOH: loneliness among seniors living alone](https://www.moh.gov.sg/newsroom/addressing-loneliness-and-psychological-distress-among-seniors-living-alone/) (figures as surfaced in search snippet; verify on page)
- Age Well SG is a national plan spanning transport, housing, active ageing and care. There are over 230 Active Ageing Centres, and "8 in 10 seniors" have one near home. The remaining 2 in 10 is a natural gap-analysis target for A1 and C2. — [Age Well SG](https://www.agewellsg.gov.sg/about/); [MOH ageing in community](https://www.moh.gov.sg/ageing-well/ageing-in-the-community/)
- **Climate / heat:** 2026 is the Year of Climate Adaptation, with a review across heat resilience, coastal and flood resilience, and water and food resilience. A heat-resilience R&D programme with a S$40m fund will study heat effects on population groups, with the elderly named as a priority. — [MSE YOCA](https://www.mse.gov.sg/yoca/); [FCC Singapore](https://www.fccsingapore.com/news/n/news/singapore-in-2026-understanding-the-year-of-climate-change-adaptation.html)
- NEA's Heat Stress Advisory (launched 2023) uses WBGT with Low / Moderate / High bands. A HeatGuard risk tier can map onto this official scheme, which helps adoption credibility. — [Malay Mail 2023](https://malaymail.com/news/singapore/2023/07/24/singapores-first-heat-stress-advisory-launched-as-temperatures-keep-rising-amid-climate-change/81534)
- **Flood:** PUB flash floods and warnings in Feb 2026 hit Jurong Town Hall Road (18 Feb, CNY day 2), Katong (17 Feb) and the west (5 Feb). PUB says it has spent about $2bn on drainage in a decade, but "not feasible to expand drains to cater for every extreme rainfall event". — [AsiaOne](https://www.asiaone.com/singapore/flash-floods-jurong-cny-day-2); [Mothership](https://mothership.sg/2026/02/risk-flash-floods-katong-pub/); [PUB About Floods](https://www.pub.gov.sg/Public/KeyInitiatives/Flood-Resilience/About-Floods)
- **Dengue (weak urgency in 2026):**
  - 2025 had 4,036 cases, the lowest since 2018. — [NUHS/ST PDF](https://www.nuhs.edu.sg/docs/default-source/newsroom-document/nuhs/2025/st-dengue-cases-in-spore-hit-7-year-low-in-2025-amid-global-decrease.pdf?sfvrsn=ccf01af9_1)
  - Cases in the first 5 months of 2026 were down 66% year on year. — [The Star](https://www.thestar.com.my/aseanplus/aseanplus-news/2026/05/16/singapore-dengue-cases-drop-66-in-first-5-months-of-2026-most-breeding-sites-in-2025-found-in-homes)
  - The 2026 weekly peak was 119 cases (week ending 13 June), with 4 red-alert clusters in the north (Lentor and elsewhere). — [Xinhua](https://english.news.cn/20260616/16666162380847008cd20fe9682603b0/c.html); [Medical Daily](https://www.medicaldaily.com/singapore-dengue-cases-2026-high-red-alert-clusters-june-475672)
  - Project Wolbachia is expanding to 740,000 households by March 2026. — [MSE PQ reply](https://www.mse.gov.sg/latest-news/oral-reply-to-parliamentary-question-on-dengue-and-project-wolbachia/)
  - The "about 1,700 cases as of August 2026" figure came from a search-engine summary and was not verified at source.
- **Waste:**
  - The overall recycling rate was 52% in 2025. The domestic recycling rate is stuck at 11%, while non-domestic rose from 65% to 67%. — [AsiaOne](https://www.asiaone.com/singapore/singapore-recycling-rate-zero-waste-masterplan-semakau-landfill); [NEA waste statistics](https://www.nea.gov.sg/our-services/waste-management/waste-statistics-and-overall-recycling)
  - Semakau is more than half full and is expected to be full by 2035. NEA is reviewing the 2019 Zero Waste Masterplan, and the 2030 targets are "to be reviewed". — [AsiaOne](https://www.asiaone.com/singapore/singapore-recycling-rate-zero-waste-masterplan-semakau-landfill)
  - 78% of homes recycled last year, up from 72% in 2023. — same source
- **Hawkers:** the median hawker age is about 59. Stalls are closing because of costs and a lack of successors. — [NYC Food Policy Center](https://www.nycfoodpolicy.org/the-preservation-paradox-singapores-hawker-centres-as-a-case-study-in-cultural-food-policy/) (secondary source; the median-age figure should be verified against NEA)

**Likely adopters per problem (inferred from the agencies named in the problem statements and the sources above):**

| Problem | Named stakeholders / adopters |
|---|---|
| A1 SilverWatch | Silver Generation Office (AIC), AAC operators, MSF/ComCare, Town Councils/CCs, volunteer groups |
| A2 DengueRadar | NEA Environmental Public Health, Town Councils, grassroots dengue volunteers |
| A3 HealthPulse | MOH (Healthier SG), Regional Health Systems (NUHS/NHG/SingHealth), AIC |
| B1 HeatGuard | MSE Heat Resilience programme, NEA (WBGT advisory), AICs/AACs as cooling refuges, SGO |
| B2 FloodSense | PUB, Town Councils, LTA (traffic), SCDF |
| B3 ZeroWaste | NEA, MSE, Town Councils, public waste collectors |
| C1 FlatFair | HDB, first-time buyers (consumer tool) |
| C2 MoveEasy | LTA (Walk2Ride, Friendly Streets), MOH/AIC, URA Master Plan |
| C3 KopilamAI | NEA Hawker Division, SFA, HDB/URA planning |

### Inferences
- **Policy-alignment strength (my judgement):** B1 (heat and elderly both 2026 headline priorities) ≥ A1 > C2 ≈ A3 > B2 > B3 > C3 > A2 > C1. C1's affordability angle is politically salient, but the solution is a consumer tool with no clear agency adopter.
- A2's "tens of thousands of cases" framing in the problem statement is outdated for 2025–2026. A team choosing A2 should pivot the framing to "sustaining low incidence / early warning for cluster flare-ups", or acknowledge the low base rate. The low case volume also means sparse labels.
- For B2, PUB's incumbent radar nowcasting means a student classifier should frame itself as a community or town-council situational tool, not as a replacement for PUB forecasting.

### Gaps
- I did not retrieve a verified 2026 NEA count of high-heat-stress days or 2026 heat-related hospitalisation figures. The search returned only US/EU heatwave results.
- I did not find 2026 permanent hawker-closure or vacancy statistics from NEA.
- I did not verify MOH Healthier SG 2026 enrolment figures (relevant to A3) or AAC counts beyond the "230+" figure.

## 3) Databricks Free Edition fit, limits, and what judges reward

### Takeaway
Free Edition's outbound internet is restricted to an unpublished allowlist of "trusted domains". Whether serverless notebooks can call `api.data.gov.sg` / `api-open.data.gov.sg` is **unverified** and must be tested on day 1. Streaming-centric problems (A2, B1, B2) depend on that most. H3 and ST_ spatial SQL functions are available on serverless (Spatial SQL is now GA, with native AI/BI maps), which helps every geospatial problem. The Free Edition feature set is now broad: Genie, Genie Code, Agent Bricks, Lakebase, serverless GPUs and Lakeflow Designer were added in June 2026. That makes an "AI layer on top of a medallion pipeline" achievable.

### Cited Findings
- **Free Edition limits (official docs):**
  - Serverless only.
  - Outbound internet "restricted to a limited set of trusted domains".
  - One SQL warehouse at 2X-Small.
  - 5 concurrent job tasks.
  - "One active pipeline per pipeline type".
  - 3 Apps, which auto-stop after 24h.
  - One AI Search endpoint with one search unit (no Direct Vector Access).
  - One Lakebase project with scale-to-zero.
  - Limited model-serving endpoints: no GPU serving, no provisioned throughput, no custom-model GPU or batch inference, and "certain models unavailable".
  - No R or Scala, online tables, clean rooms or Knowledge Assistant.
  - Exceeding quotas shuts compute down for the rest of the day or month.
  - The docs also state that "LinkedIn verification unlocks expanded serverless GPU access and broader internet connectivity" (from the fetched docs page; worth confirming in-product).

  — [Databricks docs: Free Edition limitations](https://docs.databricks.com/aws/en/getting-started/free-edition-limitations)
- **No published allowlist.** A Databricks employee confirmed this on 2 Feb 2026. pypi.org works, and wikipedia.org is blocked in some regions (allowed in eu-west-1, blocked in us-east-2), so allowlists vary by region. Government APIs were not confirmed either way. — [Databricks Community thread 146591](https://community.databricks.com/t5/databricks-free-edition-help/whitelist-for-outbound-network-access/td-p/146591); [Thread 121832: "outbound internet suddenly blocked"](https://community.databricks.com/t5/data-engineering/free-edition-outbound-internet-suddenly-blocked-error/td-p/121832)
- **Contradiction with the organisers:** the DAISI workflow guide tells teams to "ingest raw datasets from data.gov.sg APIs" and to stream live weather and flood data. This implies, but does not prove, that it works from Free Edition. — local `data-gov-sg_and_databricks-workflow.txt`
- **Geospatial:** H3 functions are built into Databricks SQL and Runtime. Spatial SQL (80+ ST_ functions) is GA, with native maps in AI/BI dashboards. Serverless release notes list new ST_ and H3 functions (for example `st_estimatesrid`, `h3_try_coverash3`). — [H3 docs](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-h3-geospatial-functions); [Spatial SQL GA blog](https://www.databricks.com/blog/geospatial-unbounded-spatial-sql-ga-aibi-maps-delta-sharing-and-iceberg-v3); [Spatial SQL intro](https://www.databricks.com/blog/introducing-spatial-sql-databricks-80-functions-high-performance-geospatial-analytics); [Serverless release notes](https://docs.databricks.com/aws/en/release-notes/serverless/)
- **New Free Edition features (17 Jun 2026):** Genie Code (an autonomous coding agent), serverless GPUs, Lakebase, Agent Bricks and Lakeflow Designer. Databricks says Free Edition now covers "every core Databricks practitioner feature". — [Databricks blog: What's coming next to Free Edition](https://www.databricks.com/blog/whats-coming-next-free-edition)
- **The organisers' own Free Edition page lists five build patterns:**
  - AI app/agent (Apps + Foundation Model APIs)
  - Analytics (notebooks, SQL, dashboards, Genie spaces)
  - Lakeflow pipeline
  - Lakebase-backed app
  - MLflow experiment

  It also warns: "Add the Databricks capability that matters because it improves the solution, not to pad the feature count." — local `databricks-free-edition_setup_and_limits.txt`
- **What Databricks hackathon judges reward:**
  - The inaugural Free Edition Hackathon (winners announced 16 Dec 2025) was judged on Technical Complexity & Execution, Creativity & Innovation, Presentation & Communication, and Impact & Learning Value.
  - 1st place, VidMind, turned unstructured video into a knowledge base.
  - 2nd place was a space-weather system forecasting power-grid failures 7 days ahead, praised for "real-world impact on grid operator decision-making". This is structurally similar to B1 and B2: a forecast plus a decision for an infrastructure operator.
  - 3rd place was an NLP recipe recommender with a natural-language query interface.

  — [Databricks blog: Free Edition Hackathon winners](https://www.databricks.com/blog/announcing-winners-inaugural-databricks-free-edition-hackathon)
- The APJ "Smart Business Insights Challenge" centred on AI/BI Dashboards and Genie. — [Databricks blog APJ winners](https://www.databricks.com/blog/announcing-winners-apj-databricks-smart-business-insights-challenge-data-intelligence-powered)
- The 2026 DAIS "Apps & Agents for Good" hackathon centred on Databricks Apps plus agents for social good. — [Devpost](https://dais-for-good-2026.devpost.com/)

**Per-problem feature fit (inference from the problem statements and feature docs):**

| Problem | Natural showcase features | Free Edition friction |
|---|---|---|
| A1 SilverWatch | Medallion over mostly static CSVs; Spatial SQL/H3 for AAC coverage gaps; MLflow risk index; AI/BI map; **Genie space for coordinators ("which towns have most seniors living alone and no AAC within 400m?")**; Unity Catalog row/column masking for social data (stated stretch goal); Lakebase for an outreach-tracking app | Low. No streaming needed. Risk: "unsupervised" risk score with no ground-truth label, so an honest weighting method is needed |
| A2 DengueRadar | Auto Loader / Structured Streaming from real-time rainfall and temperature APIs; GeoJSON clusters parsed with ST_ functions; MLflow comparison against a baseline | **High.** Depends on data.gov.sg API egress (unverified); 1 active streaming pipeline; low 2026 case counts give sparse labels; H3 needed to join clusters to planning areas |
| A3 HealthPulse | Batch medallion; time-series forecasting in MLflow; scenario toggles in a Databricks App; UC governance for health data | Low compute need. Mostly national or annual data, so planning-area granularity has to be synthesised, which is a data-rigour risk |
| B1 HeatGuard | ≥2 real-time streams (temperature, PM2.5, rainfall) via Auto Loader or a scheduled Lakeflow job; Spatial SQL nearest-station interpolation to planning areas; MLflow heat-risk score mapped to NEA WBGT bands; alert agent (Foundation Model API drafts advisories); Genie | **Medium–high.** Needs API egress (unverified; fallback is to poll locally and land JSON in a UC Volume); 2X-Small warehouse fine; ~50 stations limits spatial resolution |
| B2 FloodSense | Batch historical training plus streaming inference; Auto Loader; MLflow classifier | **High.** API egress; sparse flood-alert labels (alerts API excludes warnings); flood-prone-areas data is annual and coarse |
| B3 ZeroWaste | Batch medallion; Spatial SQL bin-per-1,000-residents; forecast to 2030; scenario simulation App | Low. Data mostly national annual series (small n for ML); geospatial points available |
| C1 FlatFair | Clean batch pipeline with schema evolution; MLflow forecasting; Genie over transactions; App fair-value estimator | Very low friction, but very high saturation |
| C2 MoveEasy | **Spatial SQL/H3 is the core** (distance to AAC/polyclinic/cycling path, isochrone-like coverage); AI/BI maps; Genie | Low compute. Needs polyclinic locations (not in the listed datasets; must source separately); cycling GeoJSON is large but manageable |
| C3 KopilamAI | Spatial SQL density per 10k residents; closure trend; food-waste estimate | Low friction. Closure dataset is mostly cleaning schedules; food-waste data is national-level only, so the estimation model is weakly grounded |

### Inferences
- **Day-1 test (critical):** from a Free Edition notebook, run `requests.get("https://api-open.data.gov.sg/v2/real-time/api/air-temperature")` and the datastore_search URL. If blocked, the fallback is:
  1. poll from a laptop or GitHub Actions and push JSON into a UC Volume;
  2. let Auto Loader pick up files incrementally.

  This still demonstrates Auto Loader and incremental ingestion honestly. Databricks Apps may have different egress than notebooks, which is also unverified. The LinkedIn-verification route to broader internet is worth trying.
- "One active pipeline per pipeline type" means a team can run one Lakeflow Declarative Pipeline covering bronze, silver and gold as a single pipeline. Separate streaming and batch pipelines of the same type cannot both be active. It is better to design one pipeline with multiple tables, and use Jobs for scheduled polling.
- The problems that can showcase the full stack without depending on unverified egress are A1, C2, A3 and B3. B1 can showcase the most features (streaming, geo, ML, alerts, agent) but carries the most infrastructure risk.
- Judges reward end-to-end execution plus a clear decision-maker. Past winners paired forecasting with an operator decision or used a natural-language interface. A Genie space or an Agent Bricks / Foundation-Model "explain and act" layer on top of a gold table is a cheap differentiator on any problem, and it directly counters "not a generic dashboard".
- Stick to Spatial SQL (ST_ and H3) inside Databricks rather than GeoPandas-heavy code. It showcases platform features and renders natively in AI/BI maps.

### Gaps
- **Unverified:** whether `data.gov.sg` / `api-open.data.gov.sg` is on the Free Edition egress allowlist, and which AWS region Free Edition workspaces are provisioned in (the allowlist is region-dependent). This must be tested empirically.
- **Unverified:** whether Databricks Apps in Free Edition have the same egress restrictions as notebooks.
- I did not confirm that Genie spaces and AI/BI map visuals have no additional Free Edition caps beyond the 2X-Small warehouse.
- I did not confirm which Foundation Model API models are currently available in Free Edition ("certain models unavailable").
- No public judging rubrics or winner write-ups were found from prior DAISI rounds, if any exist.
