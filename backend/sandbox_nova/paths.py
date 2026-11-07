"""Keep local file tools inside the sandbox workspace."""

from __future__ import annotations

import os


def resolve_workspace_path(root: str, raw: str) -> str:
    relative = (raw or "").strip() or "."
    if os.path.isabs(relative):
        candidate = os.path.abspath(relative)
    else:
        candidate = os.path.abspath(os.path.join(root, relative))
    root_abs = os.path.abspath(root)
    if candidate != root_abs and not candidate.startswith(root_abs + os.sep):
        raise ValueError("Path is outside the sandbox workspace.")
    return candidate
