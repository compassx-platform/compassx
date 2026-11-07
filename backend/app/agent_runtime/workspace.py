"""Read a sandbox worktree and its git changes for an Agent Runtime session."""
from __future__ import annotations

import base64
import json
import re
import shlex
from typing import Any

WORKDIR = "/workspace"
_MAX_ENTRIES = 2000
_MAX_FILE_CHARS = 200_000
_MAX_DIFF_CHARS = 200_000


def safe_relative_path(path: str) -> str:
    raw = (path or "").replace("\\", "/").strip()
    if not raw or raw.startswith("/") or raw.startswith("~"):
        raise ValueError("Path must be relative to the sandbox workspace.")
    parts = [part for part in raw.split("/") if part not in ("", ".")]
    if not parts or any(part == ".." for part in parts):
        raise ValueError("Path escapes the sandbox workspace.")
    return "/".join(parts)


def _python_command(script: str, env: dict[str, str] | None = None) -> str:
    encoded = base64.b64encode(script.encode("utf-8")).decode("ascii")
    prefix = ""
    if env:
        prefix = " ".join(f"{key}={shlex.quote(value)}" for key, value in env.items()) + " "
    return f"{prefix}python3 -c {shlex.quote('import base64,sys; exec(base64.b64decode(sys.argv[1]).decode())')} {shlex.quote(encoded)}"


def files_command() -> str:
    script = f"""
import json, os
root = {WORKDIR!r}
skip = {{".git", "node_modules", "__pycache__", ".venv", "venv"}}
entries = []
if os.path.isdir(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(name for name in dirnames if name not in skip)
        rel_dir = os.path.relpath(dirpath, root).replace("\\\\", "/")
        if rel_dir == ".":
            rel_dir = ""
        for name in dirnames:
            if len(entries) >= {_MAX_ENTRIES}:
                break
            rel = f"{{rel_dir}}/{{name}}" if rel_dir else name
            entries.append({{"path": rel, "type": "dir", "size": 0}})
        for name in sorted(filenames):
            if len(entries) >= {_MAX_ENTRIES}:
                break
            full = os.path.join(dirpath, name)
            rel = f"{{rel_dir}}/{{name}}" if rel_dir else name
            try:
                size = os.path.getsize(full)
            except OSError:
                size = 0
            entries.append({{"path": rel.replace("\\\\", "/"), "type": "file", "size": size}})
print(json.dumps({{"root": root, "entries": entries}}))
"""
    return _python_command(script)


def file_content_command(relative_path: str) -> str:
    rel = safe_relative_path(relative_path)
    script = f"""
import json, os
root = {WORKDIR!r}
rel = os.environ["CX_REL"]
full = os.path.normpath(os.path.join(root, rel))
if not full.startswith(root + os.sep) and full != root:
    raise SystemExit("path escapes workspace")
if not os.path.isfile(full):
    print(json.dumps({{"path": rel, "content": "", "truncated": False, "missing": True}}))
else:
    with open(full, "r", encoding="utf-8", errors="replace") as handle:
        text = handle.read({_MAX_FILE_CHARS} + 1)
    truncated = len(text) > {_MAX_FILE_CHARS}
    print(json.dumps({{"path": rel, "content": text[:{_MAX_FILE_CHARS}], "truncated": truncated, "missing": False}}))
"""
    return _python_command(script, {"CX_REL": rel})


def write_file_command(relative_path: str, content: str) -> str:
    rel = safe_relative_path(relative_path)
    if len(content) > _MAX_FILE_CHARS:
        raise ValueError("File is too large to save from the editor.")
    encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
    script = """
import json, os, base64
root = os.environ["CX_ROOT"]
rel = os.environ["CX_REL"]
full = os.path.normpath(os.path.join(root, rel))
if not (full == root or full.startswith(root + os.sep)):
    raise SystemExit("path escapes workspace")
parent = os.path.dirname(full)
if parent:
    os.makedirs(parent, exist_ok=True)
data = base64.b64decode(os.environ["CX_BODY"])
with open(full, "wb") as handle:
    handle.write(data)
print(json.dumps({"path": rel, "bytes": len(data)}))
"""
    return _python_command(script, {"CX_ROOT": WORKDIR, "CX_REL": rel, "CX_BODY": encoded})


