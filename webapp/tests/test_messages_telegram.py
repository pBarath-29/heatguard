import datetime as dt

import pytest

from server import messages as m
from server import telegram as tg

TODAY = dt.date(2026, 10, 19)          # Monday
TOMORROW = dt.date(2026, 10, 20)       # Tuesday


def compose(**kw):
    args = dict(level="very_hot", day=TOMORROW, today=TODAY, language="en", centre="Radin Mas CC", cool="Radin Mas CC")
    return m.compose(**{**args, **kw})


# ---------------- dates ----------------
@pytest.mark.parametrize("lang, expected", [
    ("en", "Tomorrow, Tuesday 20 October"),
    ("zh", "明天（10月20日，星期二）"),
    ("ms", "Esok (Selasa, 20 Oktober)"),
    ("ta", "நாளை (அக்டோபர் 20, செவ்வாய்க்கிழமை)"),
])
def test_day_is_written_in_the_chosen_language(lang, expected):
    assert m.when_text(TOMORROW, TODAY, lang) == expected


def test_today_and_other_days():
    assert m.when_text(TODAY, TODAY, "ms").startswith("Hari ini")
    assert m.when_text(dt.date(2026, 10, 25), TODAY, "en") == "Sunday 25 October"


# ---------------- messages ----------------
@pytest.mark.parametrize("lang", list(m.LANGUAGES))
@pytest.mark.parametrize("level", m.LEVELS)
def test_every_combination_fills_in_without_placeholders(lang, level):
    text = compose(language=lang, level=level, haze=True)
    assert "{" not in text and "}" not in text
    assert "Radin Mas CC" in text


def test_senior_message_never_contains_staff_instructions():
    for level in m.LEVELS:
        text = compose(level=level).lower()
        assert "before 11 am" not in text and "call or visit" not in text and "live alone" not in text


def test_hot_and_very_hot_have_different_advice():
    assert "11 am to 4 pm" in compose(level="very_hot")
    assert "12 pm to 4 pm" in compose(level="hot")
    assert "•" not in compose(level="normal")


def test_haze_advice_only_when_hazy():
    assert "haze" in compose(haze=True).lower()
    assert "haze" not in compose(haze=False).lower()


def test_missing_names_have_sensible_defaults():
    assert "the nearest Community Club" in compose(cool=None)
    assert "Hello from your centre!" in compose(centre="  ")


def test_bad_inputs_rejected():
    for bad in (dict(language="fr"), dict(level="scorching")):
        with pytest.raises(m.MessageError):
            compose(**bad)


# ---------------- Telegram ----------------
def test_only_groups_and_channels_are_found():
    updates = [
        {"message": {"chat": {"id": 111, "type": "private", "first_name": "Someone"}}},
        {"message": {"chat": {"id": -100123, "type": "supergroup", "title": "Radin Mas seniors"}}},
        {"channel_post": {"chat": {"id": -100456, "type": "channel", "title": "Heat alerts"}}},
        {"message": {"chat": {"id": -100123, "type": "supergroup", "title": "Radin Mas seniors (new name)"}}},
    ]
    chats = tg.chats_from_updates(updates)
    assert [c["chat_id"] for c in chats] == ["-100456", "-100123"]
    assert chats[1]["title"] == "Radin Mas seniors (new name)"


def test_group_that_removed_the_bot_is_dropped():
    updates = [
        {"message": {"chat": {"id": -5, "type": "group", "title": "Volunteers"}}},
        {"my_chat_member": {"chat": {"id": -5, "type": "group", "title": "Volunteers"}, "new_chat_member": {"status": "kicked"}}},
    ]
    assert tg.chats_from_updates(updates) == []


def test_friendly_errors_never_leak_details():
    assert "token" in tg.friendly_error(401, "Unauthorized")
    assert "Add it back" in tg.friendly_error(403, "Forbidden: bot was kicked from the supergroup chat")
    assert "slow down" in tg.friendly_error(429, "Too Many Requests: retry after 5")


def test_text_checks():
    assert tg.check_text("  hi  ") == "hi"
    with pytest.raises(tg.TelegramError):
        tg.check_text("   ")
    with pytest.raises(tg.TelegramError):
        tg.check_text("x" * (tg.MAX_TEXT + 1))


def test_not_configured_without_token(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    assert tg.configured() is False
    with pytest.raises(tg.TelegramError):
        tg.send("-1", "hello")


# ---------------- coordinator to-do ----------------
from server import plan as pl  # noqa: E402


def ids(level, **kw):
    out = pl.todo(level, haze=kw.get("haze", False), focus_areas=["Telok Blangah Rise"], for_date=TOMORROW, today=kw.get("today", TODAY))
    return [t["id"] for t in out["todo"]], out


def test_very_hot_steps_are_in_time_order_and_reach_people_before_the_heat():
    order, out = ids("very_hot")
    assert order == ["send", "call", "activities", "centre", "follow_up"]
    whens = [t["when"] for t in out["todo"]]
    assert whens[0] == "Tonight" and "before 11 am" in whens[1] and "4 – 5 pm" in whens[-1]
    assert "Telok Blangah Rise" in out["todo"][1]["text"] and out["safety"] and "995" in out["safety"]


def test_no_reminder_is_scheduled_during_the_hottest_hours():
    for level in ("very_hot", "hot"):
        _, out = ids(level)
        for t in out["todo"]:
            if t["id"] in ("send", "call"):
                assert not any(h in t["when"] for h in ("12 pm", "11 am – 4 pm", "12 – 4"))


def test_hot_and_normal_days():
    assert ids("hot")[0] == ["send", "call", "activities", "follow_up"]
    order, out = ids("normal")
    assert order == ["routine"] and out["safety"] is None


def test_haze_adds_a_medicine_check_after_calls():
    assert ids("hot", haze=True)[0] == ["send", "call", "haze", "activities", "follow_up"]


def test_labels_change_when_the_plan_is_for_today():
    _, out = ids("very_hot", today=TOMORROW)
    assert out["todo"][0]["when"] == "Now" and out["todo"][1]["when"] == "Before 11 am"


def test_every_step_with_a_link_points_to_a_real_page():
    for level in ("very_hot", "hot", "normal"):
        for t in ids(level, haze=True)[1]["todo"]:
            if t["action"]:
                assert t["action"]["to"].split("?")[0] in ("#areas", "/welfare", "/activity")
