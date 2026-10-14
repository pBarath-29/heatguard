"""Start the web server on the port Databricks Apps provides (8000 locally)."""
import os

import uvicorn

uvicorn.run("server.main:app", host="0.0.0.0", port=int(os.environ.get("DATABRICKS_APP_PORT", "8000")), proxy_headers=True)
