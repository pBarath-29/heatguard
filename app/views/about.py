"""About & help: how HeatGuard works, what the numbers mean, data sources, limitations and glossary."""
import pandas as pd
import streamlit as st

from heatguard_app import data, ui


def render():
    ui.hero("About HeatGuard", "How the check-in list is made, what the numbers mean, and the data behind it.")

    st.subheader("How it works")
    steps = [
        ("Collect", "NEA heat-stress (WBGT) readings from ~30 stations every 15 minutes, NEA forecasts, and haze (PSI) for 5 regions, plus Census 2020, the URA subzone map, Community Clubs and libraries."),
        ("Clean", "A Databricks pipeline removes faulty readings (e.g. sensor errors), duplicates and gaps, and counts every row it drops."),
        ("Forecast", "A machine-learning model, tested on months it never saw, forecasts tomorrow afternoon's peak heat at each station and the chance it reaches High."),
        ("Rank", "Each area with seniors gets a risk score from heat, haze, how many vulnerable seniors live there, and distance to a cool space. Actions come from a fixed rulebook."),
    ]
    cols = st.columns(4)
    for i, (col, (title, body)) in enumerate(zip(cols, steps), start=1):
        col.markdown(f'<div class="hg-step"><span class="num">{i}</span><b>{title}</b><br/><span class="hg-note">{body}</span></div>',
                     unsafe_allow_html=True)
    st.caption("Updated every evening at about 7 pm (Singapore time), so the list is ready before coordinators plan the next day.")

    st.subheader("What the risk score means")
    w = data.score_weights()
    if w is not None and len(w):
        names = {"heat": "Heat", "haze": "Haze", "vulnerability": "Vulnerable seniors", "access": "Distance to a cool space",
                 "pct_65_plus": "Share aged 65+", "pop_65_plus": "Number aged 65+", "pct_1_2_room": "Share in 1–2 room flats",
                 "pa_pct_one_person": "One-person households", "pa_pct_difficulty": "Daily-activity difficulty"}
        c1, c2 = st.columns(2)
        for col, score, title in [(c1, "risk_score", "Risk score (0–100)"), (c2, "vulnerability_score", "Vulnerability (part of the risk score)")]:
            t = w[w["score"] == score].assign(Part=lambda d: d["component"].map(names), Weight=lambda d: d["weight"])
            col.markdown(f"**{title}**")
            col.dataframe(t[["Part", "Weight", "description"]].rename(columns={"description": "How it's measured"}), hide_index=True,
                          width="stretch", column_config={"Weight": st.column_config.NumberColumn(format="percent")})
    st.caption("Vulnerability compares each area with all other areas that have at least 50 seniors (percentile ranks), so very different measures can be combined fairly.")

    st.subheader("What to do at each level (rulebook)")
    rb = data.rulebook()
    if rb is not None and len(rb):
        rb = rb.assign(When=lambda d: d.apply(lambda r: f"{'Heat' if r['trigger'] == 'heat' else 'Haze'}: {r['level']}", axis=1))
        st.dataframe(rb[["When", "action"]].rename(columns={"action": "Action"}), hide_index=True, width="stretch",
                     column_config={"Action": st.column_config.TextColumn(width="large")})
    st.caption("Actions are fixed by people, not chosen by AI. They are a draft to be checked against NEA's heat-stress and haze advisories. "
               "The AI writing assistant only rewords and translates them.")

    st.subheader("Glossary")
    g = pd.DataFrame([
        ("WBGT", "Wet Bulb Globe Temperature (°C): NEA's heat-stress measure. It combines air temperature, humidity, sunshine and wind — how hot it feels to the body."),
        ("Heat-stress level", "NEA bands: Low (below 31 °C), Moderate (31–32.9 °C), High (33 °C and above)."),
        ("Afternoon peak", "The highest WBGT between 12 pm and 6 pm — the most dangerous time for seniors outdoors."),
        ("High-heat alert", "HeatGuard's model sees a meaningful chance of High heat tomorrow, even if the typical forecast is Moderate. Plan as for a High day."),
        ("PSI", "Pollutant Standards Index (24-hour), NEA's haze measure. Good ≤ 50, Moderate 51–100, Unhealthy 101–200, Very unhealthy 201–300, Hazardous above 300."),
        ("Subzone / planning area", "URA's map units. A planning area (e.g. Bukit Merah) contains several subzones (e.g. Telok Blangah Rise)."),
        ("Cool space", "A free, air-conditioned public place seniors can go to: Community Clubs and public libraries."),
    ], columns=["Term", "Meaning"])
    st.dataframe(g, hide_index=True, width="stretch", column_config={"Meaning": st.column_config.TextColumn(width="large")})

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Limitations")
        st.markdown(
            "- Heat is measured at ~30 stations; values for each area are blended from the nearest three, so very local hot spots can be missed.\n"
            "- Census data is from 2020. Living-alone and daily-activity figures are published only for the 30 largest planning areas; elsewhere the national rate is used (shown on *Why here?*).\n"
            "- Distances to cool spaces are straight-line from the area's centre, not walking routes.\n"
            "- There is no official haze forecast, so the latest haze reading is carried forward.\n"
            "- The action wording is a draft and should be checked by an Active Ageing Centre coordinator.")
    with c2:
        st.subheader("Privacy")
        st.markdown("HeatGuard uses **area-level open data only** — no names, addresses or personal records. "
                    "It tells coordinators *where and when* to act; their own client lists tell them *who*.")
        st.subheader("Data sources")
        st.markdown("- **NEA** (via data.gov.sg): WBGT, 24-hour forecast, PSI, PM2.5, air temperature, humidity\n"
                    "- **Singapore Department of Statistics**: Census of Population 2020\n"
                    "- **URA**: Master Plan 2019 subzone boundaries\n"
                    "- **People's Association**: Community Clubs · **NLB**: public libraries\n\n"
                    "Open data under the Singapore Open Data Licence. Built on Databricks: Lakeflow pipeline, Unity Catalog, MLflow, Genie, "
                    "Foundation Model APIs and Databricks Apps.")
