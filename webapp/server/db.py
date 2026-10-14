"""Warehouse access with a small in-memory cache and friendly error messages."""
import datetime as dt
import json
import os
import threading
import time
from functools import lru_cache

import pandas as pd

S = "workspace.heatguard"
SGT = dt.timezone(dt.timedelta(hours=8))
CACHE_SECONDS = 300


class ConfigError(RuntimeError):
    pass


class DataError(RuntimeError):
    """An error with a message that is safe and useful to show to a coordinator."""
    def __init__(self, message, detail=""):
        super().__init__(message)
        self.detail = detail


def setting(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise ConfigError(f"The app setting {name} is missing. Add the matching resource to the app (see webapp/README.md).")
    return value


@lru_cache(maxsize=1)
def config():
    from databricks.sdk.core import Config
    return Config()


@lru_cache(maxsize=1)
def workspace():
    from databricks.sdk import WorkspaceClient
    return WorkspaceClient()


def friendly(error):
    text = str(error)
    if isinstance(error, (ConfigError, DataError)):
        return str(error)
    if "TABLE_OR_VIEW_NOT_FOUND" in text:
        return "Some HeatGuard data hasn't been created yet. Ask the team to run the daily HeatGuard job, then try again."
    if "PERMISSION_DENIED" in text or "Insufficient privileges" in text or "403" in text:
        return "The app doesn't have permission to read the HeatGuard data. Ask the team to grant it access."
    if "RESOURCE_EXHAUSTED" in text or "quota" in text.lower():
        return "Databricks is busy or the free-usage limit was reached. Wait a minute and try again."
    if "timed out" in text.lower() or "timeout" in text.lower():
        return "The data warehouse took too long to answer. It may still be starting up — try again in a moment."
    return "Something went wrong while loading the data. Try again; if it keeps happening, tell the HeatGuard team."


_cache, _lock = {}, threading.Lock()


def query(statement, params=None):
    """Run SQL on the warehouse; results are cached for five minutes."""
    key = (statement, json.dumps(params or {}, sort_keys=True))
    now = time.time()
    with _lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < CACHE_SECONDS:
            return hit[1]
    from databricks import sql
    cfg = config()
    try:
        with sql.connect(server_hostname=cfg.host, http_path=f"/sql/1.0/warehouses/{setting('DATABRICKS_WAREHOUSE_ID')}",
                         credentials_provider=lambda: cfg.authenticate) as conn, conn.cursor() as cur:
            cur.execute(statement, params or {})
            df = cur.fetchall_arrow().to_pandas()
    except Exception as e:  # noqa: BLE001
        raise DataError(friendly(e), str(e)[:2000]) from e
    with _lock:
        _cache[key] = (now, df)
    return df


def clear_cache():
    with _lock:
        _cache.clear()


def records(df):
    """DataFrame → JSON-safe list of dicts (NaN → null, timestamps → ISO strings)."""
    if df is None:
        return []
    return json.loads(df.to_json(orient="records", date_format="iso"))


def today_sgt():
    return dt.datetime.now(SGT).date()
