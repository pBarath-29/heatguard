"""Forecast accuracy: how good HeatGuard's forecast is, in plain English."""
import altair as alt
import pandas as pd
import streamlit as st

from heatguard_app import data, ui


def render():
    ui.hero("How accurate is the forecast?", "HeatGuard's forecast was tested on recent months it never saw while learning, against simple rules of thumb.")
    ev = data.model_evaluation()
    if ev is None:
        return
    if ev.empty:
        st.info("No evaluation results yet. Ask the HeatGuard team to run the forecast training notebook.", icon=":material/inbox:")
        return
    hg = ev[ev["model"].str.startswith("HeatGuard")].iloc[0]
    base = ev[~ev["model"].str.startswith("HeatGuard")].sort_values("mae").iloc[0]
    st.info(f"**Test period:** {hg['test_period']} · {int(hg['station-days']):,} station-days · model version {hg['model_version']}. "
            f"None of these days were used to build or tune the model.", icon=":material/science:")

    c = st.columns(4)
    ui.kpi(c[0], "Average miss", f"{hg['mae']:.2f} °C", f"vs {base['mae']:.2f} °C for '{base['model']}'", "#15803D",
           "Average difference between the forecast and the real afternoon peak.")
    ui.kpi(c[1], "Within 1 °C", ui.pct(hg["within_1c"]), f"vs {ui.pct(base['within_1c'])} for the best simple rule", "#15803D")
    ui.kpi(c[2], "High-heat days caught", ui.pct(hg["high_recall"]), "by the High-heat alert", "#B91C1C",
           "Of the station-days that really reached High (WBGT ≥ 33 °C), the share HeatGuard had flagged the evening before.")
    ui.kpi(c[3], "Alerts that were High", ui.pct(hg["high_precision"]), "the rest were mostly Moderate days", "#B45309",
           "Of all High-heat alerts, the share that really reached High. Most other alerts were still Moderate days.")
    st.write("")
    st.markdown(f"**In short:** HeatGuard's forecast misses by **{(1 - hg['mae'] / base['mae']) * 100:.0f}% less** than the best simple rule "
                f"('{base['model']}'), and its alert caught **{ui.pct(hg['high_recall'])}** of High-heat days. "
                "Alerts lean towards caution on purpose: an extra phone call costs little; a missed High day can cost a senior's health.")

    left, right = st.columns(2)
    with left:
        st.subheader("Average miss by method")
        e = ev.assign(method=ev["model"].str.replace(r" \(.*\)", "", regex=True), highlight=ev["model"].str.startswith("HeatGuard"))
        ch = alt.Chart(e).mark_bar(cornerRadiusEnd=4).encode(
            y=alt.Y("method:N", sort="x", title=None), x=alt.X("mae:Q", title="Average miss (°C) — lower is better"),
            color=alt.condition("datum.highlight", alt.value("#15803D"), alt.value("#CBD5E1")),
            tooltip=[alt.Tooltip("model:N", title="Method"), alt.Tooltip("mae:Q", title="Average miss °C", format=".2f"),
                     alt.Tooltip("within_1c:Q", title="Within 1 °C", format=".0%"), alt.Tooltip("band_accuracy:Q", title="Right band", format=".0%")])
        st.altair_chart(ch.properties(height=200))
        st.caption("'Persistence' = tomorrow will be like today. '7-day average' = tomorrow will be like the past week.")
    with right:
        st.subheader("What the forecast relies on")
        fi = data.feature_importance()
        if fi is not None and len(fi):
            ch = alt.Chart(fi.head(8)).mark_bar(color="#6B8FB5", cornerRadiusEnd=4).encode(
                y=alt.Y("feature:N", sort="-x", title=None), x=alt.X("mae_increase_c:Q", title="How much worse without it (°C)"),
                tooltip=[alt.Tooltip("feature:N", title="Input"), alt.Tooltip("mae_increase_c:Q", title="Extra miss °C", format=".3f")])
            st.altair_chart(ch.properties(height=200))
            st.caption("Each input was scrambled in turn; a big jump in the miss means the forecast depends on it.")

    st.subheader("Forecast vs what happened (test period, average of all stations)")
    bt = data.backtest_daily()
    if bt is not None and len(bt):
        bt["date"] = pd.to_datetime(bt["target_date"])
        long = bt.melt(id_vars="date", value_vars=["actual", "heatguard", "baseline"], var_name="series", value_name="wbgt")
        names = {"actual": "What happened", "heatguard": "HeatGuard forecast", "baseline": f"{bt['baseline_name'].iloc[0]} rule"}
        long["series"] = long["series"].map(names)
        ch = alt.Chart(long).mark_line().encode(
            x=alt.X("date:T", title=None), y=alt.Y("wbgt:Q", title="Afternoon peak WBGT (°C)", scale=alt.Scale(zero=False)),
            color=alt.Color("series:N", title=None, scale=alt.Scale(domain=list(names.values()), range=["#111827", "#16A34A", "#CBD5E1"]),
                            legend=alt.Legend(orient="top")),
            strokeWidth=alt.condition(alt.datum.series == "What happened", alt.value(2.5), alt.value(1.8)),
            tooltip=[alt.Tooltip("date:T", title="Day"), "series:N", alt.Tooltip("wbgt:Q", title="°C", format=".2f")])
        st.altair_chart(ch.properties(height=300))
        st.caption("Each point is the average across stations for one day. The green line should follow the black line more closely than the grey one.")

    st.subheader("Live track record")
    tr = data.track_record()
    if tr is None:
        return
    if tr.empty:
        st.info("Live forecasts started recently. Results appear here the day after each forecasted day has been observed.", icon=":material/hourglass_top:")
    else:
        t = tr.rename(columns={"target_date": "Day", "stations": "Stations", "avg_error_c": "Average miss (°C)",
                               "band_correct": "Right heat level", "stations_high": "Stations that hit High", "high_caught": "…of which alerted"})
        st.dataframe(t, hide_index=True, width="stretch", column_config={
            "Average miss (°C)": st.column_config.NumberColumn(format="%.2f"),
            "Right heat level": st.column_config.NumberColumn(format="percent")})
