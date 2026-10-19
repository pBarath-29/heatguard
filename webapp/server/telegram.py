"""Send HeatGuard messages to Telegram groups and channels through a Telegram bot.

How it works for a centre:
  1. The HeatGuard team creates a bot with @BotFather and stores its token as the Databricks secret `heatguard/telegram_bot_token`
     (the app reads it as TELEGRAM_BOT_TOKEN).
  2. A coordinator adds the bot to the centre's Telegram group (or as an admin of its channel) and posts any message there.
  3. In HeatGuard → Settings, "Find my groups" lists the groups the bot can see; the coordinator links the right one.
  4. "Send to Telegram" on My plan posts the ready-made message to the linked groups.

Only group and channel IDs are stored. Private chats are ignored, so no individual's Telegram account is ever recorded.
"""
from __future__ import annotations

import os
import time

import requests

API = "https://api.telegram.org"
TIMEOUT_S = 10
MAX_TEXT = 4000                 # Telegram's limit is 4096 characters per message
GROUP_TYPES = {"group", "supergroup", "channel"}


class TelegramError(Exception):
    def __init__(self, message: str, detail: str = ""):
        super().__init__(message)
        self.detail = detail


def token() -> str | None:
    return (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip() or None


def configured() -> bool:
    return token() is not None


def friendly_error(code: int | None, description: str | None) -> str:
    """Plain-English reason a Telegram call failed (never includes the token)."""
    d = (description or "").lower()
    if code == 401 or "unauthorized" in d:
        return "The HeatGuard bot's token isn't valid any more. Ask the HeatGuard team to update it."
    if "bot was kicked" in d or "bot is not a member" in d or "have no rights" in d or "not enough rights" in d:
        return "The bot isn't allowed to post in this group any more. Add it back (as an admin for channels), then try again."
    if "chat not found" in d:
        return "Telegram can't find this group. It may have been deleted, or the bot was removed."
    if "group chat was upgraded" in d:
        return "This group was upgraded by Telegram. Use 'Find my groups' again and link the new one."
    if code == 429 or "too many requests" in d:
        return "Telegram asked us to slow down. Wait a minute and send again."
    if code == 409 or "webhook" in d:
        return "The bot is connected to another service, so HeatGuard can't read its groups."
    return "Telegram didn't accept the message. Please try again."


def _call(method: str, payload: dict | None = None) -> dict | list:
    tok = token()
    if not tok:
        raise TelegramError("Telegram isn't set up yet. Ask the HeatGuard team to add the bot token.")
    last = None
    for attempt in range(2):
        try:
            r = requests.post(f"{API}/bot{tok}/{method}", json=payload or {}, timeout=TIMEOUT_S)
            body = r.json()
        except (requests.RequestException, ValueError) as e:
            last = TelegramError("Couldn't reach Telegram. Check the internet connection and try again.", type(e).__name__)
            time.sleep(1 + attempt)
            continue
        if body.get("ok"):
            return body["result"]
        code, desc = body.get("error_code"), body.get("description")
        raise TelegramError(friendly_error(code, desc), f"{code}: {desc}")
    raise last  # type: ignore[misc]


_me: dict | None = None


def bot_info() -> dict:
    global _me
    if _me is None:
        me = _call("getMe")
        _me = {"username": me.get("username"), "name": me.get("first_name")}
    return _me


def chats_from_updates(updates: list[dict]) -> list[dict]:
    """Groups and channels the bot has seen (newest title wins). Private chats are skipped on purpose."""
    found: dict[str, dict] = {}
    for u in updates:
        for key in ("message", "channel_post", "my_chat_member", "edited_message", "edited_channel_post"):
            chat = (u.get(key) or {}).get("chat")
            if not chat or chat.get("type") not in GROUP_TYPES:
                continue
            status = ((u.get("my_chat_member") or {}).get("new_chat_member") or {}).get("status") if key == "my_chat_member" else None
            cid = str(chat["id"])
            if status in ("left", "kicked"):
                found.pop(cid, None)
                continue
            found[cid] = {"chat_id": cid, "title": chat.get("title") or "Untitled group", "chat_type": chat["type"]}
    return sorted(found.values(), key=lambda c: c["title"].lower())


def discover() -> list[dict]:
    """Groups/channels that recently saw the bot (Telegram keeps updates for 24 hours; nothing is marked as read)."""
    return chats_from_updates(_call("getUpdates", {"allowed_updates": ["message", "channel_post", "my_chat_member"], "timeout": 0}))


def check_text(text: str) -> str:
    t = (text or "").strip()
    if not t:
        raise TelegramError("The message is empty.")
    if len(t) > MAX_TEXT:
        raise TelegramError(f"The message is too long for Telegram (max {MAX_TEXT} characters).")
    return t


def send(chat_id: str, text: str) -> None:
    _call("sendMessage", {"chat_id": chat_id, "text": check_text(text), "disable_web_page_preview": True})
