# DAISI Challenge — Singapore · Team Knock Before Noon · B1 HeatGuard

Student hackathon: build on **Databricks Free Edition** using Singapore open data (data.gov.sg) for measurable social impact.
**Status: selected for the top 10 → Stage 2 build sprint.**

## Key dates
| What | When |
|---|---|
| Round 1 — idea submission | ✅ submitted, selected for top 10 (9 Oct) |
| Build kickoff, mentors assigned | Mon 12 Oct 2026 |
| Mentored build sprint | 12–26 Oct 2026 |
| **Demo Day** (top 3 selected) | **Tue 27 Oct 2026, 4–7 pm SGT** |
| Finale at Databricks Singapore office | 4 Nov 2026 |

## What's built (as of 14 Oct 2026)
| Piece | Where |
|---|---|
| **Website** for coordinators (FastAPI + React): check-in list, Why here?, heat & haze now, Genie chat, forecast accuracy, message writer | [webapp/](webapp/) · https://heatguard-web-7474645045833960.aws.databricksapps.com |
| **Pipeline** bronze → silver → gold with data-quality expectations | [notebooks/04_pipeline.py](notebooks/04_pipeline.py) · pipeline `heatguard-pipeline` |
| **Forecast model** (tomorrow's afternoon peak WBGT + chance of High heat) in MLflow / Unity Catalog | [notebooks/05_forecast_model.py](notebooks/05_forecast_model.py) · `workspace.heatguard.wbgt_peak_forecaster@champion` |
| **Daily job** at 6:45 pm SGT: refresh data → pipeline → forecast → pipeline | `heatguard-daily` |
| **Keep-alive job**: restarts the website at 5:30 am, checks again at 5:30 pm, so the links stay live on Free Edition | `heatguard-keep-apps-on` · [notebooks/07_keep_apps_running.py](notebooks/07_keep_apps_running.py) |
| **Genie space** "HeatGuard: ask about heat risk" | [genie/create_genie_space.py](genie/create_genie_space.py) |
| Ingestion: setup, live 15-min job (paused), backfill, static data | [notebooks/00–03](notebooks/) |

## Start here
- [docs/stage2/build-plan.md](docs/stage2/build-plan.md) — scope, day-by-day plan, mentor questions, demo checklist
- [docs/decision-log.md](docs/decision-log.md) — shared record of decisions, learnings and open questions
- [reports/DAISI problem statement selection.md](reports/DAISI%20problem%20statement%20selection.md) — why B1, dataset checks

## Folder layout
```
docs/
  original/            untouched source material from Round 1
  problem-statements/  the 9 problems, split by track
  guidelines/          judging criteria, submission checklist, Free Edition limits
  stage2/              selection email, participant guide, build plan, reply draft
  decision-log.md      decisions, learnings, open questions
submission/
  round1-idea/         submitted deck (PDF/PPTX), Devpost text, gallery images
  round2-demo-day/     Demo Day materials
data/
  raw/                 downloads from data.gov.sg
  processed/           cleaned / joined outputs
notebooks/             Databricks notebooks (00 setup → 06 daily forecast)
webapp/                Main website: FastAPI backend + React frontend (Databricks App heatguard-web)
genie/                 Genie space definition
reports/, research_notes/   problem-selection research
```
