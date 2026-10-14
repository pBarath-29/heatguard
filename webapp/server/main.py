"""HeatGuard web app: JSON API for the React frontend, plus the built frontend itself."""
import datetime as dt
import os
import pathlib

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from typing import Optional

from pydantic import BaseModel, Field

from . import ai
from .db import S, ConfigError, DataError, clear_cache, query, records, setting, today_sgt

app = FastAPI(title="HeatGuard", docs_url="/api/docs", openapi_url="/api/openapi.json")
STATIC = pathlib.Path(__file__).resolve().parent.parent / "static"


@app.exception_handler(DataError)
async def data_error(_: Request, e: DataError):
    return JSONResponse(status_code=503, content={"error": str(e), "detail": e.detail})


@app.exception_handler(ConfigError)
async def config_error(_: Request, e: ConfigError):
    return JSONResponse(status_code=503, content={"error": str(e), "detail": ""})


# ---------------- data ----------------

def checkin_rows():
    return query(f"SELECT * FROM {S}.gold_checkin_list ORDER BY rank")


@app.get("/api/health")
def health():
    configured = {k: bool(os.environ.get(k)) for k in ("DATABRICKS_WAREHOUSE_ID", "GENIE_SPACE_ID", "SERVING_ENDPOINT")}
    return {"ok": True, "configured": configured, "today_sgt": str(today_sgt())}


@app.post("/api/refresh")
def refresh():
    clear_cache()
    return {"ok": True}


@app.get("/api/checkin")
def checkin():
    df = checkin_rows()
    today = today_sgt()
    for_date = df["for_date"].max() if len(df) else None
    for_date = for_date if for_date is None or isinstance(for_date, dt.date) else for_date.date()
    is_fc = bool(df["heat_is_forecast"].fillna(False).any()) if len(df) else False
    basis = df["heat_basis"].dropna().iloc[0] if len(df) and df["heat_basis"].notna().any() else ""
    if not len(df):
        status = "empty"
    elif not is_fc:
        status = "observed"
    elif for_date < today:
        status = "past"
    elif for_date == today:
        status = "today"
    else:
        status = "tomorrow"
    return {"meta": {"for_date": str(for_date) if for_date else None, "today": str(today), "status": status,
                     "heat_basis": basis, "is_forecast": is_fc, "areas": int(len(df))},
            "rows": records(df)}


@app.get("/api/area/{subzone}")
def area(subzone: str):
    df = checkin_rows()
    row = df[df["subzone_name"] == subzone.upper()]
    if row.empty:
        raise HTTPException(404, detail="That area isn't on the check-in list (it may have fewer than 50 residents aged 65+).")
    stations = query(f"SELECT * FROM {S}.gold_subzone_station_weights WHERE subzone_name = :sz ORDER BY station_rank", {"sz": subzone.upper()})
    ids = stations["station_id"].tolist()
    peaks = forecasts = None
    if ids:
        id_list = ",".join("'" + i.replace("'", "") + "'" for i in ids)
        peaks = query(f"""SELECT p.station_id, s.station_name, p.date_sgt, p.afternoon_peak_wbgt_c
                          FROM {S}.silver_wbgt_daily_peak p JOIN {S}.silver_wbgt_stations s USING (station_id)
                          WHERE p.station_id IN ({id_list}) AND p.afternoon_readings >= 12 AND p.date_sgt >= date_sub(current_date(), 30)
                          ORDER BY p.date_sgt""")
        forecasts = query(f"""SELECT station_id, station_name, target_date, predicted_peak_wbgt_c, prob_high
                              FROM {S}.ml_wbgt_forecast WHERE station_id IN ({id_list})
                                AND target_date = (SELECT max(target_date) FROM {S}.ml_wbgt_forecast)""")
    weights = query(f"SELECT * FROM {S}.gold_score_weights")
    return {"row": records(row)[0], "total_areas": int(len(df)), "stations": records(stations),
            "peaks": records(peaks), "forecasts": records(forecasts), "weights": records(weights)}


