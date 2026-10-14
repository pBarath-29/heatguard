"""Home page: tomorrow's ranked check-in list."""
import pandas as pd
import pydeck as pdk
import streamlit as st

from heatguard_app import data, nav, ui
from heatguard_app.message import message_dialog

PAGE_SIZE = 10


def _status(df):
    """One clear sentence about which day the list is for and how fresh it is."""
    for_date = pd.Timestamp(df["for_date"].max()).date() if df["for_date"].notna().any() else None
    is_fc = bool(df["heat_is_forecast"].fillna(False).any())
    basis = df["heat_basis"].dropna().iloc[0] if df["heat_basis"].notna().any() else ""
    today = data.today_sgt()
    if not is_fc:
        st.warning(f"**Tomorrow's forecast isn't ready yet.** Heat below is the latest *observed* afternoon peak ({basis.split(' on ')[-1]}). "
                   "The forecast is added after the evening update (around 7 pm).", icon=":material/schedule:")
    elif for_date and for_date < today:
        st.warning(f"**This list is for {data.nice_date(for_date)}, which has passed.** The evening update hasn't run since. "
                   "Use it as a rough guide only and let the HeatGuard team know.", icon=":material/history:")
    elif for_date == today:
        st.info(f"**This list is for today, {data.nice_date(for_date)}.** Tomorrow's list appears after this evening's update (around 7 pm).",
                icon=":material/today:")
    else:
        st.success(f"**List for {data.nice_date(for_date)}** — heat is HeatGuard's forecast ({basis.split('(')[-1].rstrip(')')}); "
                   "haze is the latest reading (there is no official haze forecast).", icon=":material/event_available:")
    return for_date


def _kpis(df):
    c = st.columns(4)
    alert = int((df["action_band"] == "High").sum())
    moderate = int((df["action_band"] == "Moderate").sum())
    top20 = int(df.loc[df["rank"] <= 20, "pop_65_plus"].sum())
    worst = df.loc[df["psi_twenty_four_hourly"].idxmax()] if df["psi_twenty_four_hourly"].notna().any() else None
    ui.kpi(c[0], "High-heat alerts", f"{alert}", f"of {len(df)} areas with seniors", "#B91C1C" if alert else "#15803D",
           "Areas forecast High, or with a meaningful chance of High heat. Use the High heat actions.")
    ui.kpi(c[1], "Moderate heat", f"{moderate}", "areas", "#B45309" if moderate else "#15803D",
           "Areas forecast Moderate heat stress (WBGT 31–32.9 °C).")
    ui.kpi(c[2], "Seniors in top 20 areas", ui.num(top20), "residents aged 65+", "#7C2D12",
           "How many residents aged 65+ live in the 20 highest-priority areas (Census 2020).")
    if worst is not None:
        ui.kpi(c[3], "Haze", str(worst["psi_band"]), f"worst PSI {int(worst['psi_twenty_four_hourly'])} ({str(worst['haze_region']).title()})",
               ui.PSI.get(worst["psi_band"], {}).get("fg", "#111827"), "24-hour PSI, latest reading, worst of NEA's 5 regions.")
    else:
        ui.kpi(c[3], "Haze", "No reading", "", "#6B7280")


def _filters(df):
    c1, c2, c3 = st.columns([2.2, 2.2, 2.6])
    q = c1.text_input("Find an area", placeholder="e.g. Toa Payoh, Bedok North", key="ck_search",
                      help="Search by subzone or planning area name.")
    areas = sorted(df["planning_area"].dropna().unique())
    pas = c2.multiselect("Planning area", [a.title() for a in areas], key="ck_pa", placeholder="All planning areas")
    level = c3.segmented_control("Heat level", ["All areas", "Moderate or higher", "High-heat alerts"], default="All areas",
                                 key="ck_level", help="High-heat alerts include areas forecast High and areas with a meaningful chance of High.")
    out = df
    if q:
        ql = q.strip().upper()
        out = out[out["subzone_name"].str.contains(ql, regex=False) | out["planning_area"].str.contains(ql, regex=False)]
    if pas:
        out = out[out["planning_area"].isin([p.upper() for p in pas])]
    if level == "Moderate or higher":
        out = out[out["action_band"].isin(["Moderate", "High"])]
    elif level == "High-heat alerts":
        out = out[out["action_band"] == "High"]
    return out


