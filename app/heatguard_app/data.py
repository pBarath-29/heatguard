"""Data access: every query goes through `load()`, which caches results and turns failures into friendly messages."""
import datetime as dt
import os

import pandas as pd
import streamlit as st

S = "workspace.heatguard"
SGT = dt.timezone(dt.timedelta(hours=8))


class ConfigError(RuntimeError):
    pass


def setting(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise ConfigError(f"The app setting {name} is missing. Add the matching resource to the app (see app/README.md).")
    return value


@st.cache_resource(show_spinner=False)
def _config():
    from databricks.sdk.core import Config
    return Config()


@st.cache_resource(show_spinner=False)
def workspace():
    from databricks.sdk import WorkspaceClient
    return WorkspaceClient()


def _connect():
    from databricks import sql
    cfg = _config()
    return sql.connect(server_hostname=cfg.host, http_path=f"/sql/1.0/warehouses/{setting('DATABRICKS_WAREHOUSE_ID')}",
                       credentials_provider=lambda: cfg.authenticate)


@st.cache_data(ttl=300, show_spinner=False)
def _query(statement, params=None):
    with _connect() as conn, conn.cursor() as cur:
        cur.execute(statement, params or {})
        return cur.fetchall_arrow().to_pandas()


def friendly(error):
    """Turn a technical error into a sentence a coordinator can act on."""
    text = str(error)
    if isinstance(error, ConfigError):
        return text
    if "TABLE_OR_VIEW_NOT_FOUND" in text:
        return "Some HeatGuard data hasn't been created yet. Ask the team to run the daily HeatGuard job, then try again."
    if "PERMISSION_DENIED" in text or "Insufficient privileges" in text or "403" in text:
        return "The app doesn't have permission to read the HeatGuard data. Ask the team to grant it access (see app/README.md)."
    if "RESOURCE_EXHAUSTED" in text or "quota" in text.lower():
        return "Databricks is busy or the free-usage limit was reached. Wait a minute and try again."
    if "timed out" in text.lower() or "timeout" in text.lower():
        return "The data warehouse took too long to answer. It may still be starting up — try again in a moment."
    return "Something went wrong while loading the data. Try again; if it keeps happening, tell the HeatGuard team."


def load(statement, params=None, what="data"):
    """Run a query with a spinner; on failure show a friendly message with a retry button and return None."""
    try:
        with st.spinner(f"Loading {what}… (the first load of the day can take up to 30 seconds while the warehouse starts)"):
            return _query(statement, params)
    except Exception as e:  # noqa: BLE001 — every failure becomes a friendly message
        show_error(f"Couldn't load {what}.", e)
        return None


def show_error(headline, error):
    st.error(f"**{headline}** {friendly(error)}", icon=":material/error:")
    with st.expander("Technical details (for the HeatGuard team)"):
        st.code(str(error)[:3000], language=None)
    if st.button("Try again", key=f"retry_{abs(hash(headline)) % 10**8}", icon=":material/refresh:"):
        _query.clear()
        st.rerun()


def refresh_all():
    _query.clear()


# ---------- queries used by the pages ----------

def checkin_list():
    return load(f"SELECT * FROM {S}.gold_checkin_list ORDER BY rank", what="tomorrow's check-in list")


def station_latest():
    return load(f"SELECT * FROM {S}.gold_wbgt_station_latest ORDER BY wbgt_c DESC", what="the latest heat readings")


def haze_latest():
    return load(f"SELECT * FROM {S}.gold_haze_latest ORDER BY region", what="the latest haze readings")


def daily_summary(days=30):
    return load(f"SELECT * FROM {S}.gold_daily_summary WHERE date_sgt >= date_sub(current_date(), {int(days)}) ORDER BY date_sgt",
                what="recent daily heat and haze")


def station_weights(subzone):
    return load(f"SELECT * FROM {S}.gold_subzone_station_weights WHERE subzone_name = :sz ORDER BY station_rank",
                {"sz": subzone}, what="the weather stations near this area")


def station_peaks(station_ids, days=30):
    ids = ",".join("'" + s.replace("'", "") + "'" for s in station_ids) or "''"
    return load(f"""SELECT p.station_id, s.station_name, p.date_sgt, p.afternoon_peak_wbgt_c
                    FROM {S}.silver_wbgt_daily_peak p JOIN {S}.silver_wbgt_stations s USING (station_id)
                    WHERE p.station_id IN ({ids}) AND p.afternoon_readings >= 12 AND p.date_sgt >= date_sub(current_date(), {int(days)})
                    ORDER BY p.date_sgt""", what="recent afternoon peaks")


def station_forecasts(station_ids):
    ids = ",".join("'" + s.replace("'", "") + "'" for s in station_ids) or "''"
    return load(f"""SELECT station_id, station_name, target_date, predicted_peak_wbgt_c, prob_high
                    FROM {S}.ml_wbgt_forecast WHERE station_id IN ({ids})
                      AND target_date = (SELECT max(target_date) FROM {S}.ml_wbgt_forecast)""", what="the forecast for nearby stations")


def cool_spaces():
    return load(f"SELECT name, space_type, latitude, longitude, street, postal_code FROM {S}.silver_cool_spaces", what="cool spaces")


def model_evaluation():
    return load(f"SELECT * FROM {S}.ml_model_evaluation", what="forecast accuracy")


def backtest_daily():
    return load(f"""SELECT target_date, avg(actual_peak_wbgt_c) AS actual, avg(predicted_peak_wbgt_c) AS heatguard,
                           avg(baseline_peak_wbgt_c) AS baseline, max(baseline_name) AS baseline_name,
                           sum(CASE WHEN actual_band = 'High' THEN 1 ELSE 0 END) AS stations_high,
                           sum(CASE WHEN high_alert THEN 1 ELSE 0 END) AS stations_alerted
                    FROM {S}.ml_backtest_predictions GROUP BY target_date ORDER BY target_date""", what="past forecasts")


def feature_importance():
    return load(f"SELECT feature, mae_increase_c FROM {S}.ml_feature_importance ORDER BY mae_increase_c DESC", what="what the forecast relies on")


def track_record():
    return load(f"""SELECT target_date, count(*) AS stations, avg(abs_error_c) AS avg_error_c,
                           avg(CASE WHEN actual_band = predicted_band THEN 1.0 ELSE 0.0 END) AS band_correct,
                           sum(CASE WHEN actual_band = 'High' THEN 1 ELSE 0 END) AS stations_high,
                           sum(CASE WHEN high_alert AND actual_band = 'High' THEN 1 ELSE 0 END) AS high_caught
                    FROM {S}.ml_forecast_track_record WHERE actual_peak_wbgt_c IS NOT NULL
                    GROUP BY target_date ORDER BY target_date DESC""", what="the live forecast track record")


def score_weights():
    return load(f"SELECT * FROM {S}.gold_score_weights", what="the score weights")


def rulebook():
    return load(f"SELECT * FROM {S}.gold_rulebook", what="the action rulebook")


# ---------- small helpers ----------

def today_sgt():
    return dt.datetime.now(SGT).date()


def to_sgt(ts):
    """Timestamp (UTC or naive UTC) → aware SGT datetime, or None."""
    if ts is None or pd.isna(ts):
        return None
    t = pd.Timestamp(ts)
    t = t.tz_localize("UTC") if t.tzinfo is None else t
    return t.tz_convert("Asia/Singapore").to_pydatetime()


def nice_date(d, with_year=False):
    if d is None or pd.isna(d):
        return "—"
    d = pd.Timestamp(d)
    return d.strftime("%a %-d %b %Y" if with_year else "%a %-d %b") if os.name != "nt" else d.strftime("%a %#d %b %Y" if with_year else "%a %#d %b")


def ago(t):
    """'12 minutes ago' style text for an aware datetime."""
    if t is None:
        return "unknown"
    secs = (dt.datetime.now(SGT) - t).total_seconds()
    if secs < 90:
        return "just now"
    if secs < 3600:
        return f"{int(secs // 60)} minutes ago"
    if secs < 172800:
        h = int(secs // 3600)
        return f"{h} hour{'s' if h != 1 else ''} ago"
    return f"{int(secs // 86400)} days ago"
