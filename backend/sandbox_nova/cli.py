"""Entry point for `/usr/local/bin/nova`."""

from __future__ import annotations

import argparse
import json
import os
import sys

from sandbox_nova.config import NovaSettings
from sandbox_nova.llm import GatewayLLM
from sandbox_nova.loop import InboxServer, NovaAgentLoop
from sandbox_nova.tools.registry import build_default_registry
from sandbox_nova.transcript import TranscriptStore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="nova", description="CompassX Nova agent (sandbox isolation).")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve", help="Run the Nova loop and consume inbox turns.")
    serve.add_argument("--session", dest="session_id", default=os.environ.get("NOVA_SESSION_ID"))
    dump = sub.add_parser("transcript", help="Print transcript JSON for host sync.")
    dump.add_argument("--session", dest="session_id", default=os.environ.get("NOVA_SESSION_ID"))
    args = parser.parse_args(argv)
    settings = NovaSettings.from_env(args.session_id)
    os.makedirs(settings.state_dir, exist_ok=True)
    os.makedirs(settings.inbox_dir, exist_ok=True)
    transcript = TranscriptStore(settings.transcript_path)
    if args.command == "transcript":
        events = [
            {
                "kind": item.get("kind"),
                "content": item.get("content") or "",
                "source_id": item.get("id") or item.get("source_id"),
            }
            for item in transcript.read_all()
            if item.get("kind") in ("thinking", "tool", "reply", "error")
        ]
        print(json.dumps({"activities": events}))
        return 0
    loop = NovaAgentLoop(settings, GatewayLLM(settings), build_default_registry(settings), transcript)
    InboxServer(settings, loop).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
