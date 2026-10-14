"""Ask HeatGuard: a chat with the HeatGuard Genie space."""
import streamlit as st

from heatguard_app import genie, ui
from heatguard_app.data import ConfigError, setting

SUGGESTED = [
    "Which 10 areas should we check on first tomorrow?",
    "Which areas are on High-heat alert tomorrow?",
    "Show tomorrow's list for Bedok",
    "How many seniors live in areas forecast Moderate or High tomorrow?",
    "Which priority areas are more than 1 km from a cool space?",
    "How many High heat days were there each month this year?",
    "How accurate is the HeatGuard forecast?",
    "What is the haze level in each region right now?",
]


def _render_answer(msg, idx):
    for t in msg.get("text", []):
        st.markdown(t)
    for qi, q in enumerate(msg.get("queries", [])):
        if q.get("description"):
            st.caption(q["description"])
        df = q.get("df")
        if df is not None and len(df):
            st.dataframe(df, hide_index=True, width="stretch")
            st.download_button("Download this table", df.to_csv(index=False).encode("utf-8"), file_name="heatguard_answer.csv",
                               mime="text/csv", key=f"dl_{idx}_{qi}", icon=":material/download:")
        elif df is not None:
            st.info("The answer has no rows — nothing matched the question.", icon=":material/search_off:")
        if q.get("sql"):
            with st.expander("See how Genie worked it out (SQL)"):
                st.code(q["sql"], language="sql")
    if msg.get("error"):
        st.warning(msg["error"], icon=":material/info:")


def _ask(question):
    st.session_state.genie_messages.append({"role": "user", "text": [question]})
    try:
        with st.spinner("Genie is looking at the HeatGuard data… (usually 10–30 seconds)"):
            ans = genie.ask(question, st.session_state.get("genie_conversation"))
        st.session_state.genie_conversation = ans["conversation_id"]
        st.session_state.genie_messages.append({"role": "assistant", **ans})
    except (genie.GenieError, ConfigError) as e:
        st.session_state.genie_messages.append({"role": "assistant", "error": str(e)})
    except Exception as e:  # noqa: BLE001
        st.session_state.genie_messages.append({"role": "assistant", "error": f"Something went wrong talking to Genie. Try again in a moment. ({type(e).__name__})"})


def render():
    ui.hero("Ask HeatGuard", "Ask questions in plain English about tomorrow's list, heat, haze, cool spaces and forecast accuracy.")
    try:
        setting("GENIE_SPACE_ID")
    except ConfigError as e:
        st.error(str(e), icon=":material/error:")
        return
    st.session_state.setdefault("genie_messages", [])
    st.session_state.setdefault("genie_conversation", None)

    top = st.columns([5, 1.2])
    top[0].caption("Answers come from Databricks Genie, which turns your question into a query on HeatGuard's tables. "
                   "It can make mistakes — check important answers against the check-in list.")
    if top[1].button("New conversation", icon=":material/restart_alt:", width="stretch"):
        st.session_state.genie_messages, st.session_state.genie_conversation = [], None
        st.rerun()

    pending = None
    if not st.session_state.genie_messages:
        st.markdown("**Try one of these:**")
        cols = st.columns(2)
        for i, q in enumerate(SUGGESTED):
            if cols[i % 2].button(q, key=f"sugg_{i}", width="stretch", icon=":material/chat_bubble:"):
                pending = q

    for i, m in enumerate(st.session_state.genie_messages):
        with st.chat_message(m["role"], avatar=":material/person:" if m["role"] == "user" else ":material/thermostat:"):
            if m["role"] == "user":
                st.markdown(m["text"][0])
            else:
                _render_answer(m, i)

    last = st.session_state.genie_messages[-1] if st.session_state.genie_messages else None
    if last and last["role"] == "assistant" and last.get("suggestions"):
        st.markdown("**Follow-up ideas:**")
        for i, s in enumerate(last["suggestions"][:3]):
            if st.button(s, key=f"follow_{len(st.session_state.genie_messages)}_{i}", icon=":material/subdirectory_arrow_right:"):
                pending = s

    typed = st.chat_input("Ask a question, e.g. Which areas in Toa Payoh are on High-heat alert tomorrow?")
    question = typed or pending
    if question:
        if len(question) > 500:
            st.warning("That question is very long. Please keep it under 500 characters.", icon=":material/info:")
        else:
            _ask(question.strip())
            st.rerun()
