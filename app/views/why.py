"""Why here? Explain one area's priority: score breakdown, people, heat, nearest cool space, recent trend."""
import urllib.parse

import altair as alt
import pandas as pd
import streamlit as st

from heatguard_app import data, ui
from heatguard_app.message import message_dialog

COMPONENT_LABELS = {"heat": "Heat", "haze": "Haze", "vulnerability": "Vulnerable seniors", "access": "Distance to a cool space"}
COMPONENT_COLORS = {"Heat": "#DC2626", "Haze": "#64748B", "Vulnerable seniors": "#7C3AED", "Distance to a cool space": "#2563EB"}


def _breakdown(row, weights):
    w = {r["component"]: r["weight"] for _, r in weights.iterrows() if r["score"] == "risk_score"} if weights is not None else {}
    w = w or {"heat": 0.35, "haze": 0.15, "vulnerability": 0.35, "access": 0.15}
    psi = row.get("psi_twenty_four_hourly")
    explain = {
        "heat": f"{row['heat_wbgt_c']:.1f} °C ({row['heat_band']}). Counts nothing at 29 °C and fully at 34 °C." if pd.notna(row.get("heat_wbgt_c")) else "No heat value.",
        "haze": (f"PSI {int(psi)} ({row['psi_band']}). Counts nothing up to PSI 50 and fully at 200." if pd.notna(psi) else "No haze reading."),
        "vulnerability": f"Vulnerability {row['vulnerability_score']:.2f} of 1 — how this area compares with others on seniors, small flats, living alone and daily-activity difficulty.",
        "access": f"{row['cool_space_km']} km to {row['nearest_cool_space']}. Counts nothing at the door and fully at 2 km or more.",
    }
    rows = []
    for k in ["heat", "vulnerability", "haze", "access"]:
        comp = row.get(f"{k}_component")
        comp = 0.0 if comp is None or pd.isna(comp) else float(comp)
        rows.append({"Part": COMPONENT_LABELS[k], "Points": round(100 * w.get(k, 0) * comp, 1),
                     "Maximum": round(100 * w.get(k, 0)), "What it means": explain[k]})
    return pd.DataFrame(rows)


def _confidence(stations):
    if stations is None or stations.empty:
        return "Unknown", "No station information."
    near = float(stations["distance_km"].min())
    if near <= 2:
        return "High", f"Measured by a station {near:.1f} km away."
    if near <= 5:
        return "Medium", f"The nearest station is {near:.1f} km away; heat is blended from {len(stations)} stations."
    return "Lower", f"The nearest station is {near:.1f} km away, so local heat may differ."


