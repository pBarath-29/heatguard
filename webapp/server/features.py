"""API for the coordinator features: activity check, today/tomorrow weather, cooling places, welfare checklist, ready-to-send
messages and Telegram sending."""
from __future__ import annotations

import datetime as dt
import logging
import re
import uuid
from typing import Optional

import pandas as pd
import requests
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from . import heatrisk as hr
from . import messages as msg
from . import telegram as tg
from . import weather as wx
from . import welfare as wf
from .db import S, DataError, execute, query, records

router = APIRouter(prefix="/api")
log = logging.getLogger("heatguard")
RAIN = re.compile(r"shower|rain|thunder|drizzle", re.I)


# ======================================================================= locations
def onemap_search(q: str, limit: int = 5) -> list[dict]:
    try:
        r = requests.get("https://www.onemap.gov.sg/api/common/elastic/search",
                         params={"searchVal": q, "returnGeom": "Y", "getAddrDetails": "Y", "pageNum": 1}, timeout=12)
        r.raise_for_status()
        results = r.json().get("results") or []
    except Exception as e:  # noqa: BLE001
        raise DataError("Couldn't reach OneMap to look up that place. Check your connection and try again.", type(e).__name__) from e
    out, seen = [], set()
    for x in results:
        try:
            lat, lon = float(x["LATITUDE"]), float(x["LONGITUDE"])
        except (KeyError, ValueError):
            continue
        name = x.get("BUILDING") if x.get("BUILDING") not in (None, "", "NIL") else x.get("SEARCHVAL")
        key = (round(lat, 4), round(lon, 4))
        if key in seen:
            continue
        seen.add(key)
        out.append({"name": (name or "").title(), "address": (x.get("ADDRESS") or "").title(), "postal": x.get("POSTAL"), "latitude": lat, "longitude": lon})
        if len(out) == limit:
            break
    return out


@router.get("/locate")
def locate(q: str):
    q = q.strip()
    if not 2 <= len(q) <= 100:
        raise HTTPException(400, detail="Type a postal code, address or place name (2–100 characters).")
    results = onemap_search(q)
    if not results:
        raise HTTPException(404, detail="No place found. Try a 6-digit postal code or a fuller address.")
    return {"results": results, "source": "OneMap (Singapore Land Authority)"}


def _check_point(lat: float, lon: float):
    if not (1.15 <= lat <= 1.48 and 103.55 <= lon <= 104.10):
        raise HTTPException(400, detail="That location is outside Singapore.")


# ======================================================================= forecast for a point
def _day(which: str) -> dt.date:
    today = hr.today_sgt()
    if which == "today":
        return today
    if which == "tomorrow":
        return today + dt.timedelta(days=1)
    raise HTTPException(400, detail="Choose today or tomorrow.")


def point_forecast(lat: float, lon: float, day: dt.date) -> dict | None:
    """Tomorrow-style forecast at a point: blend of the 3 nearest stations (closer counts more). None if no forecast exists for `day`."""
    fc = query(f"""SELECT f.station_id, f.station_name, f.feature_date, f.predicted_peak_wbgt_c, f.prob_moderate_plus, f.prob_high,
                          f.high_alert_threshold, f.model_version, f.scored_at, s.latitude, s.longitude
                   FROM {S}.ml_wbgt_forecast f JOIN {S}.silver_wbgt_stations s USING (station_id)
                   WHERE f.target_date = :d""", {"d": day.isoformat()})
    if fc.empty:
        return None
    try:
        prof = query(f"SELECT station_id, hour, offset_median_c FROM {S}.gold_station_hour_profile")
    except DataError:                                                   # no daily pattern yet → peak only, no hourly estimates
        prof = pd.DataFrame(columns=["station_id", "hour", "offset_median_c"])
    fc = fc.assign(d=[max(0.2, hr.haversine_km((lat, lon), (a, b))) for a, b in zip(fc.latitude, fc.longitude)]).nsmallest(3, "d")
    w = {r.station_id: 1 / r.d ** 2 for r in fc.itertuples()}
    tot = sum(w.values())
    blend = lambda col: float(sum(w[r.station_id] * getattr(r, col) for r in fc.itertuples()) / tot)
    offsets: dict[int, float] = {}
    for h in range(24):
        rows = prof[(prof.hour == h) & prof.station_id.isin(w.keys())]
        if len(rows):
            ww = sum(w[s] for s in rows.station_id)
            offsets[h] = float(sum(w[s] * o for s, o in zip(rows.station_id, rows.offset_median_c)) / ww)
    peak = round(blend("predicted_peak_wbgt_c"), 1)
    return {"date": day.isoformat(), "peak_c": peak, "band": hr.band(peak), "prob_high": round(blend("prob_high"), 3),
            "prob_moderate_plus": round(blend("prob_moderate_plus"), 3), "alert_threshold": float(fc.high_alert_threshold.max()),
            "hourly": hr.hourly_estimate(peak, offsets), "made_on": str(fc.feature_date.max())[:10], "model_version": str(fc.model_version.max()),
            "scored_at": fc.scored_at.max().isoformat() if fc.scored_at.notna().any() else None,
            "stations": [{"name": r.station_name, "distance_km": round(r.d, 1)} for r in fc.itertuples()]}


