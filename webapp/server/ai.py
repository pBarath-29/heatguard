"""Genie (Ask HeatGuard) and the message writer (Llama). Both turn failures into friendly messages."""
import datetime as dt

import pandas as pd

from .db import DataError, setting, workspace

GENIE_TIMEOUT = dt.timedelta(minutes=2)

LANGUAGES = ["English", "中文 (Chinese)", "Bahasa Melayu", "தமிழ் (Tamil)"]
AUDIENCES = {
    "seniors": "a short, warm WhatsApp or SMS message to seniors living in the area, in very simple words, "
               "no jargon (do not mention WBGT, PSI or scores)",
    "staff": "a short briefing for Active Ageing Centre staff and volunteers who will phone or visit seniors, "
             "with the reason and the steps as a numbered list",
}
SYSTEM = ("You rewrite heat-safety outreach guidance for Active Ageing Centre staff in Singapore. "
          "Use ONLY the facts and actions provided. Do not add new actions, medical advice, phone numbers, places or numbers that are not given. "
          "Describe the heat and haze levels exactly as given (for example 'moderate heat stress'); do not exaggerate or play them down. "
          "Keep it under 120 words. Write the whole message in {language}. Keep place names in English. Output only the message, without quotation marks.")


def _statement_to_table(sr):
    if sr is None or sr.manifest is None or sr.manifest.schema is None:
        return None
    cols = [c.name for c in (sr.manifest.schema.columns or [])]
    rows = sr.result.data_array if sr.result and sr.result.data_array else []
    df = pd.DataFrame(rows, columns=cols)
    for c in df.columns:
        converted = pd.to_numeric(df[c], errors="coerce")
        if converted.notna().sum() == df[c].notna().sum():
            df[c] = converted
    return {"columns": cols, "rows": df.astype(object).where(df.notna(), None).values.tolist()}


def ask_genie(question, conversation_id=None):
    space_id = setting("GENIE_SPACE_ID")
    w = workspace()
    try:
        if conversation_id:
            msg = w.genie.create_message_and_wait(space_id, conversation_id, question, timeout=GENIE_TIMEOUT)
        else:
            msg = w.genie.start_conversation_and_wait(space_id, question, timeout=GENIE_TIMEOUT)
    except TimeoutError as e:
        raise DataError("Genie took too long to answer. Try a simpler question, or try again in a moment.") from e
    except Exception as e:  # noqa: BLE001
        text = str(e)
        if "RESOURCE_EXHAUSTED" in text or "429" in text:
            raise DataError("Genie is busy right now. Wait a few seconds and try again.", text) from e
        if "PERMISSION" in text or "403" in text:
            raise DataError("The app isn't allowed to use the HeatGuard Genie space. Ask the team to grant it access.", text) from e
        raise DataError("Genie couldn't answer this question. Try rephrasing it, or start a new conversation.", text) from e

    status = str(getattr(msg, "status", "") or "")
    if "FAILED" in status or "CANCELLED" in status:
        raise DataError("Genie couldn't answer this question. Try rephrasing it.")
    message_id = getattr(msg, "message_id", None) or getattr(msg, "id", None)
    out = {"conversation_id": msg.conversation_id, "text": [], "queries": [], "suggestions": []}
    for att in msg.attachments or []:
        if getattr(att, "text", None) and att.text.content:
            out["text"].append(att.text.content)
        if getattr(att, "query", None):
            table = None
            try:
                res = w.genie.get_message_attachment_query_result(space_id, msg.conversation_id, message_id, att.attachment_id)
                table = _statement_to_table(res.statement_response)
            except Exception:  # noqa: BLE001 — still show the text answer
                table = None
            out["queries"].append({"description": att.query.description, "sql": att.query.query, "table": table})
        sq = getattr(att, "suggested_questions", None)
        if sq is not None and getattr(sq, "questions", None):
            out["suggestions"].extend(sq.questions)
    if not out["text"] and not out["queries"]:
        out["text"].append("Genie didn't return an answer. Try asking in a different way, e.g. name the area or the day.")
    return out


def facts(row):
    area = str(row["subzone_name"]).title()
    pa = str(row["planning_area"]).title()
    day = pd.Timestamp(row["for_date"]).strftime("%A %d %B") if row.get("for_date") else "tomorrow"
    heat = f"{'forecast' if row.get('heat_is_forecast') else 'observed'} afternoon heat stress {row.get('heat_band') or 'unknown'}"
    if row.get("high_alert"):
        heat += f", with a {row['prob_high'] * 100:.0f}% chance of High heat"
    psi = row.get("psi_twenty_four_hourly")
    haze = f"{row.get('psi_band')} (PSI {int(psi)})" if psi is not None and not pd.isna(psi) else "no reading"
    cool = f"{row.get('nearest_cool_space')} ({row.get('nearest_cool_space_type')}, {row.get('cool_space_km')} km away)"
    return area, pa, day, heat, haze, cool, str(row.get("action") or "")


def write_message(row, language, audience):
    """Returns (text, used_ai). Falls back to the plain rulebook text if the model is unavailable."""
    from databricks.sdk.service.serving import ChatMessage, ChatMessageRole
    area, pa, day, heat, haze, cool, action = facts(row)
    if language not in LANGUAGES or audience not in AUDIENCES:
        raise DataError("Please choose a language and who the message is for.")
    prompt = (f"Write {AUDIENCES[audience]}.\n\nArea: {area} ({pa}). Day: {day}. Heat: {heat}. Haze: {haze}. "
              f"Nearest air-conditioned place: {cool}.\nActions to include (keep all of them, no others):\n{action}")
    try:
        resp = workspace().serving_endpoints.query(
            name=setting("SERVING_ENDPOINT"),
            messages=[ChatMessage(role=ChatMessageRole.SYSTEM, content=SYSTEM.format(language=language)),
                      ChatMessage(role=ChatMessageRole.USER, content=prompt)],
            max_tokens=400, temperature=0.3)
        return resp.choices[0].message.content.strip().strip('"“”').strip(), True
    except Exception:  # noqa: BLE001 — never leave the coordinator without a message
        return f"{area} — {day}\n{heat[0].upper() + heat[1:]}.\nNearest cool space: {cool}.\n\nWhat to do:\n{action}", False
