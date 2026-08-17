"""
Start jupyter_server as a sidecar process.
Run: python backend/notebook/start_server.py
Env vars:
  JUPYTER_TOKEN   — auth token (default: compass-notebook-token)
  JUPYTER_PORT    — port (default: 8888)
  JUPYTER_ROOT_DIR — notebooks root dir (default: current dir)
"""
import os
import subprocess
import sys
from pathlib import Path

config_file = Path(__file__).parent / "jupyter_server_config.py"

port = os.environ.get("JUPYTER_PORT", "8888")
token = os.environ.get("JUPYTER_TOKEN", "compass-notebook-token")
root_dir = os.environ.get("JUPYTER_ROOT_DIR", str(Path(__file__).parent.parent.parent))

subprocess.run(
    [
        sys.executable,
        "-m",
        "jupyter_server",
        f"--config={config_file}",
        f"--ServerApp.port={port}",
        f"--ServerApp.token={token}",
        f"--ServerApp.root_dir={root_dir}",
    ],
    check=True,
)
