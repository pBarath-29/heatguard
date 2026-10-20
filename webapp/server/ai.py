"""Genie (Ask HeatGuard): the link for the Genie space embedded on the Ask page."""
import os
import re
from functools import lru_cache


from .db import DataError, config, setting, workspace


@lru_cache(maxsize=1)
def _workspace_id() -> str:
    wid = os.environ.get("DATABRICKS_WORKSPACE_ID", "").strip()
    if wid:
        return wid
    try:
        return str(workspace().get_workspace_id())
    except Exception as e:  # noqa: BLE001
        raise DataError("Couldn't work out the Databricks workspace for Genie. Please try again later.", str(e)) from e


def embed_links() -> dict:
    space_id = setting("GENIE_SPACE_ID")
    if not re.fullmatch(r"[0-9a-f]{32}", space_id):
        raise DataError("The Genie space id in the app settings looks wrong. Ask the HeatGuard team to check it.")
    host = (config().host or "").rstrip("/")
    if not host.startswith("https://"):
        raise DataError("The app doesn't know its Databricks address, so Genie can't be shown here. Please try again later.")
    org = _workspace_id()
    return {"embed_url": f"{host}/embed/genie/rooms/{space_id}?o={org}"}