def _periods_for(periods: dict | None, day: dt.date):
    if not periods:
        return []
    return [p for p in periods["periods"] if p["start"][:10] == day.isoformat() or (p.get("end") or "")[:10] == day.isoformat()]


# ======================================================================= weather (today & tomorrow)
@router.get("/weather")
def weather(lat: float, lon: float):
    _check_point(lat, lon)
    today = hr.today_sgt()
    tomorrow = today + dt.timedelta(days=1)
    now = wx.current(lat, lon)
    observed, obs_err = wx._safe(wx.wbgt_today_by_hour, lat, lon, today)
    fc_today = fc_tomorrow = None
    notes = list(now["notes"])
    try:
        fc_today, fc_tomorrow = point_forecast(lat, lon, today), point_forecast(lat, lon, tomorrow)
    except DataError as e:
        notes.append(f"HeatGuard forecast: {e}")
    if obs_err:
        notes.append(f"Today's readings: {obs_err}")
    return {"today": {"date": today.isoformat(), "now": {k: now[k] for k in ("wbgt", "air_temp", "humidity")}, "two_hour": now["two_hour"],
                      "observed_by_hour": observed, "forecast": fc_today, "nea_periods": _periods_for(now["periods"], today)},
            "tomorrow": {"date": tomorrow.isoformat(), "forecast": fc_tomorrow, "nea_periods": _periods_for(now["periods"], tomorrow)},
            "nea_24h": {k: v for k, v in (now["periods"] or {}).items() if k != "periods"} or None,
            "notes": notes, "fetched_at": now["fetched_at"],
            "sources": ["NEA via data.gov.sg (live readings and forecasts)", "HeatGuard forecast model (hourly values are estimates)"]}


# ======================================================================= cooling places
@router.get("/cool-places")
def cool_places(lat: float, lon: float, limit: int = 8):
    _check_point(lat, lon)
    cs = query(f"SELECT name, space_type, latitude, longitude, street, postal_code FROM {S}.silver_cool_spaces")
    out = []
    for r in cs.itertuples():
        km = hr.haversine_km((lat, lon), (r.latitude, r.longitude))
        walk_km = km * hr.ROUTE_DETOUR
        out.append({"name": r.name, "type": r.space_type, "latitude": r.latitude, "longitude": r.longitude,
                    "address": ", ".join(x for x in [r.street, r.postal_code and f"Singapore {r.postal_code}"] if x and x == x),
                    "straight_km": round(km, 2), "walk_min_estimate": max(1, round(walk_km / hr.WALK_KMH * 60)),
                    "opening_hours": None, "accessibility": None,
                    "directions_url": f"https://www.google.com/maps/dir/?api=1&origin={lat},{lon}&destination={r.latitude},{r.longitude}&travelmode=walking"})
    out.sort(key=lambda x: x["straight_km"])
    heat, err = wx._safe(wx.wbgt_now, lat, lon)
    return {"places": out[:max(1, min(limit, 20))], "heat_now": heat, "heat_note": err,
            "coverage": "Community Clubs (People's Association) and public libraries (NLB) only. Opening hours and accessibility are not in these datasets — check before you go.",
            "source": "data.gov.sg datasets loaded into HeatGuard"}


