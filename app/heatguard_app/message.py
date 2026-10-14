"""'Write a message' dialog: rulebook actions → a ready-to-send message in the coordinator's chosen language."""
import pandas as pd
import streamlit as st

from . import advisor
from .data import nice_date


def _facts(row):
    area = str(row["subzone_name"]).title()
    pa = str(row["planning_area"]).title()
    day = nice_date(row.get("for_date"))
    heat = f"{'forecast' if row.get('heat_is_forecast') else 'observed'} afternoon heat stress {row.get('heat_band') or 'unknown'}"
    if row.get("high_alert"):
        heat += f", with a {row['prob_high'] * 100:.0f}% chance of High heat"
    psi = row.get("psi_twenty_four_hourly")
    haze = f"{row.get('psi_band')} (PSI {int(psi)})" if psi is not None and not pd.isna(psi) else "no reading"
    cool = f"{row.get('nearest_cool_space')} ({row.get('nearest_cool_space_type')}, {row.get('cool_space_km')} km away)"
    return area, pa, day, heat, haze, cool, str(row.get("action") or "")


@st.dialog("Write a message", width="large")
def message_dialog(row):
    area, pa, day, heat, haze, cool, action = _facts(row)
    st.markdown(f"**{area}** · {pa} · {day}")
    st.caption("The message uses only the actions from HeatGuard's rulebook. The AI rewrites the wording and translates; it never adds new advice.")
    c1, c2 = st.columns(2)
    audience = c1.radio("Who is it for?", list(advisor.AUDIENCES), key="msg_audience")
    language = c2.selectbox("Language", advisor.LANGUAGES, key="msg_language")
    if st.button("Write the message", type="primary", icon=":material/edit_note:", width="stretch"):
        try:
            with st.spinner("Writing… (about 5–10 seconds)"):
                text = advisor.write_message(area, pa, day, heat, haze, cool, action, language, audience)
            st.success("Ready. Use the copy button at the top right of the box.", icon=":material/check_circle:")
            st.code(text, language=None, wrap_lines=True)
        except Exception as e:  # noqa: BLE001
            st.warning("The writing assistant isn't available right now, so here is the plain rulebook text instead. "
                       "You can still copy and send it.", icon=":material/info:")
            with st.expander("Technical details"):
                st.code(str(e)[:1500], language=None)
            st.code(advisor.fallback_message(area, day, heat, cool, action), language=None, wrap_lines=True)
