# HeatGuard app (Databricks App)

A Streamlit app for Active Ageing Centre coordinators: tomorrow's ranked check-in list, the reasons behind it, current heat and haze,
a Genie chat, forecast accuracy, and a multilingual message writer.

**Live app:** https://heatguard-7474645045833960.aws.databricksapps.com (sign in with the team's Databricks account)

## Pages

| Page | For |
|---|---|
| Check-in list | Tomorrow's areas ranked by risk, with the reason, the action, a map, filters and CSV download |
| Why here? | One area's score breakdown, who lives there, heat confidence, nearest cool space, recent heat |
| Heat & haze now | Latest WBGT per station, PSI per region, last 30 days |
| Ask HeatGuard | Genie chat over the gold tables (space `01f1c7ce26701e9d830c00124d3a37ed`) |
| Forecast accuracy | Test-period results vs simple rules, live track record, what the model relies on |
| About & help | How it works, weights, rulebook, glossary, limitations, data sources |

## Resources (set on the app; read via `app.yaml`)

| Resource key | Resource | Permission |
|---|---|---|
| `sql-warehouse` | Serverless Starter Warehouse `e4c9f81b068eb070` | Can use |
| `genie-space` | Genie space "HeatGuard: ask about heat risk" | Can run |
| `serving-endpoint` | `databricks-meta-llama-3-3-70b-instruct` | Can query |

The app's service principal also needs to read the HeatGuard tables:

```sql
GRANT USE CATALOG ON CATALOG workspace TO `<app service principal client id>`;
GRANT USE SCHEMA, SELECT ON SCHEMA workspace.heatguard TO `<app service principal client id>`;
```

## Deploy a new version

1. Push to `main`, then pull the Databricks Git folder (Workspace → `heatguard` → Pull).
2. `databricks apps deploy heatguard --source-code-path /Workspace/Users/yubrajb2907@gmail.com/heatguard/app`

Free Edition stops apps after 24 hours: before a demo, open **Compute → Apps → heatguard** and click **Start** if it is stopped.

## Run locally

```bash
pip install -r requirements.txt
export DATABRICKS_CONFIG_PROFILE=heatguard DATABRICKS_WAREHOUSE_ID=e4c9f81b068eb070 \
       GENIE_SPACE_ID=01f1c7ce26701e9d830c00124d3a37ed SERVING_ENDPOINT=databricks-meta-llama-3-3-70b-instruct
streamlit run app.py
```

## Error handling

Every query goes through `heatguard_app/data.py::load`, which caches results for 5 minutes, shows a spinner (the warehouse can take
up to 30 seconds to wake), and turns failures into a plain-English message with a **Try again** button. The pages also warn when the
list is for a past day, when the forecast is missing (falls back to observed heat), and when live readings are old. If the message
writer fails, the plain rulebook text is shown instead; Genie timeouts and errors are shown in the chat.
