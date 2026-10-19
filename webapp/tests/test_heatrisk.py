import datetime as dt

import pytest

from server import heatrisk as hr

# A plausible day: cool morning, peak 32.5 °C at 14:00
OFFSETS = {7: -5.0, 8: -4.0, 9: -3.0, 10: -2.0, 11: -1.2, 12: -0.6, 13: -0.2, 14: 0.0, 15: -0.3, 16: -0.9, 17: -1.8, 18: -3.0}


def day(peak=32.5):
    return hr.hourly_estimate(peak, OFFSETS)


def test_hourly_estimate_never_invents():
    assert hr.hourly_estimate(None, OFFSETS) == {}
    assert hr.hourly_estimate(32.0, {}) == {}
    assert day()[14] == 32.5 and day()[8] == 28.5


@pytest.mark.parametrize("start,minutes,hours", [
    (dt.time(15, 0), 60, [15]), (dt.time(15, 30), 60, [15, 16]), (dt.time(14, 0), 120, [14, 15]), (dt.time(9, 59), 2, [9, 10]),
])
def test_hours_covered(start, minutes, hours):
    assert hr.hours_covered(start, minutes) == hours


def test_lower_risk_morning_light_activity():
    a = hr.assess_window(day(), dt.time(8, 0), 60, older_adults=False, exertion="light")
    assert a.status == "Lower risk" and a.window_max_c == 28.5


def test_caution_moderate_band():
    a = hr.assess_window(day(31.5), dt.time(14, 0), 60, older_adults=False, exertion="light")
    assert a.status == "Caution"


def test_high_risk_afternoon_peak():
    a = hr.assess_window(day(33.4), dt.time(14, 0), 60, older_adults=False, exertion="light")
    assert a.status == "High risk"


def test_older_adults_and_exertion_raise_the_level():
    base = hr.assess_window(day(32.0), dt.time(15, 0), 60, older_adults=False, exertion="light")
    cautious = hr.assess_window(day(32.0), dt.time(15, 0), 60, older_adults=True, exertion="moderate")
    assert base.status == "Caution" and cautious.status == "High risk"
    assert any("not an official rule" in r for r in cautious.reasons)


def test_activity_spanning_periods_uses_worst_hour():
    # 12:30–14:30 covers 12, 13, 14 → worst is the 14:00 peak
    a = hr.assess_window(day(32.5), dt.time(12, 30), 120, older_adults=False, exertion="light")
    assert a.window_hours == [12, 13, 14] and a.window_max_c == 32.5


def test_missing_hours_are_insufficient_not_safe():
    a = hr.assess_window({8: 28.0}, dt.time(8, 30), 60, older_adults=False, exertion="light")
    assert a.status == "Insufficient data"
    assert hr.assess_window({}, dt.time(8, 0), 30, older_adults=False, exertion="light").status == "Insufficient data"


def test_probability_of_high_raises_lower_risk_to_caution_in_afternoon():
    a = hr.assess_window(day(30.0), dt.time(14, 0), 60, older_adults=False, exertion="light", prob_high=0.3, alert_threshold=0.15)
    assert a.status == "Caution"


def test_safer_times_are_better_and_spread_out():
    h = day(33.5)
    current = hr.assess_window(h, dt.time(14, 0), 60, older_adults=True, exertion="moderate").status
    alts = hr.safer_times(h, 60, older_adults=True, exertion="moderate", current_status=current)
    assert alts and all(a["status"] in ("Lower risk", "Caution") for a in alts)
    assert len({a["start"][:2] for a in alts}) == len(alts)


def test_safer_times_empty_when_whole_day_is_hot():
    hot = {h: 34.0 for h in range(7, 19)}
    assert hr.safer_times(hot, 60, older_adults=False, exertion="light", current_status="High risk") == []


def test_warm_night_streak():
    d = dt.date(2026, 10, 18)
    nights = [(d - dt.timedelta(days=i), m) for i, m in enumerate([28.4, 28.1, 27.2, 28.9])]
    assert hr.warm_night_streak(nights) == 2
    assert hr.warm_night_streak([(d, None)]) is None
    assert hr.warm_night_streak([]) is None


def test_route_order_and_duration():
    start = (1.3340, 103.9380)
    stops = [{"id": "far", "latitude": 1.3400, "longitude": 103.9450}, {"id": "near", "latitude": 1.3345, "longitude": 103.9385}]
    plan = hr.route_plan(start, stops, visit_min=15)
    assert [s["id"] for s in plan["stops"]] == ["near", "far"]
    assert plan["visit_min"] == 30 and plan["total_min"] == plan["walk_min"] + 30


def test_best_departure_avoids_heat_and_flags_too_hot():
    ok = hr.best_departure(day(32.5), total_min=120)
    assert ok["status"] == "ok" and ok["depart"] == "08:00"
    hot = hr.best_departure({h: 33.0 for h in range(7, 20)}, total_min=60)
    assert hot["status"] == "too_hot"
    assert hr.best_departure({}, 60)["status"] == "insufficient"


def test_today_in_singapore_across_midnight():
    # 16:30 UTC on 18 Oct is 00:30 on 19 Oct in Singapore
    assert hr.today_sgt(dt.datetime(2026, 10, 18, 16, 30, tzinfo=dt.timezone.utc)) == dt.date(2026, 10, 19)
    assert hr.today_sgt(dt.datetime(2026, 10, 18, 15, 59, tzinfo=dt.timezone.utc)) == dt.date(2026, 10, 18)
