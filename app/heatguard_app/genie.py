"""Ask HeatGuard: a thin wrapper around the Genie Conversation API with friendly errors."""
import datetime as dt

import pandas as pd

from .data import setting, workspace

TIMEOUT = dt.timedelta(minutes=2)


class GenieError(RuntimeError):
    pass


def _statement_to_df(sr):
    if sr is None or sr.manifest is None or sr.manifest.schema is None:
        return None
    cols = [c.name for c in (sr.manifest.schema.columns or [])]
    rows = (sr.result.data_array if sr.result and sr.result.data_array else [])
    df = pd.DataFrame(rows, columns=cols)
    for c in df.columns:
        converted = pd.to_numeric(df[c], errors="coerce")
        if converted.notna().sum() == df[c].notna().sum():   # every non-empty value is a number
            df[c] = converted
    return df


def ask(question, conversation_id=None):
    """Send a question (new or follow-up) and return {conversation_id, text, queries, suggestions}."""
    space_id = setting("GENIE_SPACE_ID")
    w = workspace()
    try:
        if conversation_id:
            msg = w.genie.create_message_and_wait(space_id, conversation_id, question, timeout=TIMEOUT)
        else:
            msg = w.genie.start_conversation_and_wait(space_id, question, timeout=TIMEOUT)
    except TimeoutError as e:
        raise GenieError("Genie took too long to answer. Try a simpler question, or try again in a moment.") from e
    except Exception as e:  # noqa: BLE001
        text = str(e)
        if "RESOURCE_EXHAUSTED" in text or "429" in text:
            raise GenieError("Genie is busy right now (too many questions in a short time). Wait a few seconds and try again.") from e
        if "PERMISSION" in text or "403" in text:
            raise GenieError("The app isn't allowed to use the HeatGuard Genie space. Ask the team to grant it access.") from e
        raise GenieError("Genie couldn't answer this question. Try rephrasing it, or start a new conversation.") from e

    status = str(getattr(msg, "status", "") or "")
    message_id = getattr(msg, "message_id", None) or getattr(msg, "id", None)
    out = {"conversation_id": msg.conversation_id, "text": [], "queries": [], "suggestions": []}
    if "FAILED" in status or "CANCELLED" in status:
        err = getattr(getattr(msg, "error", None), "error", None) or ""
        raise GenieError("Genie couldn't answer this question" + (f" ({err})" if err else "") + ". Try rephrasing it.")

    for att in msg.attachments or []:
        if getattr(att, "text", None) and att.text.content:
            out["text"].append(att.text.content)
        if getattr(att, "query", None):
            df = None
            try:
                res = w.genie.get_message_attachment_query_result(space_id, msg.conversation_id, message_id, att.attachment_id)
                df = _statement_to_df(res.statement_response)
            except Exception:  # noqa: BLE001 — show the answer text even if the table can't be fetched
                df = None
            out["queries"].append({"title": getattr(att.query, "title", None), "description": att.query.description,
                                   "sql": att.query.query, "df": df})
        sq = getattr(att, "suggested_questions", None)
        if sq is not None and getattr(sq, "questions", None):
            out["suggestions"].extend(sq.questions)
    if not out["text"] and not out["queries"]:
        out["text"].append("Genie didn't return an answer. Try asking in a different way, e.g. name the area or the day.")
    return out
