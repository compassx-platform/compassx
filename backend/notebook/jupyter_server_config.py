"""
Jupyter server configuration for the notebook sidecar.
Set JUPYTER_TOKEN env var to override the default token.
"""
import os

c = get_config()  # noqa: F821 — injected by jupyter_server

c.ServerApp.ip = "0.0.0.0"
c.ServerApp.port = 8888
c.ServerApp.open_browser = False
c.ServerApp.token = os.environ.get("JUPYTER_TOKEN", "compass-notebook-token")
c.ServerApp.password = ""
c.ServerApp.disable_check_xsrf = True
c.ServerApp.allow_origin = "*"
c.ServerApp.allow_credentials = True
c.ServerApp.root_dir = os.environ.get("JUPYTER_ROOT_DIR", ".")