@app.get("/api/now")
def now():
    stations = query(f"SELECT * FROM {S}.gold_wbgt_station_latest ORDER BY wbgt_c DESC")
    haze = query(f"SELECT * FROM {S}.gold_haze_latest ORDER BY region")
    daily = query(f"SELECT * FROM {S}.gold_daily_summary WHERE date_sgt >= date_sub(current_date(), 30) ORDER BY date_sgt")
    latest = stations["latest_reading_ts"].max() if len(stations) else None
    return {"latest_reading_ts": None if latest is None else latest.isoformat(),
            "stations": records(stations), "haze": records(haze), "daily": records(daily)}


@app.get("/api/cool-spaces")
def cool_spaces():
    return records(query(f"SELECT name, space_type, latitude, longitude, street, postal_code FROM {S}.silver_cool_spaces"))


@app.get("/api/accuracy")
def accuracy():
    ev = query(f"SELECT * FROM {S}.ml_model_evaluation")
    backtest = query(f"""SELECT target_date, avg(actual_peak_wbgt_c) AS actual, avg(predicted_peak_wbgt_c) AS heatguard,
                                avg(baseline_peak_wbgt_c) AS baseline, max(baseline_name) AS baseline_name
                         FROM {S}.ml_backtest_predictions GROUP BY target_date ORDER BY target_date""")
    importance = query(f"SELECT feature, mae_increase_c FROM {S}.ml_feature_importance ORDER BY mae_increase_c DESC")
    track = query(f"""SELECT target_date, count(*) AS stations, avg(abs_error_c) AS avg_error_c,
                             avg(CASE WHEN actual_band = predicted_band THEN 1.0 ELSE 0.0 END) AS band_correct,
                             sum(CASE WHEN actual_band = 'High' THEN 1 ELSE 0 END) AS stations_high,
                             sum(CASE WHEN high_alert AND actual_band = 'High' THEN 1 ELSE 0 END) AS high_caught
                      FROM {S}.ml_forecast_track_record WHERE actual_peak_wbgt_c IS NOT NULL
                      GROUP BY target_date ORDER BY target_date DESC""")
    ev = ev.rename(columns={"station-days": "station_days"})
    return {"evaluation": records(ev), "backtest": records(backtest), "importance": records(importance), "track_record": records(track)}


@app.get("/api/about")
def about():
    return {"weights": records(query(f"SELECT * FROM {S}.gold_score_weights")),
            "rulebook": records(query(f"SELECT * FROM {S}.gold_rulebook"))}


# ---------------- AI ----------------

class AskBody(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    conversation_id: Optional[str] = None


@app.post("/api/genie")
def genie(body: AskBody):
    return ai.ask_genie(body.question.strip(), body.conversation_id)


class MessageBody(BaseModel):
    subzone: str
    language: str
    audience: str


@app.get("/api/message/options")
def message_options():
    return {"languages": ai.LANGUAGES, "audiences": [{"id": "seniors", "label": "Message to seniors"},
                                                      {"id": "staff", "label": "Briefing for staff and volunteers"}]}


@app.post("/api/message")
def message(body: MessageBody):
    df = checkin_rows()
    row = df[df["subzone_name"] == body.subzone.upper()]
    if row.empty:
        raise HTTPException(404, detail="That area isn't on the check-in list.")
    text, used_ai = ai.write_message(records(row)[0], body.language, body.audience)
    return {"text": text, "used_ai": used_ai}


# ---------------- frontend ----------------

if (STATIC / "assets").exists():
    app.mount("/assets", StaticFiles(directory=STATIC / "assets"), name="assets")


@app.get("/{path:path}", include_in_schema=False)
def spa(path: str):
    if path.startswith("api/"):
        raise HTTPException(404)
    file = STATIC / path
    if path and file.is_file():
        return FileResponse(file)
    index = STATIC / "index.html"
    if not index.exists():
        return JSONResponse({"error": "The website hasn't been built. Run `npm run build` in webapp/frontend."}, status_code=500)
    return FileResponse(index, headers={"Cache-Control": "no-cache"})