def _card(row):
    name = str(row["subzone_name"]).title()
    with st.container(border=True):
        c1, c2, c3 = st.columns([0.8, 6.2, 1.3], vertical_alignment="top")
        c1.markdown(f'<div class="hg-rank">#{int(row["rank"])}</div>', unsafe_allow_html=True)
        badges = ui.band_badge(row["action_band"], "Heat: ")
        if row.get("high_alert") and row.get("heat_band") != "High":
            badges += ui.badge(f"⚠️ High heat possible ({row['prob_high'] * 100:.0f}% chance)", "#B91C1C", "#FEE2E2")
        badges += ui.driver_badge(row["main_driver"])
        if pd.notna(row.get("psi_band")):
            badges += ui.psi_badge(row["psi_band"], row.get("psi_twenty_four_hourly"))
        c2.markdown(f'<div class="hg-area">{ui.esc(name)}</div>'
                    f'<div class="hg-pa">{ui.esc(str(row["planning_area"]).title())} · {ui.num(row["pop_65_plus"])} residents aged 65+'
                    f' · nearest cool space {ui.esc(row["nearest_cool_space"])} ({row["cool_space_km"]} km)</div>'
                    f'<div style="margin-top:6px">{badges}</div>'
                    f'<div class="hg-action"><b>What to do:</b> {ui.esc(row["action"])}</div>', unsafe_allow_html=True)
        c3.markdown(ui.score_box(row["risk_score"], row["action_band"]), unsafe_allow_html=True)
        b1, b2, _ = c2.columns([1, 1.25, 2.5])
        if b1.button("Why here?", key=f"why_{row['subzone_name']}", icon=":material/travel_explore:", width="stretch"):
            nav.go("why", selected_subzone=row["subzone_name"])
        if b2.button("Write a message", key=f"msg_{row['subzone_name']}", icon=":material/sms:", width="stretch"):
            message_dialog(row.to_dict())


def _map(df, show_cool):
    m = df.dropna(subset=["centroid_latitude", "centroid_longitude"]).copy()
    m["name"] = m["subzone_name"].str.title()
    m["pa"] = m["planning_area"].str.title()
    m["color"] = m["risk_score"].apply(ui.risk_rgb)
    m["radius"] = (m["pop_65_plus"].clip(lower=50) ** 0.5) * 9
    layers = [pdk.Layer("ScatterplotLayer", m, get_position="[centroid_longitude, centroid_latitude]", get_fill_color="color",
                        get_radius="radius", radius_min_pixels=4, radius_max_pixels=28, pickable=True,
                        stroked=True, get_line_color=[255, 255, 255], line_width_min_pixels=1)]
    if show_cool:
        cs = data.cool_spaces()
        if cs is not None and len(cs):
            cs = cs.assign(name=cs["name"], pa=cs["space_type"], rank="", risk_score="", action_band="cool space", color=[[37, 99, 235, 220]] * len(cs))
            layers.append(pdk.Layer("ScatterplotLayer", cs, get_position="[longitude, latitude]", get_fill_color="color",
                                    get_radius=120, radius_min_pixels=3, radius_max_pixels=7, pickable=True))
    st.pydeck_chart(pdk.Deck(
        layers=layers, map_style=pdk.map_styles.CARTO_LIGHT, map_provider="carto",
        initial_view_state=pdk.ViewState(latitude=1.355, longitude=103.82, zoom=10.4),
        tooltip={"html": "<b>#{rank} {name}</b><br/>{pa}<br/>Risk score {risk_score} · Heat {action_band}",
                 "style": {"backgroundColor": "#1F2937", "color": "white", "fontSize": "13px"}}), height=520)
    st.caption("Circle size = number of residents aged 65+. Colour = risk score (amber → deep red)."
               + (" Blue dots = Community Clubs and libraries." if show_cool else ""))


