"""Workspace file listing, reading, writing, and diffs.

Depends on a workspace layout and the sandbox command port. It does not
start pods or talk to a concrete Docker or Kubernetes driver.
"""
from __future__ import annotations

import base64
import difflib
import json
import logging
import os
import shlex
import subprocess
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.services.app_runner import app_runner_service
from app.services.studio.sandbox_commands import build_sandbox_commands
from app.services.omnigent_dev_service import (
    _clean_id,
    git_status_from_porcelain,
    include_git_only_files,
    safe_repo_path,
)

logger = logging.getLogger(__name__)


class WorkspaceFileService:
    """Read and write the sandbox worktree and its git status."""

    def __init__(self, layout: Any):
        self._layout = layout

    def _exec(self, app, command: str, workspace_folder: str = "", timeout: int = 30):
        return build_sandbox_commands.run(
            app,
            command,
            workspace_folder=workspace_folder,
            timeout=timeout,
        )

    def _sandbox_running(self, app) -> bool:
        try:
            result = self._exec(app, "echo '__RUNNING__'", timeout=8)
        except Exception:
            return False
        return "__RUNNING__" in ((result or {}).get("output") or "")

    def list_workspace_files(self, app, workspace_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List source code files in the specified app sandbox workspace."""
        if self._sandbox_running(app):
            try:
                target_dir = self._layout.ensure_workspace_worktree(app, workspace_id)
                ws_id, ws_name, folder_path, _ = self._layout._resolve_workspace_info(app, workspace_id)
                clean_app_id = _clean_id(app.id)
                py_code = f"""
import os, json, subprocess
root_dir = '{target_dir}'
if not os.path.exists(root_dir) or not os.path.isdir(root_dir) or not any(f for f in os.listdir(root_dir) if f != '.git'):
    candidates = [
        '{target_dir}',
        '/workspaces/{clean_app_id}/{ws_name}',
        '/workspaces/{clean_app_id}/default',
        '/workspaces/{clean_app_id}/main',
        '/workspaces/{clean_app_id}',
        '/workspaces/default',
        '/workspace/app',
        '/workspaces/app',
        '/workspace/default',
        '/workspace/main',
        '/workspace',
        '/app',
    ]
    for base in ['/workspaces', '/workspace']:
        if os.path.exists(base) and os.path.isdir(base):
            try:
                for sub in sorted(os.listdir(base)):
                    p = os.path.join(base, sub)
                    if os.path.isdir(p) and any(f for f in os.listdir(p) if f != '.git'):
                        candidates.append(p)
                        try:
                            for sub2 in sorted(os.listdir(p)):
                                p2 = os.path.join(p, sub2)
                                if os.path.isdir(p2) and any(f for f in os.listdir(p2) if f != '.git'):
                                    candidates.append(p2)
                        except Exception: pass
            except Exception: pass
    for c in candidates:
        if os.path.exists(c) and os.path.isdir(c) and any(f for f in os.listdir(c) if f != '.git'):
            root_dir = c
            break
if not os.path.exists(root_dir):
    root_dir = '/workspaces' if os.path.exists('/workspaces') else '/workspace'

git_statuses = {{}}
try:
    p = subprocess.run(
        ['git', 'status', '--porcelain', '-uall'],
        cwd=root_dir,
        capture_output=True,
        text=True,
        timeout=1.5
    )
    if p.returncode == 0 and p.stdout:
        for raw in p.stdout.splitlines():
            if not raw or raw.startswith('##') or len(raw) < 4:
                continue
            code = raw[:2]
            rest = raw[3:] if raw[2] == ' ' else raw[2:]
            if ' -> ' in rest:
                rest = rest.split(' -> ', 1)[1]
            fpath = rest.strip().strip('"').replace('\\\\', '/')
            if not fpath:
                continue
            if '?' in code:
                st_label = 'untracked'
            elif 'D' in code:
                st_label = 'deleted'
            elif 'A' in code or 'R' in code or 'C' in code:
                st_label = 'added'
            else:
                st_label = 'modified'
            git_statuses[fpath] = st_label
except Exception:
    pass

ign = {{'.git', 'node_modules', '__pycache__', '.venv', '.pytest_cache', '.DS_Store', '.mypy_cache', '.coverage'}}
res = []
for r, dirs, files in os.walk(root_dir):
    dirs[:] = [d for d in dirs if d not in ign]
    for f in files:
        if f in ign: continue
        p = os.path.join(r, f)
        try:
            st = os.stat(p)
            sz = st.st_size
            mt = int(st.st_mtime * 1000)
            rel = os.path.relpath(p, root_dir).replace('\\\\', '/')
            ext = f.split('.')[-1] if '.' in f else ''
            git_st = git_statuses.get(rel)
            res.append({{'path': rel, 'name': f, 'size': sz, 'bytes': sz, 'ext': ext, 'modified_at': mt, 'git_status': git_st}})
        except Exception: pass
seen = set(item['path'] for item in res)
for fpath, st_label in git_statuses.items():
    if fpath in seen:
        continue
    name = fpath.replace('\\\\', '/').rstrip('/').split('/')[-1] or fpath
    ext = name.rsplit('.', 1)[-1] if '.' in name and not name.startswith('.') else ''
    res.append({{'path': fpath, 'name': name, 'size': 0, 'bytes': 0, 'ext': ext, 'modified_at': None, 'git_status': st_label}})
print('__JSON_START__' + json.dumps(res) + '__JSON_END__')
"""
                b64_code = base64.b64encode(py_code.encode("utf-8")).decode("ascii")
                exec_res = self._exec(app, command=f"echo '{b64_code}' | base64 -d | python3", workspace_folder=folder_path)
                out = exec_res.get("output") or ""
                if "__JSON_START__" in out and "__JSON_END__" in out:
                    raw_json = out.split("__JSON_START__", 1)[1].split("__JSON_END__", 1)[0]
                    file_tree = json.loads(raw_json)
                    return sorted(file_tree, key=lambda x: x["path"])
            except Exception as e:
                logger.warning("Failed listing container files for app %s ws %s: %s", app.id, workspace_id, e)

        # Fallback to host repository
        repo_dir = self._layout.get_repo_dir(app)
        ws_id, ws_name, folder_path, _ = self._layout._resolve_workspace_info(app, workspace_id)
        if ws_name and ws_name != "default":
            ws_host_dir = os.path.join(app_runner_service.get_app_dir(app.id), "workspaces", ws_name)
            if os.path.exists(ws_host_dir):
                repo_dir = ws_host_dir

        git_statuses = {}
        try:
            p = subprocess.run(
                ['git', 'status', '--porcelain', '-uall'],
                cwd=repo_dir,
                capture_output=True,
                text=True,
                timeout=1.5
            )
            if p.returncode == 0:
                git_statuses = git_status_from_porcelain(p.stdout or "")
        except Exception:
            pass

        file_tree = []
        ignored = {".git", "node_modules", "__pycache__", ".venv", ".pytest_cache", ".DS_Store"}

        for root, dirs, files in os.walk(repo_dir):
            dirs[:] = [d for d in dirs if d not in ignored]
            for file in files:
                if file in ignored:
                    continue
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, repo_dir).replace("\\", "/")
                try:
                    stat = os.stat(full_path)
                    size = stat.st_size
                    mtime = int(stat.st_mtime * 1000)
                except Exception:
                    size = 0
                    mtime = 0
                file_tree.append({
                    "path": rel_path,
                    "name": file,
                    "size": size,
                    "bytes": size,
                    "ext": os.path.splitext(file)[1].lstrip("."),
                    "modified_at": mtime,
                    "git_status": git_statuses.get(rel_path),
                })

        return sorted(include_git_only_files(file_tree, git_statuses), key=lambda x: x["path"])

    def read_workspace_file(self, app, file_path: str, workspace_id: Optional[str] = None) -> Dict[str, Any]:
        """Read text content of a workspace file."""
        self._layout.touch_workspace_activity(app.id)
        clean_rel = file_path.lstrip("/\\")

        if self._sandbox_running(app):
            try:
                target_dir = self._layout.ensure_workspace_worktree(app, workspace_id)
                ws_id, ws_name, folder_path, _ = self._layout._resolve_workspace_info(app, workspace_id)
                clean_app_id = _clean_id(app.id)
                py_code = f"""
import os, base64
root_dir = '{target_dir}'
if not os.path.exists(root_dir) or not os.path.isdir(root_dir) or not any(f for f in os.listdir(root_dir) if f != '.git'):
    candidates = [
        '{target_dir}',
        '/workspaces/{clean_app_id}/{ws_name}',
        '/workspaces/{clean_app_id}/default',
        '/workspaces/{clean_app_id}/main',
        '/workspaces/{clean_app_id}',
        '/workspaces/default',
        '/workspace/app',
        '/workspaces/app',
        '/workspace/default',
        '/workspace/main',
        '/workspace',
        '/app',
    ]
    for base in ['/workspaces', '/workspace']:
        if os.path.exists(base) and os.path.isdir(base):
            try:
                for sub in sorted(os.listdir(base)):
                    p = os.path.join(base, sub)
                    if os.path.isdir(p) and any(f for f in os.listdir(p) if f != '.git'):
                        candidates.append(p)
                        try:
                            for sub2 in sorted(os.listdir(p)):
                                p2 = os.path.join(p, sub2)
                                if os.path.isdir(p2) and any(f for f in os.listdir(p2) if f != '.git'):
                                    candidates.append(p2)
                        except Exception: pass
            except Exception: pass
    for c in candidates:
        if os.path.exists(c) and os.path.isdir(c) and any(f for f in os.listdir(c) if f != '.git'):
            root_dir = c
            break

p = os.path.normpath(os.path.join(root_dir, '{clean_rel}'))
if not p.startswith(root_dir) or not os.path.exists(p) or not os.path.isfile(p):
    print('__NOT_FOUND__')
else:
    with open(p, 'rb') as f:
        print('__FILE_B64__' + base64.b64encode(f.read()).decode('ascii') + '__FILE_END__')
"""
                b64_code = base64.b64encode(py_code.encode("utf-8")).decode("ascii")
                exec_res = self._exec(app, command=f"echo {b64_code} | base64 -d | python3")
                out = exec_res.get("output") or ""
                if "__NOT_FOUND__" in out:
                    raise FileNotFoundError(f"File '{file_path}' not found in workspace.")
                if "__FILE_B64__" in out and "__FILE_END__" in out:
                    b64_str = out.split("__FILE_B64__", 1)[1].split("__FILE_END__", 1)[0].strip()
                    content_bytes = base64.b64decode(b64_str)
                    content = content_bytes.decode("utf-8", errors="replace")
                    return {
                        "path": file_path,
                        "content": content,
                        "size": len(content),
                        "ext": os.path.splitext(file_path)[1].lstrip("."),
                    }
            except FileNotFoundError:
                raise
            except Exception as e:
                logger.warning("Failed reading file from container for %s: %s", file_path, e)

        # Fallback to host repository
        repo_dir = self._layout.get_repo_dir(app)
        ws_id, ws_name, folder_path, _ = self._layout._resolve_workspace_info(app, workspace_id)
        if ws_name and ws_name != "default":
            ws_host_dir = os.path.join(app_runner_service.get_app_dir(app.id), "workspaces", ws_name)
            if os.path.exists(ws_host_dir):
                repo_dir = ws_host_dir

        safe_path = os.path.normpath(os.path.join(repo_dir, clean_rel))
        if not safe_path.startswith(repo_dir) or not os.path.exists(safe_path) or not os.path.isfile(safe_path):
            raise FileNotFoundError(f"File '{file_path}' not found in app repository.")

        with open(safe_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        return {
            "path": file_path,
            "content": content,
            "size": len(content),
            "ext": os.path.splitext(file_path)[1].lstrip("."),
        }

    def _git_diff_text(self, repo_dir: str, rel_path: str) -> str:
        """Unified diff of the worktree against HEAD. New files are compared with an empty file."""
        tracked = subprocess.run(
            ["git", "cat-file", "-e", f"HEAD:{rel_path}"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if tracked.returncode == 0:
            cmd = ["git", "diff", "--no-color", "--unified=3", "HEAD", "--", rel_path]
        else:
            cmd = ["git", "diff", "--no-color", "--unified=3", "--no-index", "--", os.devnull, rel_path]
        result = subprocess.run(cmd, cwd=repo_dir, capture_output=True, text=True, timeout=8)
        return (result.stdout or "")[:200000]

    def diff_workspace_file(self, app, file_path: str, workspace_id: Optional[str] = None) -> Dict[str, Any]:
        """Return the git unified diff for one sandbox file."""
        rel_path = safe_repo_path(file_path)
        quoted = shlex.quote(rel_path)
        _, _, folder_path, _ = self._layout._resolve_workspace_info(app, workspace_id)
        folder = shlex.quote(folder_path.strip("/"))
        script = (
            "set +e; "
            f"for d in /workspaces/{folder} /workspace /app; do "
            "  if [ -d \"$d\" ]; then cd \"$d\" && break; fi; "
            "done; "
            f"if git cat-file -e HEAD:{quoted} >/dev/null 2>&1; then "
            f"  git diff --no-color --unified=3 HEAD -- {quoted}; "
            "else "
            f"  git diff --no-color --unified=3 --no-index -- /dev/null {quoted}; "
            "fi; "
            "echo __DIFF_END__"
        )
        patch = ""
        try:
            exec_res = self._exec(app, command=script, workspace_folder=folder_path.strip("/"), timeout=15)
            out = (exec_res or {}).get("output") or ""
            if "__DIFF_END__" in out:
                patch = out.split("__DIFF_END__", 1)[0]
        except Exception as exc:
            logger.debug("Sandbox diff exec failed for %s: %s", rel_path, exc)

        if not patch.strip():
            repo_dir = self._layout.get_repo_dir(app)
            _, ws_name, _, _ = self._layout._resolve_workspace_info(app, workspace_id)
            if ws_name and ws_name != "default":
                ws_host_dir = os.path.join(app_runner_service.get_app_dir(app.id), "workspaces", ws_name)
                if os.path.exists(ws_host_dir):
                    repo_dir = ws_host_dir
            try:
                patch = self._git_diff_text(repo_dir, rel_path)
            except Exception as exc:
                logger.debug("Host diff failed for %s: %s", rel_path, exc)
                patch = ""

        return {"path": rel_path, "patch": patch.strip()[:200000]}

    def write_workspace_file(self, app, file_path: str, content: str, workspace_id: Optional[str] = None) -> Dict[str, Any]:
        """Write content to a file in the workspace (triggering hot reload)."""
        self._layout.touch_workspace_activity(app.id)
        clean_rel = file_path.lstrip("/\\")

        if self._sandbox_running(app):
            try:
                target_dir = self._layout.ensure_workspace_worktree(app, workspace_id)
                ws_id, ws_name, folder_path, _ = self._layout._resolve_workspace_info(app, workspace_id)
                clean_app_id = _clean_id(app.id)
                content_bytes = content.encode("utf-8")
                b64_content = base64.b64encode(content_bytes).decode("ascii")
                py_code = f"""
import os, base64
root_dir = '{target_dir}'
if not os.path.exists(root_dir) or not os.path.isdir(root_dir) or not any(f for f in os.listdir(root_dir) if f != '.git'):
    candidates = [
        '{target_dir}',
        '/workspaces/{clean_app_id}/{ws_name}',
        '/workspaces/{clean_app_id}/default',
        '/workspaces/{clean_app_id}/main',
        '/workspaces/{clean_app_id}',
        '/workspaces/default',
        '/workspace/app',
        '/workspaces/app',
        '/workspace/default',
        '/workspace/main',
        '/workspace',
        '/app',
    ]
    for base in ['/workspaces', '/workspace']:
        if os.path.exists(base) and os.path.isdir(base):
            try:
                for sub in sorted(os.listdir(base)):
                    p = os.path.join(base, sub)
                    if os.path.isdir(p) and any(f for f in os.listdir(p) if f != '.git'):
                        candidates.append(p)
                        try:
                            for sub2 in sorted(os.listdir(p)):
                                p2 = os.path.join(p, sub2)
                                if os.path.isdir(p2) and any(f for f in os.listdir(p2) if f != '.git'):
                                    candidates.append(p2)
                        except Exception: pass
            except Exception: pass
    for c in candidates:
        if os.path.exists(c) and os.path.isdir(c) and any(f for f in os.listdir(c) if f != '.git'):
            root_dir = c
            break

p = os.path.normpath(os.path.join(root_dir, '{clean_rel}'))
if not p.startswith(root_dir):
    print('__ERROR_PATH__')
else:
    old = ''
    if os.path.exists(p):
        with open(p, 'rb') as f: old = base64.b64encode(f.read()).decode('ascii')
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'wb') as f: f.write(base64.b64decode('{b64_content}'))
    print('__SAVED__' + old + '__OLD_END__')
