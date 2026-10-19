"""Live NEA readings and forecasts from data.gov.sg, validated and cached for 5 minutes.

Everything returned is labelled as an *observation* (measured) or a *forecast* (NEA's prediction). Nothing is invented: if a source
fails or returns something unexpected, that part comes back as None with a plain-English note, and the rest still works.
"""
from __future__ import annotations

import datetime as dt
import os
import threading
import time

import requests

from .heatrisk import SGT, band, haversine_km

BASE = "https://api-open.data.gov.sg/v2/real-time/api"
TIMEOUT_S = 10
CACHE_S = 300
_cache: dict[str, tuple[float, dict]] = {}
_lock = threading.Lock()


class WeatherError(RuntimeError):
    pass


def _get(path: str, params: dict | None = None) -> dict:
    """GET with a timeout, two retries for transient problems (timeouts, 429, 5xx), and validation of the data.gov.sg envelope."""
    key = f"{path}?{sorted((params or {}).items())}"
    with _lock:
        hit = _cache.get(key)
        if hit and time.time() - hit[0] < CACHE_S:
            return hit[1]
    headers = {"x-api-key": os.environ["DATAGOV_API_KEY"]} if os.environ.get("DATAGOV_API_KEY") else {}
    last = "no response"
    for attempt in range(3):
        try:
            r = requests.get(f"{BASE}/{path}", params=params, headers=headers, timeout=TIMEOUT_S)
        except requests.RequestException as e:
            last = type(e).__name__
            time.sleep(1.5 * (attempt + 1)); continue
        if r.status_code == 429 or r.status_code >= 500:
            last = f"HTTP {r.status_code}"
            time.sleep(2 * (attempt + 1)); continue
        try:
            body = r.json()
        except ValueError:
            raise WeatherError("NEA sent an unreadable reply.")
        if body.get("code") == 17:
            data = {}
        elif body.get("code") != 0 or not isinstance(body.get("data"), dict):
            raise WeatherError(f"NEA data is not available right now ({body.get('errorMsg') or 'unexpected reply'}).")
        else:
            data = body["data"]
        with _lock:
            _cache[key] = (time.time(), data)
        return data
    raise WeatherError(f"Couldn't reach NEA's data service ({last}). Try again in a minute.")


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _nearest(lat, lon, items):
    """items: [(lat, lon, payload)] → (payload, distance_km) of the closest; None if empty."""
    best = min(((haversine_km((lat, lon), (a, b)), p) for a, b, p in items if a is not None and b is not None), default=None, key=lambda x: x[0])
    return (best[1], round(best[0], 1)) if best else None


def _safe(fn, *args):
    try:
        return fn(*args), None
    except WeatherError as e:
        return None, str(e)
    except (KeyError, TypeError, ValueError, IndexError):
        return None, "NEA's reply was incomplete."


def wbgt_now(lat, lon):
    d = _get("weather", {"api": "wbgt"})
    rec = (d.get("records") or [None])[0]
    if not rec:
        return None
    items = [(_f(r["location"]["latitude"]), _f(r["location"]["longitude"]), r) for r in rec["item"]["readings"] if _f(r.get("wbgt")) is not None]
    hit = _nearest(lat, lon, items)
    if not hit:
        return None
    r, km = hit
    v = _f(r["wbgt"])
    return {"kind": "observation", "value_c": v, "band": band(v), "station": r["station"]["name"], "distance_km": km, "time": rec["datetime"]}


def station_reading(lat, lon, path):
    d = _get(path)
    stations = {s["id"]: s for s in d.get("stations") or []}
    reading = (d.get("readings") or [None])[0]
    if not reading:
        return None
    items = [(_f(stations[x["stationId"]]["location"]["latitude"]), _f(stations[x["stationId"]]["location"]["longitude"]), x)
             for x in reading["data"] if x.get("stationId") in stations and _f(x.get("value")) is not None]
    hit = _nearest(lat, lon, items)
    if not hit:
        return None
    x, km = hit
    return {"kind": "observation", "value": _f(x["value"]), "station": stations[x["stationId"]]["name"], "distance_km": km, "time": reading["timestamp"]}