# ======================================================================= activity safety check
class ActivityBody(BaseModel):
    activity: str = Field(min_length=1, max_length=80)
    exertion: str = Field(pattern="^(light|moderate|vigorous)$")
    latitude: float
    longitude: float
    place: Optional[str] = Field(default=None, max_length=120)
    day: str = Field(pattern="^(today|tomorrow)$")
    start: str = Field(pattern=r"^\d{2}:\d{2}$")
    duration_min: int = Field(ge=10, le=480)
    older_adults: bool = True


@router.post("/activity-check")
def activity_check(b: ActivityBody):
    _check_point(b.latitude, b.longitude)
    try:
        start = dt.datetime.strptime(b.start, "%H:%M").time()
    except ValueError:
        raise HTTPException(400, detail="Please enter the start time as HH:MM.")
    day = _day(b.day)
    now_sgt = dt.datetime.now(hr.SGT)
    if b.day == "today" and dt.datetime.combine(day, start, tzinfo=hr.SGT) < now_sgt:
        raise HTTPException(400, detail="That time has already passed today. Choose a later time or tomorrow.")
    end_dt = dt.datetime.combine(day, start) + dt.timedelta(minutes=b.duration_min)
    fc = point_forecast(b.latitude, b.longitude, day)
    nea, nea_err = wx._safe(wx.periods_24h, b.latitude, b.longitude)
    window_periods = [p for p in _periods_for(nea, day)
                      if p["start"] < end_dt.strftime("%Y-%m-%dT%H:%M") and (p.get("end") or "9999") > f"{day.isoformat()}T{b.start}"]
    rain = any(RAIN.search(p["forecast"]) for p in window_periods)
    base = {"activity": b.activity, "place": b.place, "date": day.isoformat(), "start": b.start, "end": end_dt.strftime("%H:%M"),
            "duration_min": b.duration_min, "exertion": b.exertion, "older_adults": b.older_adults, "nea_periods": window_periods,
            "disclaimer": "This is forecast-based guidance from HeatGuard, not a medical assessment or an official NEA warning. Always follow NEA's latest advisories on the day."}
    if fc is None or not fc["hourly"]:
        return {**base, "status": "Insufficient data", "reasons": [
            f"HeatGuard has no heat forecast for {day:%A %d %B} yet." if fc is None else "The usual daily heat pattern for this location is missing.",
            "Tomorrow's forecast is published every afternoon at about 4 pm."], "precautions": ["Check NEA's heat stress advisory before the activity."],
            "alternatives": [], "indoor_options": [], "forecast": None, "sources": ["NEA via data.gov.sg"], "nea_note": nea_err}
    if fc["made_on"] < (day - dt.timedelta(days=1)).isoformat():
        return {**base, "status": "Insufficient data", "reasons": [f"The latest forecast was made on {fc['made_on']}, which is too old for {day:%A %d %B}."],
                "precautions": ["Try again after this afternoon's update (about 4 pm)."], "alternatives": [], "indoor_options": [], "forecast": None, "sources": []}
    a = hr.assess_window(fc["hourly"], start, b.duration_min, older_adults=b.older_adults, exertion=b.exertion,
                         prob_high=fc["prob_high"], alert_threshold=fc["alert_threshold"], rain_expected=rain)
    not_before = (now_sgt + dt.timedelta(minutes=30)).time() if b.day == "today" else None
    alts = [] if a.status == "Lower risk" else hr.safer_times(fc["hourly"], b.duration_min, older_adults=b.older_adults, exertion=b.exertion,
                                                               current_status=a.status, not_before=not_before)
    indoor = []
    if a.status in ("High risk", "Caution"):
        indoor = cool_places(b.latitude, b.longitude, limit=3)["places"]
    shorter = None
    if a.status != "Lower risk" and b.duration_min > 30:
        s30 = hr.assess_window(fc["hourly"], start, 30, older_adults=b.older_adults, exertion=b.exertion)
        if s30.status != a.status:
            shorter = {"duration_min": 30, "status": s30.status}
    nights = query(f"""SELECT n.night_date, n.night_min_c, n.station_name, n.latitude, n.longitude FROM {S}.gold_night_min_temp n
                       WHERE n.night_date >= date_sub(current_date(), 10)""")
    warm = None
    if len(nights):
        nights = nights.assign(d=[hr.haversine_km((b.latitude, b.longitude), (x, y)) for x, y in zip(nights.latitude, nights.longitude)])
        st = nights.nsmallest(1, "d").station_name.iloc[0]
        series = [(r.night_date, r.night_min_c) for r in nights[nights.station_name == st].itertuples()]
        streak = hr.warm_night_streak(series)
        if streak:
            warm = {"streak": streak, "station": st, "threshold_c": hr.WARM_NIGHT_MIN_C,
                    "text": f"The last {streak} night{'s' if streak > 1 else ''} stayed above {hr.WARM_NIGHT_MIN_C:.0f} °C near {st}. Bodies recover less after warm nights — consider a shorter session, more rest breaks and plenty of water."}
    return {**base, "status": a.status, "reasons": a.reasons, "precautions": a.precautions,
            "window": {"hours": a.window_hours, "max_c": a.window_max_c, "band": hr.band(a.window_max_c)},
            "alternatives": alts, "shorter": shorter, "indoor_options": indoor, "warm_nights": warm,
            "forecast": {k: fc[k] for k in ("date", "peak_c", "band", "prob_high", "prob_moderate_plus", "made_on", "model_version", "scored_at", "stations", "hourly")},
            "uncertainty": f"Hourly values are estimates from the forecast afternoon peak and the usual daily pattern at nearby stations; typical forecast error is about ±{hr.TYPICAL_ERROR_C} °C.",
            "sources": ["HeatGuard forecast model (Databricks)", "NEA 24-hour forecast via data.gov.sg", "NEA heat-stress bands: Low < 31, Moderate 31–32.9, High ≥ 33 °C WBGT"],
            "nea_note": nea_err}