def render():
    ui.hero("Why here?", "See exactly why an area is on the list, who lives there, and where the nearest cool space is.")
    df = data.checkin_list()
    if df is None:
        return
    if df.empty:
        st.info("The check-in list is empty. Ask the HeatGuard team to run the daily update.", icon=":material/inbox:")
        return
    names = df["subzone_name"].tolist()
    default = st.session_state.get("selected_subzone", names[0])
    idx = names.index(default) if default in names else 0
    lookup = df.set_index("subzone_name")
    sel = st.selectbox("Choose an area", names, index=idx, key="why_select",
                       format_func=lambda n: f"#{int(lookup.loc[n, 'rank'])} · {n.title()} ({lookup.loc[n, 'planning_area'].title()})",
                       help="Type to search. Areas are listed in priority order.")
    st.session_state["selected_subzone"] = sel
    row = df[df["subzone_name"] == sel].iloc[0]

    with st.container(border=True):
        c1, c2 = st.columns([6, 1.3], vertical_alignment="center")
        badges = ui.band_badge(row["action_band"], "Heat: ") + ui.driver_badge(row["main_driver"])
        if row.get("high_alert") and row.get("heat_band") != "High":
            badges += ui.badge(f"⚠️ High heat possible ({row['prob_high'] * 100:.0f}% chance)", "#B91C1C", "#FEE2E2")
        c1.markdown(f'<div class="hg-area" style="font-size:1.5rem">{ui.esc(sel.title())}</div>'
                    f'<div class="hg-pa">Priority #{int(row["rank"])} of {len(df)} · {ui.esc(row["planning_area"].title())} · '
                    f'{ui.esc(str(row["ura_region"]).title())} · {ui.esc(row["heat_basis"])}</div><div style="margin-top:6px">{badges}</div>'
                    f'<div class="hg-action"><b>What to do:</b> {ui.esc(row["action"])}</div>', unsafe_allow_html=True)
        c2.markdown(ui.score_box(row["risk_score"], row["action_band"]), unsafe_allow_html=True)
        if c1.button("Write a message for this area", icon=":material/sms:", key="why_msg"):
            message_dialog(row.to_dict())

    st.subheader("How the risk score adds up")
    weights = data.score_weights()
    bd = _breakdown(row, weights)
    chart = alt.Chart(bd).mark_bar(cornerRadiusEnd=4).encode(
        y=alt.Y("Part:N", sort=None, title=None), x=alt.X("Points:Q", title="Points (out of 100 in total)", scale=alt.Scale(domain=[0, 35])),
        color=alt.Color("Part:N", scale=alt.Scale(domain=list(COMPONENT_COLORS), range=list(COMPONENT_COLORS.values())), legend=None),
        tooltip=["Part", "Points", "Maximum", "What it means"])
    st.altair_chart(chart.properties(height=190))
    st.dataframe(bd, hide_index=True, width="stretch", column_config={
        "Points": st.column_config.NumberColumn(format="%.1f"), "What it means": st.column_config.TextColumn(width="large")})
    st.caption(f"Total risk score: **{row['risk_score']:.0f}**. Weights: heat 35, vulnerable seniors 35, haze 15, distance to a cool space 15.")

    stations = data.station_weights(sel)
    c1, c2, c3 = st.columns(3)
    with c1, st.container(border=True):
        st.markdown("#### 👵 Who lives here")
        st.markdown(f"- **{ui.num(row['pop_65_plus'])}** residents aged 65+ (**{ui.pct(row['pct_65_plus'])}** of {ui.num(row['pop_total'])})\n"
                    f"- **{ui.num(row['pop_75_plus'])}** aged 75+ ({ui.pct(row['pct_75_plus'])})\n"
                    f"- **{ui.pct(row['pct_1_2_room'])}** of residents in 1–2 room HDB flats\n"
                    f"- **{ui.pct(row['pa_pct_one_person'])}** one-person households*\n"
                    f"- **{ui.pct(row['pa_pct_difficulty'])}** of households have someone with daily-activity difficulty*")
        note = ("*Planning-area figures for " + row["planning_area"].title() + "." if row["pa_data_published"]
                else "*Singapore-wide rate: the Census doesn't publish this for " + row["planning_area"].title() + ".")
        st.caption(note + " Source: Census 2020.")
    with c2, st.container(border=True):
        st.markdown("#### 🌡️ Heat")
        if row.get("heat_is_forecast"):
            st.markdown(f"- Forecast afternoon peak: **{row['heat_wbgt_c']:.1f} °C** ({row['heat_band']})\n"
                        f"- Chance of Moderate or higher: **{ui.pct(row['prob_moderate_plus'])}**\n"
                        f"- Chance of High: **{ui.pct(row['prob_high'])}**")
        else:
            st.markdown(f"- Latest observed afternoon peak: **{row['heat_wbgt_c']:.1f} °C** ({row['heat_band']})")
        if pd.notna(row.get("wbgt_latest_c")):
            st.markdown(f"- Latest reading: {row['wbgt_latest_c']:.1f} °C")
        level, why = _confidence(stations)
        st.markdown(f"- Measurement confidence: **{level}** — {why}")
        st.caption("WBGT combines temperature, humidity, sun and wind into one heat-stress number (NEA).")
    with c3, st.container(border=True):
        st.markdown("#### ❄️ Nearest cool space")
        addr = " ".join(str(x) for x in [row.get("nearest_cool_space_street"), row.get("nearest_cool_space_postal")] if x and pd.notna(x))
        st.markdown(f"**{row['nearest_cool_space']}**  \n{row['nearest_cool_space_type']} · {row['cool_space_km']} km from the area centre"
                    + (f"  \n{addr}" if addr else "") + f"\n\n{int(row['cool_spaces_within_1km'])} cool space(s) within 1 km.")
        q = urllib.parse.quote_plus(f"{row['nearest_cool_space']} Singapore {row.get('nearest_cool_space_postal') or ''}")
        st.link_button("Open in Google Maps", f"https://www.google.com/maps/search/?api=1&query={q}", icon=":material/directions:")
        st.caption("Community Clubs and public libraries are free and air-conditioned. Distance is straight-line.")

    st.subheader("Recent afternoon heat near this area")
    if stations is not None and len(stations):
        ids = stations["station_id"].tolist()
        peaks = data.station_peaks(ids, 30)
        fc = data.station_forecasts(ids)
        if peaks is not None and len(peaks):
            peaks["date"] = pd.to_datetime(peaks["date_sgt"])
            base = alt.Chart(peaks).mark_line(point=True).encode(
                x=alt.X("date:T", title=None), y=alt.Y("afternoon_peak_wbgt_c:Q", title="Afternoon peak WBGT (°C)", scale=alt.Scale(zero=False)),
                color=alt.Color("station_name:N", title="Station", legend=alt.Legend(orient="top")),
                tooltip=[alt.Tooltip("date:T", title="Day"), alt.Tooltip("station_name:N", title="Station"),
                         alt.Tooltip("afternoon_peak_wbgt_c:Q", title="Peak °C", format=".1f")])
            layers = [base, alt.Chart(pd.DataFrame({"y": [31, 33]})).mark_rule(strokeDash=[4, 4], color="#9CA3AF").encode(y="y:Q")]
            if fc is not None and len(fc):
                fc["date"] = pd.to_datetime(fc["target_date"])
                layers.append(alt.Chart(fc).mark_point(shape="diamond", size=140, filled=True, color="#111827").encode(
                    x="date:T", y="predicted_peak_wbgt_c:Q",
                    tooltip=[alt.Tooltip("date:T", title="Forecast for"), alt.Tooltip("station_name:N", title="Station"),
                             alt.Tooltip("predicted_peak_wbgt_c:Q", title="Forecast °C", format=".1f"),
                             alt.Tooltip("prob_high:Q", title="Chance of High", format=".0%")]))
            st.altair_chart(alt.layer(*layers).properties(height=300))
            st.caption("Lines: each nearby station's afternoon peak over the last 30 days. Black diamonds: HeatGuard's forecast. "
                       "Dashed lines: Moderate (31 °C) and High (33 °C).")
        t = stations[["station_name", "distance_km", "weight"]].rename(columns={"station_name": "Station", "distance_km": "Distance (km)",
                                                                                "weight": "Share of the area's heat value"})
        st.dataframe(t, hide_index=True, width="stretch",
                     column_config={"Share of the area's heat value": st.column_config.ProgressColumn(min_value=0, max_value=1, format="percent")})
