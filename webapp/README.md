# HeatGuard web app (FastAPI + React, Databricks App `heatguard-web`)

The HeatGuard website — the project's only app.

## How it's built

| Part | Tech | Folder |
|---|---|---|
| Backend API + serves the website | FastAPI (Python) on Databricks Apps | `server/` |
| Frontend | React 18 + TypeScript, Tailwind CSS, TanStack Query (loading/error/retry), lucide icons | `frontend/` |
| Built website (committed so Databricks only needs Python) | Vite build output | `static/` |

Data: SQL on the `workspace.heatguard` gold/ML tables via the Serverless Starter Warehouse. Genie: Conversation API on space
`01f1c7ce26701e9d830c00124d3a37ed`. Message writer: `databricks-meta-llama-3-3-70b-instruct` (falls back to the plain rulebook text).

## Pages (for coordinators only)

| Page | What it shows |
|---|---|
| **My plan** (`/`) | Asks once for the centre's postal code, then: plain-words outlook, tick-off to-do list, ready-to-send message (seniors or staff, 4 languages, one-tap WhatsApp), nearby areas to check first, nearest cool place |
| **Area** (`/area/<name>`) | Why to check this area, what to do, nearest cool place, message button |
| **Ask a question** (`/ask`) | Genie answers in plain words (technical columns and SQL are hidden) |

Technical material (model accuracy, replay of past hot days, Singapore-wide ranking) is kept out of the website; it lives in the notebooks,
the `gold_replay_*` / `ml_*` tables and `docs/decision-log.md`.

## API

| Endpoint | Returns |
|---|---|
| `GET /api/near?postal=<6 digits>` | Centre location (OneMap), tomorrow's heat there, plain-language plan and to-do, nearby areas, nearest cool places |
| `GET /api/area/{subzone}` | One area's row from the check-in list |
| `POST /api/message` | `{subzone, language, audience, centre?}` → ready-to-send message |
| `POST /api/genie` | `{question, conversation_id?}` → Genie answer |
| `GET /api/health`, `POST /api/refresh` | Status; clear the 5-minute cache |

Errors come back as `{"error": "<plain-English message>"}`.

## Change and deploy

```bash
cd frontend && npm install && npm run build      # rebuilds ../static
git add -A && git commit && git push              # then pull the Databricks Git folder
databricks apps deploy heatguard-web --source-code-path /Workspace/Users/yubrajb2907@gmail.com/heatguard/webapp
```

Local development: run the API (`python -m server` from this folder with `DATABRICKS_CONFIG_PROFILE`, `DATABRICKS_WAREHOUSE_ID`,
`GENIE_SPACE_ID`, `SERVING_ENDPOINT` set), then `npm run dev` in `frontend/` (proxies `/api` to port 8000).

Free Edition stops apps after 24 hours: before a demo, open **Compute → Apps → heatguard-web** and click **Start**.
