"""Central heat-risk logic for every HeatGuard feature (activity check, block-route timing, weather view).

Kept free of I/O so it can be unit-tested. Concepts are separated on purpose:
  raw weather data  →  hourly heat estimate  →  heat-risk assessment  →  activity decision  →  alternatives  →  explanation.

Thresholds (documented, configurable):
  * WBGT bands are NEA's heat-stress bands: Low < 31 °C, Moderate 31–32.9 °C, High ≥ 33 °C.
  * NEA's heat-stress advisory: at Moderate, reduce prolonged or strenuous outdoor activity and take more breaks, especially for
    vulnerable people; at High, minimise outdoor activity.
  * HeatGuard's own, more cautious rules for older adults and exertion are labelled as HeatGuard guidance, NOT official classifications.
  * "Warm night": NEA advisories commonly describe nights whose minimum stays above 28 °C as warm nights (no single official cut-off).
"""
from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass, field

SGT = dt.timezone(dt.timedelta(hours=8))

# ---- configuration ----------------------------------------------------------------------------------------------
WBGT_MODERATE = 31.0
WBGT_HIGH = 33.0
WARM_NIGHT_MIN_C = 28.0
OLDER_ADULT_MARGIN_C = 1.0          # HeatGuard guidance: treat older adults as if it were 1 °C hotter
EXERTION_MARGIN_C = {"light": 0.0, "moderate": 0.5, "vigorous": 1.0}
LONG_ACTIVITY_MIN = 60              # activities longer than this get an extra caution note
TYPICAL_ERROR_C = 0.8               # forecast model's typical miss (test period), shown as uncertainty
DAY_START_H, DAY_END_H = 7, 19      # window searched for safer times
WALK_KMH = 4.0                      # gentle walking pace
ROUTE_DETOUR = 1.3                  # streets are longer than straight lines


def today_sgt(now: dt.datetime | None = None) -> dt.date:
    return (now or dt.datetime.now(dt.timezone.utc)).astimezone(SGT).date()


def band(wbgt: float | None) -> str | None:
    if wbgt is None or (isinstance(wbgt, float) and math.isnan(wbgt)):
        return None
    return "High" if wbgt >= WBGT_HIGH else "Moderate" if wbgt >= WBGT_MODERATE else "Low"


# ---- hourly estimate ----------------------------------------------------------------------------------------------
def hourly_estimate(peak_c: float | None, offsets: dict[int, float]) -> dict[int, float]:
    """Estimated WBGT for each hour = forecast afternoon peak + the station's usual offset for that hour.
    Returns {} when the forecast or the usual daily pattern is missing (never invents values)."""
    if peak_c is None or not offsets:
        return {}
    return {h: round(peak_c + off, 1) for h, off in sorted(offsets.items())}


def hours_covered(start: dt.time, minutes: int) -> list[int]:
    """Clock hours touched by an activity, e.g. 15:30 for 60 min → [15, 16]."""
    first = start.hour
    end_min = start.hour * 60 + start.minute + max(1, minutes)
    last = (end_min - 1) // 60
    return list(range(first, min(last, 23) + 1))


# ---- activity assessment -----------------------------------------------------------------------------------------
@dataclass
class Assessment:
    status: str                       # "Lower risk" | "Caution" | "High risk" | "Insufficient data"
    window_max_c: float | None = None
    window_hours: list[int] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    precautions: list[str] = field(default_factory=list)


