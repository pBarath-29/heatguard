"""Now: latest heat by station, haze by region, and the last 30 days."""
import datetime as dt

import altair as alt
import pandas as pd
import pydeck as pdk
import streamlit as st

from heatguard_app import data, ui


def _freshness(stations):
    latest = data.to_sgt(stations["latest_reading_ts"].max())
    if latest is None:
        return
    age = dt.datetime.now(data.SGT) - latest
    when = f"{latest:%a %d %b, %I:%M %p}".replace(" 0", " ")
    if age > dt.timedelta(hours=2):
        st.warning(f"**Readings are from {when} ({data.ago(latest)}).** Live updates (every 15 minutes) may be switched off to save "
                   "Databricks quota; the check-in list is still updated every evening.", icon=":material/schedule:")
    else:
        st.success(f"Latest readings: {when} ({data.ago(latest)}). NEA updates heat every 15 minutes and haze every hour.",
                   icon=":material/sensors:")


def _station_map(stations):
    s = stations.dropna(subset=["latitude", "longitude", "wbgt_c"]).copy()
    s["color"] = s["heat_band"].map(lambda b: ui.BAND.get(b, {"rgb": [107, 114, 128]})["rgb"] + [230])
    s["label"] = s["wbgt_c"].map(lambda v: f"{v:.1f}")
    s["time"] = s["latest_time_sgt"]
    layers = [
        pdk.Layer("ScatterplotLayer", s, get_position="[longitude, latitude]", get_fill_color="color", get_radius=700,
                  radius_min_pixels=10, radius_max_pixels=22, pickable=True, stroked=True, get_line_color=[255, 255, 255], line_width_min_pixels=2),
        pdk.Layer("TextLayer", s, get_position="[longitude, latitude]", get_text="label", get_size=12, get_color=[255, 255, 255],
                  get_alignment_baseline="'center'", font_weight=700),
    ]
    st.pydeck_chart(pdk.Deck(layers=layers, map_style=pdk.map_styles.CARTO_LIGHT, map_provider="carto",
                             initial_view_state=pdk.ViewState(latitude=1.355, longitude=103.82, zoom=10.3),
                             tooltip={"html": "<b>{station_name}</b><br/>{town_center}<br/>WBGT {label} °C ({heat_band}) at {time}",
                                      "style": {"backgroundColor": "#1F2937", "color": "white", "fontSize": "13px"}}), height=460)
    st.caption("Each circle is an NEA heat-stress station, labelled with its latest WBGT (°C). Green = Low (< 31), amber = Moderate (31–32.9), red = High (≥ 33).")


def _trend(daily):
    d = daily.copy()
    d["date"] = pd.to_datetime(d["date_sgt"])
    heat = d.melt(id_vars="date", value_vars=["hottest_peak_wbgt_c", "avg_peak_wbgt_c"], var_name="series", value_name="wbgt")
    heat["series"] = heat["series"].map({"hottest_peak_wbgt_c": "Hottest station", "avg_peak_wbgt_c": "Average of stations"})
    rules = pd.DataFrame({"y": [31, 33], "label": ["Moderate (31 °C)", "High (33 °C)"]})
    line = alt.Chart(heat).mark_line(point=True).encode(
        x=alt.X("date:T", title=None), y=alt.Y("wbgt:Q", title="Afternoon peak WBGT (°C)", scale=alt.Scale(zero=False)),
        color=alt.Color("series:N", title=None, scale=alt.Scale(range=["#B91C1C", "#F59E0B"]), legend=alt.Legend(orient="top")),
        tooltip=[alt.Tooltip("date:T", title="Day"), "series:N", alt.Tooltip("wbgt:Q", format=".1f", title="WBGT °C")])
    rule = alt.Chart(rules).mark_rule(strokeDash=[4, 4], color="#9CA3AF").encode(y="y:Q")
    text = alt.Chart(rules).mark_text(align="left", dx=4, dy=-6, color="#6B7280", fontSize=11).encode(y="y:Q", text="label:N", x=alt.value(0))
    st.altair_chart((line + rule + text).properties(height=280))
    psi = alt.Chart(d).mark_bar(color="#94A3B8").encode(
        x=alt.X("date:T", title=None), y=alt.Y("worst_psi_24h:Q", title="Worst 24-hour PSI"),
        tooltip=[alt.Tooltip("date:T", title="Day"), alt.Tooltip("worst_psi_24h:Q", title="Worst PSI"), alt.Tooltip("worst_psi_band:N", title="Band")])
    unhealthy = alt.Chart(pd.DataFrame({"y": [100]})).mark_rule(strokeDash=[4, 4], color="#B45309").encode(y="y:Q")
    st.altair_chart((psi + unhealthy).properties(height=180))
    st.caption("Top: each day's afternoon peak (12–6 pm) — the hottest station and the average across stations. "
               "Bottom: the worst haze reading each day; above the dashed line (PSI 100) is Unhealthy.")