# ======================================================================= welfare checklist (demo data only)
def _email(request: Request) -> str | None:
    return request.headers.get("X-Forwarded-Email") or request.headers.get("x-forwarded-email") or __import__("os").environ.get("DEV_USER_EMAIL")


def _role(email: str | None) -> str | None:
    if not email:
        return None
    df = query(f"SELECT role FROM {S}.app_volunteers WHERE lower(email) = lower(:e)", {"e": email}, cache=False)
    return df.role.iloc[0] if len(df) else None


def _require(request: Request) -> tuple[str, str]:
    email = _email(request)
    role = _role(email)
    if not email:
        raise HTTPException(401, detail="Please sign in to see welfare checks.")
    if role not in ("volunteer", "coordinator"):
        raise HTTPException(403, detail="You don't have access to welfare checks yet. Ask your coordinator to add you.")
    return email, role


@router.get("/me")
def me(request: Request):
    email = _email(request)
    try:
        role = _role(email)
    except DataError:
        role = None
    return {"signed_in": bool(email), "role": role, "can_view_welfare": role in ("volunteer", "coordinator")}


def _events(resident_id: str | None = None):
    where = "WHERE resident_id = :r" if resident_id else ""
    return query(f"""SELECT event_id, client_event_id, resident_id, action, outcome, remark, by_email, at FROM {S}.app_welfare_events {where}
                     ORDER BY at""", {"r": resident_id} if resident_id else None, cache=False)


@router.get("/welfare")
def welfare_list(request: Request):
    _require(request)
    res = records(query(f"SELECT * FROM {S}.app_welfare_residents ORDER BY block, unit", cache=False))
    ev = records(_events())
    by_res: dict[str, list] = {}
    for e in ev:
        by_res.setdefault(e["resident_id"], []).append(e)
    out = []
    for r in res:
        history = by_res.get(r["resident_id"], [])
        out.append({**r, "state": wf.state(history), "history": [{k: e[k] for k in ("action", "outcome", "remark", "by_email", "at")} for e in history]})
    return {"residents": out, "demo": any(r.get("demo") for r in res),
            "notice": "DEMO DATA — every resident here is fictional and was created for demonstration. No real personal information is stored."}


