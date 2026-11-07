"""Append-only JSONL transcript for host chat sync."""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from typing import Any


class TranscriptStore:
    def __init__(self, path: str) -> None:
        self.path = path
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(path), exist_ok=True)

    def append(self, kind: str, content: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        event = {
            "id": f"nova_{uuid.uuid4().hex[:12]}",
            "kind": kind,
            "content": content or "",
            "ts": time.time(),
        }
        if extra:
            event.update(extra)
        line = json.dumps(event, ensure_ascii=False)
        with self._lock:
            with open(self.path, "a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        return event

    def read_all(self) -> list[dict[str, Any]]:
        if not os.path.isfile(self.path):
            return []
        rows: list[dict[str, Any]] = []
        with open(self.path, encoding="utf-8", errors="replace") as handle:
            for raw in handle:
                line = raw.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(item, dict):
                    rows.append(item)
        return rows
