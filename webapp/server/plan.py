"""The coordinator's to-do list for one centre and day (pure functions, unit-tested).

Steps are in the order a coordinator actually does them: tell people the evening before, reach the most vulnerable before the
hottest hours, adjust outdoor activities, keep the centre open as a cool place, and follow up late afternoon on anyone not reached.
Each step says why it matters and links to the page where it is done. Wording follows the HeatGuard rulebook (NEA heat-stress
bands: hottest 11 am – 4 pm on very hot days, 12 – 4 pm on hot days).
"""
from __future__ import annotations

import datetime as dt
import urllib.parse

EMERGENCY = "If a senior is confused, faints or collapses in the heat, call 995 and move them somewhere cool."


def _item(id_, when, text, why=None, action=None):
    return {"id": id_, "when": when, "text": text, "why": why,
            "action": {"label": action[0], "to": action[1]} if action else None}


def todo(level: str, *, haze: bool, focus_areas: list[str], for_date: dt.date | None, today: dt.date) -> dict:
    """{'todo': [...], 'safety': str | None}. Labels say 'Tonight / Tomorrow …' when the plan is for tomorrow, and 'Now / This morning …'
    when it is for today (e.g. opened after midnight)."""
    ahead = for_date is None or for_date > today
    w = lambda tomorrow, today_: tomorrow if ahead else today_                       # noqa: E731
    names = [f for f in focus_areas if f][:2]
    focus = " and ".join(names) if names else "the areas nearest your centre"
    areas = ("Choose an area", "#areas")
    welfare = ("Open welfare checks", "/welfare")
    first_area = (f"Open {names[0]}", "/area/" + urllib.parse.quote(names[0].upper())) if names else welfare   # its seniors are listed there

    if level == "very_hot":
        items = [
            _item("send", w("Tonight", "Now"), "Send the heat reminder to seniors in each area below.",
                  "Each area's message names the cool place nearest to them. Sending it the evening before gives everyone time to plan.", areas),
            _item("call", w("Tomorrow, before 11 am", "Before 11 am"),
                  f"Call or visit seniors on your list who live alone or have heart or lung conditions. Start with {focus}.",
                  "Reach them before the hottest hours, while there is still time to help.", first_area),
            _item("activities", w("Tomorrow, before 11 am", "Before 11 am"),
                  "Move any outdoor activity planned for 11 am – 4 pm indoors, or to the early morning.",
                  "Heat stress is highest from 11 am to 4 pm.", ("Check an activity", "/activity")),
            _item("centre", w("Tomorrow, 11 am – 4 pm", "11 am – 4 pm"),
                  "Keep the centre cool and open for seniors who walk in, with drinking water ready.",
                  "Some seniors' flats get too hot to stay in during the afternoon."),
            _item("follow_up", w("Tomorrow, 4 – 5 pm", "4 – 5 pm"),
                  "Call back anyone you couldn't reach in the morning, and anyone who sounded unwell.",
                  "Someone who didn't answer may need help.", ("See who needs follow-up", "/welfare?filter=follow_up")),
        ]
    elif level == "hot":
        items = [
            _item("send", w("Tonight", "Now"), "Send the heat reminder to seniors in each area below.",
                  "Each area's message names the cool place nearest to them.", areas),
            _item("call", w("Tomorrow morning", "This morning"),
                  f"Phone seniors on your list who live alone. Start with {focus}.",
                  "Remind them to stay in from 12 to 4 pm and to keep drinking water.", first_area),
            _item("activities", w("Tomorrow morning", "This morning"),
                  "Check any outdoor activity planned for 12 – 4 pm.",
                  "It may need shade, water breaks, a shorter session or a cooler time.", ("Check an activity", "/activity")),
            _item("follow_up", w("Tomorrow, 4 – 5 pm", "4 – 5 pm"),
                  "Call back anyone you couldn't reach in the morning.", None, ("See who needs follow-up", "/welfare?filter=follow_up")),
        ]
    else:
        items = [_item("routine", w("Tomorrow", "Today"), "Routine check-ins. No extra heat steps needed.",
                       "Activities can run as planned; keep drinking water available.", welfare)]

    if haze:
        items.insert(2 if level != "normal" else 1, _item(
            "haze", w("Tomorrow morning", "This morning"),
            "Check that seniors with heart or lung conditions have their medicine, and ask them to keep windows closed.",
            "The haze is at an unhealthy level.", welfare))
    return {"todo": items, "safety": EMERGENCY if level != "normal" else None}
