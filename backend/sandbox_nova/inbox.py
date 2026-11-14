from __future__ import annotations

import json
import os
import time

from sandbox_nova.config import NovaSettings


class InboxServer:
    def __init__(self, settings: NovaSettings, loop: NovaAgentLoop) -> None:
        self.settings = settings
        self.loop = loop

    def run(self) -> None:
        os.makedirs(self.settings.inbox_dir, exist_ok=True)
        print(f"Nova ready session={self.settings.session_id} workspace={self.settings.workspace_root}", flush=True)
        while True:
            turns = sorted(
                name for name in os.listdir(self.settings.inbox_dir)
                if name.endswith(".json") and not name.endswith(".done.json")
            )
            for name in turns:
                path = os.path.join(self.settings.inbox_dir, name)
                working = path + ".working"
                try:
                    os.rename(path, working)
                except OSError:
                    continue
                try:
                    with open(working, encoding="utf-8") as handle:
                        payload = json.load(handle)
                except (OSError, json.JSONDecodeError):
                    os.replace(working, path[:-5] + ".bad.json")
                    continue
                prompt = str(payload.get("prompt") or "").strip()
                model = str(payload.get("model") or "").strip() or None
                if prompt:
                    try:
                        self.loop.handle_turn(prompt, model=model)
                    except Exception as exc:
                        self.loop.transcript.append("error", str(exc))
                        print(f"Nova error: {exc}", flush=True)
                os.replace(working, path[:-5] + ".done.json")
            time.sleep(0.4)