class EventBody(BaseModel):
    action: str = Field(max_length=20)
    outcome: Optional[str] = Field(default=None, max_length=20)
    remark: Optional[str] = Field(default=None, max_length=1200)
    expected_version: int = Field(ge=0)
    client_event_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9-]+$")


@router.post("/welfare/{resident_id}/events")
def welfare_event(resident_id: str, body: EventBody, request: Request):
    email, _ = _require(request)
    if not re.fullmatch(r"[A-Za-z0-9-]{1,40}", resident_id):
        raise HTTPException(400, detail="Unknown resident.")
    if query(f"SELECT 1 FROM {S}.app_welfare_residents WHERE resident_id = :r", {"r": resident_id}, cache=False).empty:
        raise HTTPException(404, detail="That resident isn't on the list.")
    try:
        ev = wf.validate(body.model_dump())
    except wf.WelfareError as e:
        raise HTTPException(400, detail=str(e))
    history = records(_events(resident_id))
    if any(h["client_event_id"] == body.client_event_id for h in history):        # duplicate submit (e.g. double tap / retry)
        return {"state": wf.state(history), "duplicate": True}
    try:
        wf.check_version(wf.state(history)["version"], body.expected_version)
    except wf.WelfareError as e:
        raise HTTPException(409, detail=str(e))
    execute(f"""INSERT INTO {S}.app_welfare_events (event_id, client_event_id, resident_id, action, outcome, remark, by_email, at)
                VALUES (:id, :cid, :r, :a, :o, :rm, :by, current_timestamp())""",
            {"id": str(uuid.uuid4()), "cid": body.client_event_id, "r": resident_id, "a": ev["action"], "o": ev.get("outcome"),
             "rm": ev.get("remark"), "by": email})
    log.info("welfare event saved: action=%s", ev["action"])                         # no personal data in logs
    history = records(_events(resident_id))
    return {"state": wf.state(history), "history": [{k: e[k] for k in ("action", "outcome", "remark", "by_email", "at")} for e in history]}


# ======================================================================= ready-to-send messages (fixed translations)
class ComposeBody(BaseModel):
    level: str = Field(pattern="^(very_hot|hot|normal)$")
    for_date: dt.date
    language: str = Field(pattern="^(en|zh|ms|ta|all)$")
    centre: str = Field(default="", max_length=80)
    cool: Optional[str] = Field(default=None, max_length=80)
    haze: bool = False


@router.get("/message/languages")
def message_languages():
    return {"languages": [{"code": k, "label": v} for k, v in msg.LANGUAGES.items()]}


@router.post("/message/compose")
def message_compose(b: ComposeBody):
    try:
        args = dict(level=b.level, day=b.for_date, today=hr.today_sgt(), centre=b.centre, cool=b.cool, haze=b.haze)
        text = msg.compose_all(**args) if b.language == "all" else msg.compose(language=b.language, **args)
    except msg.MessageError as e:
        raise HTTPException(400, detail=str(e))
    return {"text": text, "language": b.language}


# ======================================================================= Telegram (groups and channels only)
def _coordinator(request: Request) -> str:
    email, role = _require(request)
    if role != "coordinator":
        raise HTTPException(403, detail="Only coordinators can set up or send Telegram messages.")
    return email


def _tg(fn, *args):
    try:
        return fn(*args)
    except tg.TelegramError as e:
        log.warning("telegram call failed: %s", e.detail)                            # detail never contains the token
        raise HTTPException(502, detail=str(e))


def _linked_chats() -> list[dict]:
    df = query(f"""SELECT chat_id, title, chat_type, by_email AS linked_by, at AS linked_at FROM (
                     SELECT *, row_number() OVER (PARTITION BY chat_id ORDER BY at DESC) AS n FROM {S}.app_telegram_chats)
                   WHERE n = 1 AND action = 'link' ORDER BY title""", cache=False)
    return records(df)


@router.get("/telegram")
def telegram_status(request: Request):
    email = _email(request)
    try:
        role = _role(email)
    except DataError:
        role = None
    out = {"configured": tg.configured(), "bot": None, "bot_error": None, "chats": [], "can_manage": role == "coordinator"}
    if out["configured"]:
        try:
            out["bot"] = tg.bot_info()
        except tg.TelegramError as e:
            out["bot_error"] = str(e)
    if role in ("volunteer", "coordinator"):
        try:
            out["chats"] = _linked_chats()
        except DataError:
            out["chats"] = []
    return out


