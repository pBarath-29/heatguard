# HeatGuard web app (FastAPI + React, Databricks App `heatguard-web`)

The main, polished HeatGuard website. The Streamlit app in [../app](../app) is kept as a backup.

## How it's built

| Part | Tech | Folder |
|---|---|---|
| Backend API + serves the website | FastAPI (Python) on Databricks Apps | `server/` |
| Frontend | React 18 + TypeScript, Tailwind CSS, Recharts (charts), Leaflet + OneMap (maps), TanStack Query (loading/error/retry), lucide icons | `frontend/` |
| Built website (committed so Databricks only needs Python) | Vite build output | `static/` |

Data: SQL on the `workspace.heatguard` gold/ML tables via the Serverless Starter Warehouse. Genie: Conversation API on space
`01f1c7ce26701e9d830c00124d3a37ed`. Message writer: `databricks-meta-llama-3-3-70b-instruct` (falls back to the plain rulebook text).

## API

| Endpoint | Returns |
|---|---|
| `GET /api/checkin` | Ranked list + status (`tomorrow` / `today` / `past` / `observed`) |
| `GET /api/area/{subzone}` | One area: row, stations used, last 30 days of peaks, forecasts, score weights |
| `GET /api/now` | Latest station readings, haze by region, last 30 days |
| `GET /api/accuracy` | Model vs baselines, backtest, feature importance, live track record |
| `GET /api/about` | Score weights, rulebook |
| `GET /api/cool-spaces` | Community Clubs and libraries |
| `POST /api/genie` | `{question, conversation_id?}` → Genie answer (text, tables, SQL, follow-ups) |
| `POST /api/message` | `{subzone, language, audience}` → ready-to-send message |
| `GET /api/health`, `POST /api/refresh` | Status; clear the 5-minute cache |

Interactive API docs: `/api/docs`. Errors come back as `{"error": "<plain-English message>", "detail": "<technical detail>"}`.

## Change and deploy

```bash
cd frontend && npm install && npm run build      # rebuilds ../static
git add -A && git commit && git push              # then pull the Databricks Git folder
databricks apps deploy heatguard-web --source-code-path /Workspace/Users/yubrajb2907@gmail.com/heatguard/webapp
```

Local development: run the API (`python -m server` from this folder with `DATABRICKS_CONFIG_PROFILE`, `DATABRICKS_WAREHOUSE_ID`,
`GENIE_SPACE_ID`, `SERVING_ENDPOINT` set), then `npm run dev` in `frontend/` (proxies `/api` to port 8000).

Free Edition stops apps after 24 hours: before a demo, open **Compute → Apps → heatguard-web** and click **Start**.
