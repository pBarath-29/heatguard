"""HeatGuard — heat-risk check-ins for Active Ageing Centres (Databricks App)."""
import streamlit as st

st.set_page_config(page_title="HeatGuard", page_icon="🌡️", layout="wide", initial_sidebar_state="expanded")

from heatguard_app import data, nav, ui  # noqa: E402
from views import about, accuracy, ask, checkin, now, why  # noqa: E402

ui.inject_css()

nav.PAGES.update({
    "checkin": st.Page(checkin.render, title="Check-in list", icon=":material/checklist:", url_path="checkin", default=True),
    "now": st.Page(now.render, title="Heat & haze now", icon=":material/thermostat:", url_path="now"),
    "why": st.Page(why.render, title="Why here?", icon=":material/travel_explore:", url_path="why-here"),
    "ask": st.Page(ask.render, title="Ask HeatGuard", icon=":material/forum:", url_path="ask"),
    "accuracy": st.Page(accuracy.render, title="Forecast accuracy", icon=":material/insights:", url_path="accuracy"),
    "about": st.Page(about.render, title="About & help", icon=":material/help:", url_path="about"),
})
page = st.navigation({
    "Plan": [nav.PAGES["checkin"], nav.PAGES["why"], nav.PAGES["now"]],
    "Explore": [nav.PAGES["ask"], nav.PAGES["accuracy"], nav.PAGES["about"]],
})

with st.sidebar:
    st.markdown("### 🌡️ HeatGuard")
    st.caption("Heat-risk check-ins for Active Ageing Centres in Singapore.")
    if st.button("Refresh data", icon=":material/refresh:", width="stretch",
                 help="Fetch the newest data (results are otherwise kept for 5 minutes)."):
        data.refresh_all()
        st.rerun()
    st.caption("Area-level open data only — no personal data.")

page.run()