def render():
    ui.hero("Tomorrow's check-in list", "Where to check on seniors first, and what to do — updated every evening from NEA heat and haze data.")
    df = data.checkin_list()
    if df is None:
        return
    if df.empty:
        st.info("The check-in list is empty. Ask the HeatGuard team to run the daily update.", icon=":material/inbox:")
        return
    _status(df)
    _kpis(df)
    st.write("")
    with st.expander("How to use this list", icon=":material/help:"):
        s = st.columns(3)
        for col, n, title, body in [
            (s[0], 1, "Start at the top", "Areas are ranked by risk: heat tomorrow, haze, how many vulnerable seniors live there, and how far they are from a cool space."),
            (s[1], 2, "Follow 'What to do'", "Each area shows the action for its heat and haze level. Red 'High heat possible' means plan as for a High day."),
            (s[2], 3, "Share it", "Use **Write a message** for a ready-to-send note in English, Chinese, Malay or Tamil, or download the list for your team."),
        ]:
            col.markdown(f'<div class="hg-step"><span class="num">{n}</span><b>{title}</b><br/><span class="hg-note">{body}</span></div>',
                         unsafe_allow_html=True)

    filtered = _filters(df)
    sig = (st.session_state.get("ck_search"), tuple(st.session_state.get("ck_pa") or ()), st.session_state.get("ck_level"))
    if st.session_state.get("ck_sig") != sig:          # filters changed: start again from the top of the list
        st.session_state["ck_sig"], st.session_state["ck_shown"] = sig, PAGE_SIZE
    tab_list, tab_map, tab_table = st.tabs([":material/view_agenda: List", ":material/map: Map", ":material/table: Table"])
    with tab_list:
        if filtered.empty:
            st.info("No areas match these filters. Clear the search or choose another heat level.", icon=":material/search_off:")
        else:
            shown = st.session_state.get("ck_shown", PAGE_SIZE)
            st.caption(f"Showing {min(shown, len(filtered))} of {len(filtered)} areas, highest priority first.")
            for _, row in filtered.head(shown).iterrows():
                _card(row)
            if shown < len(filtered):
                if st.button(f"Show {min(PAGE_SIZE, len(filtered) - shown)} more", icon=":material/expand_more:", width="stretch"):
                    st.session_state["ck_shown"] = shown + PAGE_SIZE
                    st.rerun()
    with tab_map:
        show_cool = st.toggle("Show Community Clubs and libraries", value=False, key="ck_cool")
        if filtered.empty:
            st.info("No areas match these filters.", icon=":material/search_off:")
        else:
            _map(filtered, show_cool)
    with tab_table:
        cols = {"rank": "Rank", "subzone_name": "Area", "planning_area": "Planning area", "risk_score": "Risk score",
                "action_band": "Heat level", "heat_wbgt_c": "Heat (WBGT °C)", "prob_high": "Chance of High",
                "pop_65_plus": "Seniors 65+", "pct_65_plus": "% aged 65+", "nearest_cool_space": "Nearest cool space",
                "cool_space_km": "Distance (km)", "psi_band": "Haze", "reason": "Why", "action": "What to do"}
        t = filtered[list(cols)].rename(columns=cols)
        t["Area"] = t["Area"].str.title(); t["Planning area"] = t["Planning area"].str.title()
        st.dataframe(t, hide_index=True, width="stretch", height=520, column_config={
            "Risk score": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.0f"),
            "Chance of High": st.column_config.NumberColumn(format="percent"),
            "% aged 65+": st.column_config.NumberColumn(format="percent"),
            "Seniors 65+": st.column_config.NumberColumn(format="localized"),
        })
    st.download_button("Download this list (CSV)", filtered[list(cols)].rename(columns=cols).to_csv(index=False).encode("utf-8"),
                       file_name=f"heatguard_checkin_{df['for_date'].max()}.csv", mime="text/csv", icon=":material/download:")