def render():
    ui.hero("Heat and haze right now", "Latest readings from NEA's heat-stress stations and haze regions, and how the last month compares.")
    stations = data.station_latest()
    haze = data.haze_latest()
    if stations is None:
        return
    if stations.empty:
        st.info("No station readings yet. Ask the HeatGuard team to run the data update.", icon=":material/inbox:")
        return
    _freshness(stations)

    c = st.columns(4)
    hottest = stations.loc[stations["wbgt_c"].idxmax()]
    hot_today = stations.loc[stations["peak_so_far_today_c"].idxmax()]
    mod_plus = int(stations["heat_band"].isin(["Moderate", "High"]).sum())
    ui.kpi(c[0], "Hottest station now", f"{hottest['wbgt_c']:.1f} °C", f"{hottest['station_name']} ({hottest['heat_band']})",
           ui.BAND.get(hottest["heat_band"], {}).get("fg", "#111827"))
    ui.kpi(c[1], "Stations Moderate or High", f"{mod_plus}", f"of {len(stations)} reporting", "#B45309" if mod_plus else "#15803D")
    ui.kpi(c[2], "Hottest so far today", f"{hot_today['peak_so_far_today_c']:.1f} °C", f"{hot_today['station_name']}",
           ui.BAND.get(hot_today["peak_so_far_band"], {}).get("fg", "#111827"))
    if haze is not None and len(haze):
        worst = haze.loc[haze["psi_twenty_four_hourly"].idxmax()]
        ui.kpi(c[3], "Worst haze", f"PSI {int(worst['psi_twenty_four_hourly'])}", f"{worst['psi_band']} · {str(worst['region']).title()}",
               ui.PSI.get(worst["psi_band"], {}).get("fg", "#111827"))
    st.write("")

    left, right = st.columns([3, 2])
    with left:
        st.subheader("Heat by station")
        _station_map(stations)
    with right:
        st.subheader("Haze by region")
        if haze is None or haze.empty:
            st.info("No haze readings available.", icon=":material/inbox:")
        else:
            for _, h in haze.iterrows():
                p = ui.PSI.get(h["psi_band"], {"fg": "#374151", "bg": "#F3F4F6"})
                pm = f" · PM2.5 {int(h['pm25_one_hourly'])} µg/m³ (1-hour)" if pd.notna(h.get("pm25_one_hourly")) else ""
                st.markdown(f'<div class="hg-kpi" style="margin-bottom:8px;border-left:6px solid {p["fg"]}">'
                            f'<div class="lbl">{ui.esc(str(h["region"]).title())}</div>'
                            f'<div class="val" style="color:{p["fg"]};font-size:1.35rem">PSI {int(h["psi_twenty_four_hourly"])} · {ui.esc(h["psi_band"])}</div>'
                            f'<div class="sub">24-hour PSI at {ui.esc(h["time_sgt"])}{ui.esc(pm)}</div></div>', unsafe_allow_html=True)
            st.caption("PSI bands: Good ≤ 50 · Moderate 51–100 · Unhealthy 101–200 · Very unhealthy 201–300 · Hazardous > 300.")

    with st.expander("All stations (table)", icon=":material/table:"):
        t = stations[["station_name", "town_center", "wbgt_c", "heat_band", "peak_so_far_today_c", "latest_time_sgt"]].rename(columns={
            "station_name": "Station", "town_center": "Near", "wbgt_c": "WBGT now (°C)", "heat_band": "Level",
            "peak_so_far_today_c": "Today's peak so far (°C)", "latest_time_sgt": "Time"})
        st.dataframe(t, hide_index=True, width="stretch")

    st.subheader("The last 30 days")
    daily = data.daily_summary(30)
    if daily is not None and len(daily):
        _trend(daily)