def changes_command() -> str:
    script = f"""
import json, os, subprocess
root = {WORKDIR!r}
entries = []
if not os.path.isdir(root):
    print(json.dumps({{"entries": entries}}))
    raise SystemExit(0)
inside = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=root, capture_output=True, text=True)
if inside.returncode != 0 or inside.stdout.strip() != "true":
    created = subprocess.run(["git", "init", "-b", "main"], cwd=root, capture_output=True, text=True)
    if created.returncode != 0:
        subprocess.run(["git", "init"], cwd=root, capture_output=True, text=True)
status = subprocess.run(["git", "status", "--porcelain", "-uall"], cwd=root, capture_output=True, text=True)
counts = {{}}
for args in (["git", "diff", "--numstat"], ["git", "diff", "--cached", "--numstat"]):
    numstat = subprocess.run(args, cwd=root, capture_output=True, text=True)
    if numstat.returncode != 0:
        continue
    for line in numstat.stdout.splitlines():
        parts = line.split("\\t")
        if len(parts) < 3 or parts[2] in counts:
            continue
        add, delete, path = parts[0], parts[1], parts[2]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        try:
            counts[path] = (int(add), int(delete))
        except ValueError:
            counts[path] = (0, 0)
if status.returncode == 0:
    for raw in status.stdout.splitlines():
        if len(raw) < 4:
            continue
        code = raw[:2]
        path = raw[3:].strip().strip('"')
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if "D" in code:
            label = "deleted"
        elif "?" in code:
            label = "untracked"
        elif "A" in code:
            label = "added"
        elif "R" in code:
            label = "renamed"
        else:
            label = "modified"
        add, delete = counts.get(path, (0, 0))
        if label == "untracked" and add == 0:
            full = os.path.join(root, path)
            try:
                with open(full, "r", encoding="utf-8", errors="replace") as handle:
                    add = sum(1 for _ in handle)
            except OSError:
                add = 0
        staged = code[0] not in (" ", "?")
        unstaged = code == "??" or (len(code) > 1 and code[1] not in (" ",))
        entries.append({{"path": path, "status": label, "additions": add, "deletions": delete, "staged": staged, "unstaged": unstaged}})
branch = subprocess.run(["git", "branch", "--show-current"], cwd=root, capture_output=True, text=True).stdout.strip() or "main"
commits = []
log = subprocess.run(["git", "log", "-n", "40", "--pretty=format:%h%x1f%s%x1f%an%x1f%ad", "--date=short"], cwd=root, capture_output=True, text=True)
if log.returncode == 0 and log.stdout.strip():
    for line in log.stdout.splitlines():
        parts = line.split("\\x1f")
        if len(parts) < 4:
            continue
        commits.append({{"hash": parts[0], "subject": parts[1], "author": parts[2], "date": parts[3]}})
print(json.dumps({{"entries": entries, "branch": branch, "commits": commits}}))
"""
    return _python_command(script)


def diff_command(relative_path: str) -> str:
    rel = safe_relative_path(relative_path)
    script = f"""
import json, os, subprocess
root = {WORKDIR!r}
rel = os.environ["CX_REL"]
full = os.path.normpath(os.path.join(root, rel))
if os.path.isabs(rel) or ".." in rel.split("/"):
    raise SystemExit("invalid path")
diff = subprocess.run(["git", "diff", "--no-color", "--unified=3", "--", rel], cwd=root, capture_output=True, text=True)
text = diff.stdout or ""
if not text.strip():
    untracked = subprocess.run(
        ["git", "diff", "--no-color", "--no-index", "--unified=3", "--", "/dev/null", rel],
        cwd=root, capture_output=True, text=True,
    )
    text = untracked.stdout or ""
if not text.strip() and os.path.isfile(full):
    with open(full, "r", encoding="utf-8", errors="replace") as handle:
        body = handle.read({_MAX_DIFF_CHARS})
    lines = "".join("+" + line for line in body.splitlines(keepends=True))
    text = f"--- /dev/null\\n+++ b/{{rel}}\\n{{lines}}"
text = text[:{_MAX_DIFF_CHARS}]
print(json.dumps({{"path": rel, "diff": text}}))
"""
    return _python_command(script, {"CX_REL": rel})