"""
                b64_code = base64.b64encode(py_code.encode("utf-8")).decode("ascii")
                exec_res = self._exec(app, command=f"echo {b64_code} | base64 -d | python3")
                out = exec_res.get("output") or ""
                if "__ERROR_PATH__" in out:
                    raise ValueError("Invalid file path outside workspace root.")
                if "__SAVED__" in out:
                    old_b64 = out.split("__SAVED__", 1)[1].split("__OLD_END__", 1)[0].strip()
                    old_content = base64.b64decode(old_b64).decode("utf-8", errors="replace") if old_b64 else ""
                    diff = "".join(difflib.unified_diff(
                        old_content.splitlines(keepends=True),
                        content.splitlines(keepends=True),
                        fromfile=f"a/{file_path}",
                        tofile=f"b/{file_path}",
                    ))
                    return {
                        "path": file_path,
                        "diff": diff,
                        "saved": True,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
            except ValueError:
                raise
            except Exception as e:
                logger.warning("Failed writing file to container for %s: %s", file_path, e)

        # Fallback to host repository
        repo_dir = self._layout.get_repo_dir(app)
        ws_id, ws_name, folder_path, _ = self._layout._resolve_workspace_info(app, workspace_id)
        if ws_name and ws_name != "default":
            ws_host_dir = os.path.join(app_runner_service.get_app_dir(app.id), "workspaces", ws_name)
            if os.path.exists(ws_host_dir):
                repo_dir = ws_host_dir

        safe_path = os.path.normpath(os.path.join(repo_dir, clean_rel))
        if not safe_path.startswith(repo_dir):
            raise ValueError("Invalid file path outside workspace root.")

        os.makedirs(os.path.dirname(safe_path), exist_ok=True)
        old_content = ""
        if os.path.exists(safe_path):
            with open(safe_path, "r", encoding="utf-8", errors="replace") as f:
                old_content = f.read()

        with open(safe_path, "w", encoding="utf-8") as f:
            f.write(content)

        diff = "".join(difflib.unified_diff(
            old_content.splitlines(keepends=True),
            content.splitlines(keepends=True),
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
        ))

        return {
            "path": file_path,
            "diff": diff,
            "saved": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

_file_service = None


def get_workspace_file_service():
    """File service bound to the Build workspace layout."""
    global _file_service
    if _file_service is None:
        from app.services.omnigent_dev_service import omnigent_dev_service
        _file_service = WorkspaceFileService(omnigent_dev_service)
    return _file_service
