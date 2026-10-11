# HeatGuard — Stage 2 build plan (12–26 Oct 2026)

**Demo Day:** Tue 27 Oct, 4–7 pm SGT. **Goal:** one polished end-to-end slice that a coordinator could actually use.

Demo Day scoring, and what earns each:

| Criterion | Weight | What we must show |
|---|---|---|
| Social impact | 30% | Named users, a next-day decision, and a realistic adoption path (rulebook checked against NEA guidance; ideally feedback from an AAC coordinator) |
| Technical execution on Databricks | 30% | Live ingestion → Lakeflow pipeline → MLflow model → dashboard/Genie, with Unity Catalog lineage |
| Solution & UX | 20% | 3-tab dashboard a non-technical person can act on in under a minute |
| Data rigour | 10% | Quality checks, beating a baseline, limitations stated up front |
| Presentation | 10% | Clear story, a live demo with a recorded backup, and confident Q&A |

---

## Scope

**Must have (the demo fails without these)**
1. Live WBGT ingestion every 15 min + historical backfill (Feb 2025 → now).
2. Lakeflow Declarative Pipeline: bronze → silver → gold, with data-quality expectations.
3. Station → subzone mapping (distance-weighted) and distance to the nearest Community Club or library.
4. Vulnerability score per subzone (Census 2020), with weights shown.
5. Next-day peak WBGT forecast per station in MLflow, beating a "tomorrow = today" baseline.
6. Ranked check-in list (heat band × vulnerability) with a reason and a rulebook action.
7. AI/BI dashboard: **Now / Tomorrow / Why here?**
8. Unity Catalog: table comments, lineage from raw to final list.

**Should have**
- Genie space over the gold tables.
- Foundation Model API advisory text.
- Forecast track-record panel (predicted vs actual, last 14 days).

**Stretch (only if everything above is done)**
- Outreach-planning agent ("plan tomorrow's outreach for Bedok").
- Block-level rental-block list via HDB Property Information.

---

## Day-by-day

| Dates | Focus | Done when |
|---|---|---|
| **Sun 11 – Mon 12 Oct** | Setup | Everyone has a Free Edition workspace; **one demo workspace chosen**; data.gov.sg API key; **test whether a notebook can reach `api-open.data.gov.sg`** (if not: poll from a laptop or GitHub Actions and upload to a UC Volume); Git folder linked to a repo |
| **Tue 13 – Wed 14 Oct** | Ingestion (bronze) | WBGT backfill landed; scheduled 15-min job running; static files loaded (Census tables, subzone map, CCs, libraries); temperature/RH history for 2023–2024 loaded (sample, to save quota) |
| **Thu 15 – Sat 17 Oct** | Pipeline (silver/gold) | Lakeflow pipeline with expectations; stations → subzones; distance to nearest cool space; vulnerability table; quality metrics visible |
| **Sun 18 – Tue 20 Oct** | Model | Training table (features = recent WBGT/temperature/RH + NEA forecast; target = next-day afternoon peak WBGT); baselines (persistence, same-day-last-week average); gradient-boosted model in MLflow; registered model; daily scoring job writes tomorrow's forecast |
| **Wed 21 – Fri 23 Oct** | Outputs | Ranking + rulebook table; 3-tab dashboard; Genie space with example questions; advisory generation |
| **Sat 24 – Sun 25 Oct** | Governance + hardening | UC comments/tags/lineage screenshot; fresh-browser test of the whole demo path; **record a backup video of the live steps** |
| **Mon 26 Oct** | Pitch | Slides, script, presenter handoffs, two full rehearsals |

**Feature freeze: Fri 23 Oct, end of day.** After that, only fixes and polish.

---

## Notebook / folder layout

```
notebooks/
  00_setup.py            catalog, schema, volume, secrets check, egress test
  01_ingest_live.py      15-min job: WBGT, temperature, humidity, forecasts → Volume
  02_backfill.py         one-off history pull (paginated, rate-limited)
  03_load_static.py      Census, subzone map, CCs, libraries → bronze
  pipeline/              Lakeflow Declarative Pipeline (bronze → silver → gold)
  10_train_forecast.py   features, baselines, model, MLflow
  11_score_tomorrow.py   daily job: forecast → subzone bands → ranked list
  20_advisories.py       Foundation Model API wording step
dashboards/              exported AI/BI dashboard JSON
docs/decision-log.md     shared record for the organisers
```

---

## Free Edition limits that affect us

- **One active pipeline per type:** keep everything in a single Lakeflow pipeline.
- **One 2X-Small SQL warehouse:** keep gold tables small; dashboards read gold only.
- **Quota lockouts can last the rest of the day:** backfill once, use samples, and stop idle compute.
- **Some models may be unavailable:** confirm which Foundation Model API model works on day 1.

## Questions for the first mentor office hours

1. Can Free Edition serverless reach `api-open.data.gov.sg`? If not, what ingestion path do they recommend?
2. Which Foundation Model API model should we use on Free Edition?
3. Do they recommend a Databricks App, or is an AI/BI dashboard + Genie enough for UX scoring?
4. Do they know an Active Ageing Centre contact who could sanity-check the action rulebook?
5. How do judges want to see Unity Catalog governance: a lineage screenshot, or a live walkthrough?

## Demo readiness checklist (from the participant guide)

- [ ] The final deployment owner can sign in and open every required resource
- [ ] Pipeline, SQL warehouse, dashboard, Genie space and data are ready in the final workspace
- [ ] Main user journey tested from a fresh browser session
- [ ] No token, password, key or personal data visible anywhere
- [ ] Every member can explain the problem, user, architecture, Databricks contribution and handoffs
- [ ] Datasets, libraries and models credited
- [ ] Backup recording ready for the most failure-prone live step
- [ ] Final link, repository and materials accessible to judges
