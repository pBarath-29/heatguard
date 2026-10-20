"""Genie (Ask HeatGuard): turns the Conversation API's answers and failures into plain, friendly results."""
import datetime as dt
import os
import re
from functools import lru_cache

import pandas as pd

from .db import DataError, config, setting, workspace

GENIE_TIMEOUT = dt.timedelta(minutes=2)



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




@lru_cache(maxsize=1)
def _workspace_id() -> str:
    wid = os.environ.get("DATABRICKS_WORKSPACE_ID", "").strip()
    if wid:
        return wid
    try:
        return str(workspace().get_workspace_id())
    except Exception as e:  # noqa: BLE001
        raise DataError("Couldn't work out the Databricks workspace for Genie. Use Simple answers for now.", str(e)) from e


def embed_links() -> dict:
    space_id = setting("GENIE_SPACE_ID")
    if not re.fullmatch(r"[0-9a-f]{32}", space_id):
        raise DataError("The Genie space id in the app settings looks wrong. Ask the HeatGuard team to check it.")
    host = (config().host or "").rstrip("/")
    if not host.startswith("https://"):
        raise DataError("The app doesn't know its Databricks address, so Genie can't be shown here. Use Simple answers for now.")
    org = _workspace_id()
    return {"embed_url": f"{host}/embed/genie/rooms/{space_id}?o={org}", "open_url": f"{host}/genie/rooms/{space_id}?o={org}"}
