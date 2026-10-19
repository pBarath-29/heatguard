import datetime as dt

import pytest

from server import messages as m
from server import telegram as tg

TODAY = dt.date(2026, 10, 19)          # Monday
TOMORROW = dt.date(2026, 10, 20)       # Tuesday


def compose(**kw):
    args = dict(level="very_hot", day=TOMORROW, today=TODAY, language="en", audience="seniors", centre="Radin Mas CC", cool="Radin Mas CC")
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
@pytest.mark.parametrize("audience", m.AUDIENCES)
@pytest.mark.parametrize("level", m.LEVELS)
def test_every_combination_fills_in_without_placeholders(lang, audience, level):
    text = compose(language=lang, audience=audience, level=level, haze=True, focus_areas=["Telok Blangah Rise"])
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


def test_staff_briefing_lists_focus_areas_and_steps():
    text = compose(audience="staff", level="hot", focus_areas=["Telok Blangah Rise", "Everton Park"])
    assert "Telok Blangah Rise and Everton Park" in text and "1. Tonight" in text and "NEA" in text


def test_missing_names_have_sensible_defaults():
    assert "the nearest Community Club" in compose(cool=None)
    assert "Hello from your centre!" in compose(centre="  ")


def test_bad_inputs_rejected():
    for bad in (dict(language="fr"), dict(audience="everyone"), dict(level="scorching")):
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
