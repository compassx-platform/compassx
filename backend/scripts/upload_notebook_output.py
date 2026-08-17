"""Upload a papermill output notebook using the configured storage backend."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from services.storage.config import storage_settings
from services.storage.fs import get_fs


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: upload_notebook_output.py <output_notebook>", file=sys.stderr)
        return 2

    output_path = Path(sys.argv[1])
    if not output_path.exists():
        print(f"output file not found: {output_path}", file=sys.stderr)
        return 1

    filename = os.environ.get("COMPASSX_OUTPUT_FILENAME") or output_path.name
    key = storage_settings.outputs_object_name(filename)
    uri = get_fs().upload_file(output_path, storage_settings.STORAGE_OUTPUTS_BUCKET, key)
    print(uri)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