def assess_window(hourly: dict[int, float], start: dt.time, minutes: int, *, older_adults: bool, exertion: str,
                  prob_high: float | None = None, alert_threshold: float | None = None, rain_expected: bool = False) -> Assessment:
    hours = hours_covered(start, minutes)
    missing = [h for h in hours if h not in hourly]
    if not hourly or missing:
        return Assessment("Insufficient data", window_hours=hours,
                          reasons=["There is no heat estimate for " + (", ".join(f"{h}:00" for h in missing) if missing else "this day") + "."])
    peak = max(hourly[h] for h in hours)
    margin = (OLDER_ADULT_MARGIN_C if older_adults else 0.0) + EXERTION_MARGIN_C.get(exertion, 0.5)
    effective = peak + margin
    reasons = [f"Estimated heat stress during the activity reaches about {peak:.1f} °C WBGT ({band(peak)} on NEA's scale)."]
    if margin:
        who = " and ".join(x for x in (["older participants"] if older_adults else []) + ([f"{exertion} exertion"] if EXERTION_MARGIN_C.get(exertion, 0) else []))
        reasons.append(f"HeatGuard adds a {margin:.1f} °C safety margin for {who} (HeatGuard guidance, not an official rule).")
    status = "High risk" if effective >= WBGT_HIGH else "Caution" if effective >= WBGT_MODERATE else "Lower risk"
    if prob_high is not None and alert_threshold is not None and prob_high >= alert_threshold and any(12 <= h <= 16 for h in hours):
        reasons.append(f"The forecast gives a {prob_high:.0%} chance of High heat stress in the afternoon.")
        if status == "Lower risk":
            status = "Caution"
    if status != "Lower risk" and minutes > LONG_ACTIVITY_MIN:
        reasons.append(f"The activity lasts {minutes} minutes — longer exposure adds to heat strain.")
    if rain_expected:
        reasons.append("NEA expects showers in the region; rain can lower heat but makes plans less certain.")
    precautions = {
        "High risk": ["Move the activity indoors to an air-conditioned venue, or reschedule to a lower-risk time.",
                      "If it must go ahead: shorten it, keep effort light, rest in shade every 15 minutes, and have water ready."],
        "Caution": ["Keep effort light and take shade and water breaks at least every 20 minutes.",
                    "Watch participants for dizziness, heavy sweating or confusion, and stop at the first sign."],
        "Lower risk": ["Normal precautions: water available and shade nearby."],
    }[status]
    return Assessment(status, window_max_c=peak, window_hours=hours, reasons=reasons, precautions=precautions)


def safer_times(hourly: dict[int, float], minutes: int, *, older_adults: bool, exertion: str, current_status: str,
                not_before: dt.time | None = None, limit: int = 2) -> list[dict]:
    """Same-length windows in daytime hours that would be assessed lower than the current status (from the estimate only)."""
    rank = {"Lower risk": 0, "Caution": 1, "High risk": 2, "Insufficient data": 3}
    out = []
    for h in range(DAY_START_H, DAY_END_H):
        for m in (0, 30):
            start = dt.time(h, m)
            if not_before and start < not_before:
                continue
            end_min = h * 60 + m + minutes
            if end_min > DAY_END_H * 60:
                continue
            a = assess_window(hourly, start, minutes, older_adults=older_adults, exertion=exertion)
            if a.status != "Insufficient data" and rank[a.status] < rank[current_status]:
                out.append({"start": start.strftime("%H:%M"), "end": f"{end_min // 60:02d}:{end_min % 60:02d}",
                            "status": a.status, "window_max_c": a.window_max_c})
    out.sort(key=lambda w: (rank[w["status"]], w["window_max_c"], w["start"]))
    picked, used = [], set()
    for w in out:                      # spread suggestions out instead of 07:00 and 07:30
        if all(abs(int(w["start"][:2]) - u) >= 2 for u in used):
            picked.append(w); used.add(int(w["start"][:2]))
        if len(picked) == limit:
            break
    return picked


def warm_night_streak(night_mins: list[tuple[dt.date, float | None]]) -> int | None:
    """Consecutive most-recent nights with a minimum ≥ WARM_NIGHT_MIN_C. None if the latest night has no data."""
    if not night_mins:
        return None
    streak = 0
    for _, m in sorted(night_mins, key=lambda x: x[0], reverse=True):
        if m is None:
            return None if streak == 0 else streak
        if m >= WARM_NIGHT_MIN_C:
            streak += 1
        else:
            break
    return streak


# ---- distances ---------------------------------------------------------------------------------
def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    (la1, lo1), (la2, lo2) = a, b
    p1, p2 = math.radians(la1), math.radians(la2)
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lo2 - lo1) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))

