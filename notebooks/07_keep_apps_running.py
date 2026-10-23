# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "6"
# ///
# MAGIC %md
# MAGIC # 07 · Keep the HeatGuard website running
# MAGIC
# MAGIC **Why this exists:** on Databricks Free Edition, apps stop automatically after about 24 hours. When that happens the HeatGuard
# MAGIC website links show "app unavailable" until someone presses **Start**. This notebook is run by the job **`heatguard-keep-apps-on`**
# MAGIC twice a day so coordinators (and judges) always find the links working:
# MAGIC
# MAGIC | Run | What it does |
# MAGIC |---|---|
# MAGIC | **5:30 am** (Singapore) | Restarts each app (stop, then start), giving it a fresh 24 hours before coordinators start their day |
# MAGIC | **5:30 pm** (Singapore) | Starts any app that has stopped; leaves running apps alone |
# MAGIC
# MAGIC Starting an app redeploys its latest deployment, so no code changes are lost. A restart takes about two minutes.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Settings
# MAGIC The apps to keep running, and which mode to use. The mode is chosen from the Singapore time of the run (morning = restart),
# MAGIC or can be forced with the `mode` widget (`auto`, `restart` or `ensure`).

# COMMAND ----------

import datetime
from databricks.sdk import WorkspaceClient

APPS = ["heatguard-web"]
dbutils.widgets.text("mode", "auto", "auto / restart / ensure")
mode = dbutils.widgets.get("mode").strip() or "auto"
hour_sgt = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=8)).hour
if mode == "auto":
    mode = "restart" if hour_sgt < 12 else "ensure"
print(f"Mode: {mode} (Singapore hour {hour_sgt})")
w = WorkspaceClient()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Start or restart each app
# MAGIC For each app: read its state; in **restart** mode stop it first if it is running; then start it if it is not running and wait until it
# MAGIC is up. One app failing does not stop the other; the job is marked failed at the end if any app could not be started, so it shows red
# MAGIC in the job history.

# COMMAND ----------

import time

SOURCE = {"heatguard-web": "/Workspace/Users/yubrajb2907@gmail.com/heatguard/webapp"}   # code to redeploy if the app lost its deployment


def state(name):
    a = w.apps.get(name)
    return str(getattr(a.compute_status, "state", "")).split(".")[-1], str(getattr(a.app_status, "state", "")).split(".")[-1]


def deploying(a):
    return any(d is not None and "IN_PROGRESS" in str(getattr(getattr(d, "status", None), "state", ""))
               for d in (a.pending_deployment, a.active_deployment))


def wait_until_running(name, minutes=15):
    """After a start, Free Edition redeploys the app in the background (the app shows UNAVAILABLE meanwhile). Wait for it; if the app
    says it has no deployment and nothing is deploying, deploy the source code again."""
    deadline = time.time() + minutes * 60
    redeployed = False
    while time.time() < deadline:
        a = w.apps.get(name)
        app = str(getattr(a.app_status, "state", "")).split(".")[-1]
        if app == "RUNNING":
            return
        message = str(getattr(a.app_status, "message", "") or "")
        if not redeployed and not deploying(a) and "not been deployed" in message and name in SOURCE:
            print(f"{name}: no active deployment, redeploying {SOURCE[name]}")
            from databricks.sdk.service.apps import AppDeployment
            try:
                w.apps.deploy(name, app_deployment=AppDeployment(source_code_path=SOURCE[name]))
            except TypeError:                     # older SDKs take the path directly
                w.apps.deploy(name, source_code_path=SOURCE[name])
            redeployed = True
        time.sleep(20)

failures = []
for name in APPS:
    try:
        compute, app = state(name)
        print(f"{name}: before → compute {compute}, app {app}")
        if mode == "restart" and compute == "ACTIVE":
            w.apps.stop_and_wait(name, timeout=datetime.timedelta(minutes=10))
            compute = "STOPPED"
        if compute != "ACTIVE" or app != "RUNNING":
            w.apps.start_and_wait(name, timeout=datetime.timedelta(minutes=15))
        wait_until_running(name)
        compute, app = state(name)
        print(f"{name}: after  → compute {compute}, app {app}")
        if app != "RUNNING":
            failures.append(f"{name} is {app}")
    except Exception as e:  # noqa: BLE001 — try the other app too
        failures.append(f"{name}: {type(e).__name__}: {str(e)[:300]}")
        print(f"{name}: FAILED — {e}")

if failures:
    raise RuntimeError("Some apps are not running: " + "; ".join(failures))
print("All HeatGuard apps are running.")
