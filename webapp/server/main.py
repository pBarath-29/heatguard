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


from .features import router as features_router      # noqa: E402  (Block Radar, activity check, weather, cooling places, welfare)

app.include_router(features_router)


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


@app.get("/api/area/{subzone}")
def area(subzone: str):
    df = checkin_rows()
    row = df[df["subzone_name"] == subzone.upper()]
    if row.empty:
        raise HTTPException(404, detail="We couldn't find that area. It may have fewer than 50 residents aged 65 or over.")
    return {"row": records(row)[0]}


def _haversine_km(lat1, lon1, lat2, lon2):
    import math
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


@app.get("/api/near")
def near(postal: str):
    """'My centre': postal code → location (OneMap) → tomorrow's heat there, nearby areas and cool spaces."""
    import re
    import requests
    code = postal.strip()
    if not re.fullmatch(r"\d{6}", code):
        raise HTTPException(400, detail="Please enter a 6-digit Singapore postal code, e.g. 098917.")
    try:
        res = requests.get("https://www.onemap.gov.sg/api/common/elastic/search",
                           params={"searchVal": code, "returnGeom": "Y", "getAddrDetails": "Y", "pageNum": 1}, timeout=15).json()
    except Exception as e:  # noqa: BLE001
        raise DataError("Couldn't reach OneMap to look up that postal code. Try again in a moment.", str(e)) from e
    hits = [r for r in res.get("results", []) if r.get("POSTAL") == code] or res.get("results", [])
    if not hits:
        raise HTTPException(404, detail="No address found for that postal code. Check the number and try again.")
    h = hits[0]
    lat, lon = float(h["LATITUDE"]), float(h["LONGITUDE"])
    place = {"name": h.get("BUILDING") if h.get("BUILDING") not in (None, "NIL") else h.get("SEARCHVAL"),
             "address": h.get("ADDRESS"), "postal": code, "latitude": lat, "longitude": lon}

    df = checkin_rows().copy()
    df["distance_km"] = [round(_haversine_km(lat, lon, a, b), 2) for a, b in zip(df["centroid_latitude"], df["centroid_longitude"])]
    nearby = df[df["distance_km"] <= 1.5].sort_values(["distance_km"])
    if nearby.empty:
        nearby = df.nsmallest(3, "distance_km")

    fc = query(f"""SELECT f.station_id, f.station_name, f.target_date, f.predicted_peak_wbgt_c, f.prob_moderate_plus, f.prob_high,
                          f.high_alert_threshold, s.latitude, s.longitude
                   FROM {S}.ml_wbgt_forecast f JOIN {S}.silver_wbgt_stations s USING (station_id)
                   WHERE f.target_date = (SELECT max(target_date) FROM {S}.ml_wbgt_forecast)""")
    point = None
    if len(fc):
        fc = fc.copy()
        fc["d"] = [max(0.2, _haversine_km(lat, lon, a, b)) for a, b in zip(fc["latitude"], fc["longitude"])]
        near3 = fc.nsmallest(3, "d")
        w = 1 / near3["d"] ** 2
        blend = lambda c: float((near3[c] * w).sum() / w.sum())
        prob_high = blend("prob_high")
        point = {"target_date": str(near3["target_date"].iloc[0]), "heat_wbgt_c": round(blend("predicted_peak_wbgt_c"), 1),
                 "prob_moderate_plus": round(blend("prob_moderate_plus"), 3), "prob_high": round(prob_high, 3),
                 "high_alert": bool(prob_high >= float(near3["high_alert_threshold"].max())),
                 "stations": [{"name": n, "distance_km": round(d, 1)} for n, d in zip(near3["station_name"], near3["d"])]}

    cool = query(f"SELECT name, space_type, latitude, longitude, street, postal_code FROM {S}.silver_cool_spaces").copy()
    cool["distance_km"] = [round(_haversine_km(lat, lon, a, b), 2) for a, b in zip(cool["latitude"], cool["longitude"])]
    cool_near = cool.nsmallest(3, "distance_km")
    return {"place": place, "point": point, "areas": records(nearby), "cool_spaces": records(cool_near),
            "plan": centre_plan(point, nearby, cool_near, df)}


TIER_ORDER = {"Start here": 1, "Check in": 2, "Routine": 3}


def centre_plan(point, nearby, cool, all_rows):
    """Plain-language plan for a coordinator: how hot, what to do and when (wording follows the HeatGuard rulebook)."""
    ordered = nearby.assign(_t=nearby["tier"].map(TIER_ORDER)).sort_values(["_t", "risk_score"], ascending=[True, False])
    focus = [str(n).title() for n in ordered["subzone_name"].head(2)]
    focus_text = " and ".join(focus) if focus else "your area"
    closest = nearby.nsmallest(1, "distance_km")
    psi_band = closest["psi_band"].iloc[0] if len(closest) else None
    cool_name = cool["name"].iloc[0] if len(cool) else "the nearest Community Club"
    for_date = all_rows["for_date"].max()
    for_date = str(for_date.date() if hasattr(for_date, "date") else for_date)[:10] if for_date is not None else None

    if point is None:
        heat = ordered["heat_band"].iloc[0] if len(ordered) else "Low"
        very_hot = heat == "High"
    else:
        heat = "High" if point["heat_wbgt_c"] >= 33 else "Moderate" if point["heat_wbgt_c"] >= 31 else "Low"
        very_hot = heat == "High" or point["high_alert"]
    if very_hot:
        level, title_, sub = "very_hot", "Very hot afternoon", "High heat stress is possible around your centre. Hottest between 12 pm and 4 pm."
    elif heat == "Moderate":
        level, title_, sub = "hot", "Hot afternoon", "Moderate heat stress around your centre. Hottest between 12 pm and 4 pm."
    else:
        level, title_, sub = "normal", "Normal afternoon", "No heat stress expected around your centre."

    haze = None
    if psi_band in ("Unhealthy", "Very unhealthy", "Hazardous"):
        haze = {"band": psi_band, "text": f"Haze is {psi_band.lower()}: keep windows closed and limit time outdoors."}

    todo = []
    if level == "very_hot":
        todo = [
            {"id": "send", "when": "Tonight", "text": "Send the heat reminder to your seniors (ready below)."},
            {"id": "call", "when": "Before 11 am", "text": f"Call or visit seniors who live alone, starting with {focus_text}."},
            {"id": "indoors", "when": "12 pm – 4 pm", "text": f"Remind them to stay indoors, drink water often, and come to {cool_name} if home is too hot."},
        ]
    elif level == "hot":
        todo = [
            {"id": "send", "when": "Tonight", "text": "Send the heat reminder to your seniors (ready below)."},
            {"id": "call", "when": "Tomorrow morning", "text": f"Phone seniors who live alone, starting with {focus_text}."},
            {"id": "indoors", "when": "12 pm – 4 pm", "text": "Remind them to avoid going out and to keep drinking water."},
        ]
    else:
        todo = [{"id": "routine", "when": "Tomorrow", "text": "Routine check-ins. No extra heat steps needed."}]
    if haze:
        todo.append({"id": "haze", "when": "In the morning", "text": "Check that seniors with heart or lung conditions have their medication. Keep windows closed."})
    lead = ordered["subzone_name"].iloc[0] if len(ordered) else None
    return {"for_date": for_date, "level": level, "title": title_, "subtitle": sub, "haze": haze, "todo": todo,
            "focus_areas": focus, "message_area": lead}


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
    centre: Optional[str] = None


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
    text, used_ai = ai.write_message(records(row)[0], body.language, body.audience, body.centre)
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
