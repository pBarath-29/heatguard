# HeatGuard web app (FastAPI + React, Databricks App `heatguard-web`)

The HeatGuard website — the project's only app.

## How it's built

| Part | Tech | Folder |
|---|---|---|
| Backend API + serves the website | FastAPI (Python) on Databricks Apps | `server/` |
| Frontend | React 18 + TypeScript, Tailwind CSS, TanStack Query (loading/error/retry), lucide icons | `frontend/` |
| Built website (committed so Databricks only needs Python) | Vite build output | `static/` |

Data: SQL on the `workspace.heatguard` gold/ML tables via the Serverless Starter Warehouse; live NEA readings from data.gov.sg
(`server/weather.py`: 10 s timeout, 2 retries, response checks, 5-minute cache; key from the app secret resource `datagov-key`,
exposed as `DATAGOV_API_KEY`). Heat rules live in one place, `server/heatrisk.py` (NEA bands Low < 31, Moderate 31–32.9, High ≥ 33 °C WBGT). Genie: Conversation API on space
`01f1c7ce26701e9d830c00124d3a37ed`. Messages: fixed, hand-written English / Chinese / Malay / Tamil wording (`server/messages.py`), sent to
linked Telegram groups or channels by the HeatGuard bot (`server/telegram.py`). Light and dark mode; phone layout with a bottom tab bar.

## Pages (for coordinators only)

| Page | What it shows |
|---|---|
| **My plan** (`/`) | Asks once for the centre's postal code, then: plain-words outlook, a tick-off to-do list in time order with links, nearby areas, nearest cool place |
| **Area** (`/area/<name>`) | Why to check this area, what to do, a message for its seniors in 4 languages naming their nearest cool place (Share on Telegram or copy), nearest cool place |
| **Weather** (`/weather`) | Today (default) and tomorrow for a place: measured heat, temperature and humidity now; NEA 2-hour and 24-hour forecasts; heat hour by hour (measured hours and estimated hours clearly marked); HeatGuard's afternoon forecast. Uses Singapore time and rolls over at midnight |
| **Activity check** (`/activity`) | Is a planned outdoor activity safe? Lower risk / Caution / High risk / Insufficient data, with reasons, precautions, safer times, a shorter option, nearby indoor venues and a warm-nights note |
| **Cool places** (`/cool-places`) | Nearest Community Clubs and libraries (map + list) from your location or a search, walking estimate, directions; opening hours shown as "not verified" |
| **Welfare checks** (`/welfare`) | Volunteers/coordinators only. **Fictional demo residents.** Mark done (with undo), unsuccessful attempt with outcome and remark, follow-up queue, full history of who changed what |
| **Ask a question** (`/ask`) | Genie answers in plain words (technical columns and SQL are hidden) |
| **Settings** (`/settings`) | Light / dark / same as device; Telegram setup (find the centre's group, link it, send a test) |

Technical material (model accuracy, replay of past hot days, Singapore-wide ranking) is kept out of the website; it lives in the notebooks,
the `gold_replay_*` / `ml_*` tables and `docs/decision-log.md`.

## API

| Endpoint | Returns |
|---|---|
| `GET /api/near?postal=<6 digits>` | Centre location (OneMap), tomorrow's heat there, plain-language plan and to-do, nearby areas, nearest cool places |
| `GET /api/area/{subzone}` | One area's row from the check-in list |
| `POST /api/genie` | `{question, conversation_id?}` → Genie answer |
| `GET /api/locate?q=` | OneMap search (postal code, address or place) |
| `GET /api/weather?lat&lon` | Today/tomorrow: live NEA readings and forecasts, today's measured heat by hour, HeatGuard forecast with hourly estimates |
| `POST /api/activity-check` | `{activity, exertion, latitude, longitude, place?, day, start, duration_min, older_adults}` → status, reasons, precautions, alternatives |
| `GET /api/cool-places?lat&lon` | Nearest CCs and libraries with walking estimate and directions link |
| `POST /api/message/compose` | `{level, for_date, language: en/zh/ms/ta, centre, cool, haze}` → message for seniors |
| `GET /api/telegram`, `POST /api/telegram/discover`, `POST/DELETE /api/telegram/chats`, `POST /api/telegram/send` | Bot status and linked groups; find groups the bot is in; link/unlink (coordinators); send with a `client_send_id` so a retry never posts twice |
| `GET /api/me`, `GET /api/welfare`, `POST /api/welfare/{id}/events` | Signed-in role; demo welfare list; append-only events (`expected_version` gives 409 on conflict, `client_event_id` makes retries safe) |
| `GET /api/health`, `POST /api/refresh` | Status; clear the 5-minute cache |

Errors come back as `{"error": "<plain-English message>"}`.

## Change and deploy

```bash
cd frontend && npm install && npm run build      # rebuilds ../static
git add -A && git commit && git push              # then pull the Databricks Git folder
databricks apps deploy heatguard-web --source-code-path /Workspace/Users/yubrajb2907@gmail.com/heatguard/webapp
```

Local development: run the API (`python -m server` from this folder with `DATABRICKS_CONFIG_PROFILE`, `DATABRICKS_WAREHOUSE_ID`,
`GENIE_SPACE_ID` set; optional `DATAGOV_API_KEY`, `TELEGRAM_BOT_TOKEN`, and `DEV_USER_EMAIL` to act as a signed-in user for Welfare
checks), then `npm run dev` in `frontend/` (proxies `/api` to port 8000).

Tests: `python -m pytest tests -q` from this folder (heat rules, messages in 4 languages, Telegram helpers, welfare state).

Free Edition stops apps after 24 hours: before a demo, open **Compute → Apps → heatguard-web** and click **Start**.