@router.post("/telegram/discover")
def telegram_discover(request: Request):
    _coordinator(request)
    found = _tg(tg.discover)
    linked = {c["chat_id"] for c in _linked_chats()}
    return {"chats": [{**c, "linked": c["chat_id"] in linked} for c in found]}


class LinkBody(BaseModel):
    chat_id: str = Field(pattern=r"^-?\d{1,20}$")


@router.post("/telegram/chats")
def telegram_link(b: LinkBody, request: Request):
    email = _coordinator(request)
    match = [c for c in _tg(tg.discover) if c["chat_id"] == b.chat_id]       # only groups the bot is really in
    if not match:
        raise HTTPException(404, detail="The bot can't see that group. Add the bot to it, post a message there, then try again.")
    c = match[0]
    execute(f"""INSERT INTO {S}.app_telegram_chats (chat_id, title, chat_type, action, by_email, at)
                VALUES (:id, :t, :ty, 'link', :by, current_timestamp())""", {"id": c["chat_id"], "t": c["title"][:120], "ty": c["chat_type"], "by": email})
    return {"chats": _linked_chats()}


@router.delete("/telegram/chats/{chat_id}")
def telegram_unlink(chat_id: str, request: Request):
    email = _coordinator(request)
    current = {c["chat_id"]: c for c in _linked_chats()}
    if chat_id not in current:
        raise HTTPException(404, detail="That group isn't linked.")
    c = current[chat_id]
    execute(f"""INSERT INTO {S}.app_telegram_chats (chat_id, title, chat_type, action, by_email, at)
                VALUES (:id, :t, :ty, 'unlink', :by, current_timestamp())""", {"id": chat_id, "t": c["title"], "ty": c["chat_type"], "by": email})
    return {"chats": _linked_chats()}


class SendBody(BaseModel):
    chat_ids: list[str] = Field(min_length=1, max_length=10)
    text: str = Field(min_length=1, max_length=tg.MAX_TEXT)
    audience: Optional[str] = Field(default=None, pattern="^(seniors|test)$")
    language: Optional[str] = Field(default=None, pattern="^(en|zh|ms|ta|all)$")
    client_send_id: str = Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9-]+$")


@router.post("/telegram/send")
def telegram_send(b: SendBody, request: Request):
    email = _coordinator(request)
    try:
        text = tg.check_text(b.text)
    except tg.TelegramError as e:
        raise HTTPException(400, detail=str(e))
    linked = {c["chat_id"]: c for c in _linked_chats()}
    done = set(query(f"SELECT chat_id FROM {S}.app_telegram_sends WHERE client_send_id = :c AND ok", {"c": b.client_send_id},
                     cache=False).chat_id)
    results = []
    for cid in dict.fromkeys(b.chat_ids):                                            # keep order, drop repeats
        chat = linked.get(cid)
        if chat is None:
            results.append({"chat_id": cid, "title": None, "ok": False, "error": "This group isn't linked any more."}); continue
        if cid in done:                                                              # double tap / retry: never post twice
            results.append({"chat_id": cid, "title": chat["title"], "ok": True, "already_sent": True}); continue
        ok, err = True, None
        try:
            tg.send(cid, text)
        except tg.TelegramError as e:
            ok, err = False, str(e)
            log.warning("telegram send failed: %s", e.detail)
        execute(f"""INSERT INTO {S}.app_telegram_sends (send_id, client_send_id, chat_id, chat_title, audience, language, text, ok, error, by_email, at)
                    VALUES (:id, :c, :chat, :title, :aud, :lang, :text, :ok, :err, :by, current_timestamp())""",
                {"id": str(uuid.uuid4()), "c": b.client_send_id, "chat": cid, "title": chat["title"], "aud": b.audience, "lang": b.language,
                 "text": text, "ok": ok, "err": err, "by": email})
        results.append({"chat_id": cid, "title": chat["title"], "ok": ok, "error": err})
    return {"results": results, "sent": sum(r["ok"] for r in results)}