def patch_command() -> str:
    """One unified diff of everything that is not committed."""
    script = f"""
import json, os, subprocess
root = {WORKDIR!r}
inside = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=root, capture_output=True, text=True)
if inside.returncode != 0 or inside.stdout.strip() != "true":
    created = subprocess.run(["git", "init", "-b", "main"], cwd=root, capture_output=True, text=True)
    if created.returncode != 0:
        subprocess.run(["git", "init"], cwd=root, capture_output=True, text=True)
parts = []
diff = subprocess.run(["git", "diff", "--no-color", "--unified=3", "HEAD"], cwd=root, capture_output=True, text=True)
if diff.returncode != 0:
    diff = subprocess.run(["git", "diff", "--no-color", "--unified=3"], cwd=root, capture_output=True, text=True)
if diff.stdout:
    parts.append(diff.stdout)
status = subprocess.run(["git", "status", "--porcelain", "-uall"], cwd=root, capture_output=True, text=True)
limit = {_MAX_DIFF_CHARS}
used = sum(len(part) for part in parts)
if status.returncode == 0:
    for raw in status.stdout.splitlines():
        if used >= limit or not raw.startswith("??") or len(raw) < 4:
            continue
        rel = raw[3:].strip().strip('"')
        full = os.path.join(root, rel)
        if not os.path.isfile(full):
            continue
        try:
            with open(full, "r", encoding="utf-8", errors="replace") as handle:
                body = handle.read(limit - used)
        except OSError:
            continue
        lines = "".join("+" + line for line in body.splitlines(keepends=True))
        chunk = f"--- /dev/null\\n+++ b/{{rel}}\\n{{lines}}\\n"
        parts.append(chunk)
        used += len(chunk)
text = "".join(parts)[:limit]
print(json.dumps({{"path": "", "diff": text}}))
"""
    return _python_command(script)


def safe_branch_name(branch: str) -> str:
    name = (branch or "").strip()
    if not name or name.startswith("-") or ".." in name.split("/") or not re.fullmatch(r"[A-Za-z0-9._/-]+", name):
        raise ValueError("Branch name is not valid.")
    return name


def git_info_command() -> str:
    script = f"""
import json, subprocess
root = {WORKDIR!r}
def run(args):
    return subprocess.run(["git", "-C", root, *args], capture_output=True, text=True)
inside = run(["rev-parse", "--is-inside-work-tree"])
if inside.returncode != 0 or inside.stdout.strip() != "true":
    created = run(["init", "-b", "main"])
    if created.returncode != 0:
        created = run(["init"])
    inside = run(["rev-parse", "--is-inside-work-tree"])
if inside.returncode != 0 or inside.stdout.strip() != "true":
    print(json.dumps({{"repo": False, "branch": "", "branches": []}}))
else:
    branch = run(["branch", "--show-current"]).stdout.strip()
    names = [line.strip() for line in run(["for-each-ref", "--format=%(refname:short)", "refs/heads"]).stdout.splitlines() if line.strip()]
    print(json.dumps({{"repo": True, "branch": branch, "branches": names}}))
"""
    return _python_command(script)


def checkout_branch_command(branch: str) -> str:
    name = safe_branch_name(branch)
    script = f"""
import subprocess, sys
root = {WORKDIR!r}
branch = {name!r}
result = subprocess.run(["git", "-C", root, "checkout", branch], capture_output=True, text=True)
if result.returncode != 0:
    sys.stderr.write((result.stderr or result.stdout or "checkout failed")[:400])
    raise SystemExit(1)
print(branch)
"""
    return _python_command(script)


def parse_json_stdout(stdout: str) -> dict[str, Any]:
    text = (stdout or "").strip()
    if not text:
        return {}
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("Sandbox did not return workspace JSON.")
    return json.loads(text[start : end + 1])