def two_hour(lat, lon):
    d = _get("two-hr-forecast")
    item = (d.get("items") or [None])[0]
    if not item:
        return None
    areas = {a["name"]: a["label_location"] for a in d.get("area_metadata") or []}
    items = [(_f(areas[f["area"]]["latitude"]), _f(areas[f["area"]]["longitude"]), f) for f in item["forecasts"] if f.get("area") in areas]
    hit = _nearest(lat, lon, items)
    if not hit:
        return None
    f, km = hit
    vp = item.get("valid_period") or {}
    return {"kind": "forecast", "area": f["area"], "forecast": f["forecast"], "distance_km": km, "valid_text": vp.get("text"),
            "valid_start": vp.get("start"), "valid_end": vp.get("end"), "issued": item.get("update_timestamp") or item.get("timestamp")}


REGION_FALLBACK = {"west": (1.35735, 103.7), "east": (1.35735, 103.94), "central": (1.35735, 103.82),
                   "south": (1.29587, 103.82), "north": (1.41803, 103.82)}   # NEA region label points (from the PSI API)


def region_of(lat, lon):
    try:
        meta = _get("psi").get("regionMetadata") or []
        pts = {m["name"]: (_f(m["labelLocation"]["latitude"]), _f(m["labelLocation"]["longitude"])) for m in meta}
    except Exception:  # noqa: BLE001 — fall back to the published label points
        pts = {}
    pts = {k: v for k, v in pts.items() if k in REGION_FALLBACK and None not in v} or REGION_FALLBACK
    return min(pts, key=lambda k: haversine_km((lat, lon), pts[k]))


def periods_24h(lat, lon):
    d = _get("twenty-four-hr-forecast")
    rec = (d.get("records") or [None])[0]
    if not rec:
        return None
    region = region_of(lat, lon)
    gen = rec.get("general") or {}
    periods = []
    for p in rec.get("periods") or []:
        tp = p.get("timePeriod") or {}
        txt = ((p.get("regions") or {}).get(region) or {}).get("text")
        if tp.get("start") and txt:
            periods.append({"start": tp["start"], "end": tp.get("end"), "label": tp.get("text"), "forecast": txt})
    return {"kind": "forecast", "region": region, "issued": rec.get("updatedTimestamp") or rec.get("timestamp"),
            "temp_low_c": (gen.get("temperature") or {}).get("low"), "temp_high_c": (gen.get("temperature") or {}).get("high"),
            "humidity_low": (gen.get("relativeHumidity") or {}).get("low"), "humidity_high": (gen.get("relativeHumidity") or {}).get("high"),
            "overall": (gen.get("forecast") or {}).get("text"), "valid_text": (gen.get("validPeriod") or {}).get("text"), "periods": periods}


def wbgt_today_by_hour(lat, lon, day: dt.date):
    """Observed WBGT today at the nearest station: the highest reading in each clock hour so far (follows pagination)."""
    readings, token, pages = [], None, 0
    while pages < 8:
        d = _get("weather", {"api": "wbgt", "date": day.isoformat(), **({"paginationToken": token} if token else {})})
        readings += d.get("records") or []
        token, pages = d.get("paginationToken"), pages + 1
        if not token:
            break
    if not readings:
        return None
    first = readings[0]["item"]["readings"]
    hit = _nearest(lat, lon, [(_f(r["location"]["latitude"]), _f(r["location"]["longitude"]), r["station"]) for r in first])
    if not hit:
        return None
    station, km = hit
    by_hour: dict[int, float] = {}
    for rec in readings:
        hour = int(rec["datetime"][11:13])
        for r in rec["item"]["readings"]:
            v = _f(r.get("wbgt"))
            if r["station"]["id"] == station["id"] and v is not None:
                by_hour[hour] = max(v, by_hour.get(hour, v))
    return {"kind": "observation", "station": station["name"], "station_id": station["id"], "distance_km": km,
            "by_hour": {h: by_hour[h] for h in sorted(by_hour)}}


def current(lat, lon):
    """Everything 'now' for a location. Each part may be None with a note; never raises for partial failures."""
    out, notes = {}, []
    for key, fn, args in [("wbgt", wbgt_now, (lat, lon)), ("air_temp", station_reading, (lat, lon, "air-temperature")),
                          ("humidity", station_reading, (lat, lon, "relative-humidity")), ("two_hour", two_hour, (lat, lon)),
                          ("periods", periods_24h, (lat, lon))]:
        val, err = _safe(fn, *args)
        out[key] = val
        if err:
            notes.append(f"{key.replace('_', ' ').title()}: {err}")
    out["notes"] = notes
    out["fetched_at"] = dt.datetime.now(SGT).isoformat()
    return out
