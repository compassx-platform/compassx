"""Download the execution-scoped notebook through the catalog-aware backend."""
from __future__ import annotations

import sys
import os
from urllib.request import Request, urlopen
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: download_notebook.py <execution_id> <local_dest>", file=sys.stderr)
        return 2

    execution_id = sys.argv[1]
    dest = Path(sys.argv[2])
    dest.parent.mkdir(parents=True, exist_ok=True)

    backend_url = os.environ["COMPASSX_BACKEND_URL"].rstrip("/")
    token = os.environ["COMPASSX_EXECUTION_TOKEN"]
    request = Request(
        f"{backend_url}/api/v1/job-executions/{execution_id}/notebook",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urlopen(request, timeout=60) as response:
        content = response.read()
    dest.write_bytes(content)
    print(f"downloaded catalog notebook for execution {execution_id} -> {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
