"""Local Driver — runs runtimes as native OS processes.

No Docker or Kubernetes dependency. infra_id == PID (as string).
Process metadata (pid, log file, spec) is kept in a state directory so
runtimes survive driver re-instantiation (but not host reboots).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import signal
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator

from compassx.interfaces.driver import ResourceDriver
from compassx.models import (
    ExecResult,
    RuntimeAlreadyExistsError,
    RuntimeInfo,
    RuntimeNotFoundError,
    RuntimePhase,
    RuntimeProvisionError,
    RuntimeSpec,
)

logger = logging.getLogger(__name__)

_DEFAULT_STATE_DIR = Path(".compassx") / "runtimes"


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        # NOTE: os.kill(pid, 0) on Windows calls TerminateProcess — it KILLS
        # the process. Use OpenProcess + GetExitCodeProcess instead.
        import ctypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False
        try:
            exit_code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return False
            return exit_code.value == STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except OSError:
        return False


class LocalDriver(ResourceDriver):
    name = "local"

    def __init__(self, state_dir: Path | str | None = None) -> None:
        self._state_dir = Path(state_dir) if state_dir else _DEFAULT_STATE_DIR
        self._state_dir.mkdir(parents=True, exist_ok=True)

    # ── state helpers ────────────────────────────────────────────────────

    def _runtime_dir(self, runtime_id: str) -> Path:
        return self._state_dir / runtime_id

    def _meta_path(self, runtime_id: str) -> Path:
        return self._runtime_dir(runtime_id) / "meta.json"

    def _log_path(self, runtime_id: str) -> Path:
        return self._runtime_dir(runtime_id) / "runtime.log"

    def _load_meta(self, runtime_id: str) -> dict:
        path = self._meta_path(runtime_id)
        if not path.exists():
            raise RuntimeNotFoundError(f"Local runtime not found: {runtime_id}")
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    def _save_meta(self, runtime_id: str, meta: dict) -> None:
        with open(self._meta_path(runtime_id), "w", encoding="utf-8") as fh:
            json.dump(meta, fh)

    # ── lifecycle ────────────────────────────────────────────────────────

    async def create_runtime(self, spec: RuntimeSpec) -> str:
        rt_dir = self._runtime_dir(spec.runtime_id)
        if self._meta_path(spec.runtime_id).exists():
            raise RuntimeAlreadyExistsError(
                f"Local runtime already exists: {spec.runtime_id}"
            )
        if not spec.command:
            raise RuntimeProvisionError(
                f"Local runtime {spec.runtime_id} requires a command"
            )
        rt_dir.mkdir(parents=True, exist_ok=True)
        meta = {
            "runtime_id": spec.runtime_id,
            "runtime_type": spec.runtime_type,
            "command": list(spec.command) + list(spec.args),
            "cwd": spec.working_dir or None,
            "env": dict(spec.env),
            "labels": dict(spec.labels),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "pid": None,
            "phase": RuntimePhase.CREATING.value,
        }
        self._save_meta(spec.runtime_id, meta)
        pid = self._spawn(spec.runtime_id, meta)
        return str(pid)

    def _spawn(self, runtime_id: str, meta: dict) -> int:
        log_file = open(self._log_path(runtime_id), "ab")
        env = {**os.environ, **(meta.get("env") or {})}
        try:
            kwargs: dict = {}
            if os.name == "nt":
                kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
            else:
                kwargs["start_new_session"] = True
            proc = subprocess.Popen(
                meta["command"],
                cwd=meta.get("cwd") or None,
                env=env,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                **kwargs,
            )
        except (OSError, ValueError) as exc:
            meta["phase"] = RuntimePhase.FAILED.value
            self._save_meta(runtime_id, meta)
            raise RuntimeProvisionError(
                f"Failed to spawn local runtime {runtime_id}: {exc}"
            ) from exc
        finally:
            log_file.close()
        meta["pid"] = proc.pid
        meta["phase"] = RuntimePhase.RUNNING.value
        meta["started_at"] = datetime.now(timezone.utc).isoformat()
        self._save_meta(runtime_id, meta)
        logger.info(
            "Local runtime started: runtime_id=%s pid=%s command=%s",
            runtime_id,
            proc.pid,
            meta["command"],
        )
        return proc.pid

    async def start_runtime(self, runtime_id: str) -> None:
        meta = self._load_meta(runtime_id)
        pid = meta.get("pid")
        if pid and _pid_alive(int(pid)):
            return
        self._spawn(runtime_id, meta)

    async def stop_runtime(self, runtime_id: str) -> None:
        meta = self._load_meta(runtime_id)
        pid = meta.get("pid")
        if pid and _pid_alive(int(pid)):
            self._terminate(int(pid))
        meta["phase"] = RuntimePhase.STOPPED.value
        meta["finished_at"] = datetime.now(timezone.utc).isoformat()
        self._save_meta(runtime_id, meta)
        logger.info("Local runtime stopped: runtime_id=%s pid=%s", runtime_id, pid)

    @staticmethod
    def _terminate(pid: int) -> None:
        try:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(pid), "/T", "/F"],
                    capture_output=True,
                    check=False,
                )
            else:
                os.killpg(os.getpgid(pid), signal.SIGTERM)
        except OSError:
            pass

    async def delete_runtime(self, runtime_id: str) -> None:
        try:
            await self.stop_runtime(runtime_id)
        except RuntimeNotFoundError:
            raise
        shutil.rmtree(self._runtime_dir(runtime_id), ignore_errors=True)
        logger.info("Local runtime deleted: runtime_id=%s", runtime_id)

    # ── inspection ───────────────────────────────────────────────────────

    def _info_from_meta(self, meta: dict) -> RuntimeInfo:
        phase = RuntimePhase(meta.get("phase", RuntimePhase.UNKNOWN.value))
        pid = meta.get("pid")
        if phase == RuntimePhase.RUNNING and pid and not _pid_alive(int(pid)):
            phase = RuntimePhase.STOPPED
        return RuntimeInfo(
            runtime_id=meta["runtime_id"],
            runtime_type=meta.get("runtime_type", ""),
            phase=phase,
            infra_id=str(pid) if pid else "",
            created_at=_parse_dt(meta.get("created_at")),
            started_at=_parse_dt(meta.get("started_at")),
            finished_at=_parse_dt(meta.get("finished_at")),
            labels=meta.get("labels") or {},
        )

    async def get_status(self, runtime_id: str) -> RuntimeInfo:
        return self._info_from_meta(self._load_meta(runtime_id))

    async def list_runtimes(self) -> list[RuntimeInfo]:
        infos = []
        for meta_path in self._state_dir.glob("*/meta.json"):
            try:
                with open(meta_path, "r", encoding="utf-8") as fh:
                    infos.append(self._info_from_meta(json.load(fh)))
            except (json.JSONDecodeError, KeyError, ValueError):
                continue
        return infos

    # ── interaction ──────────────────────────────────────────────────────

    async def exec(self, runtime_id: str, command: list[str]) -> ExecResult:
        # Local runtimes are plain processes; exec runs in the same cwd/env.
        meta = self._load_meta(runtime_id)
        env = {**os.environ, **(meta.get("env") or {})}
        proc = await asyncio.create_subprocess_exec(
            *command,
            cwd=meta.get("cwd") or None,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return ExecResult(
            exit_code=proc.returncode or 0,
            stdout=stdout.decode("utf-8", errors="replace"),
            stderr=stderr.decode("utf-8", errors="replace"),
        )

    async def logs(self, runtime_id: str, tail: int | None = None) -> str:
        self._load_meta(runtime_id)  # existence check
        path = self._log_path(runtime_id)
        if not path.exists():
            return ""
        text = path.read_text(encoding="utf-8", errors="replace")
        if tail is not None:
            return "\n".join(text.splitlines()[-tail:])
        return text

    async def stream_logs(self, runtime_id: str) -> AsyncIterator[str]:
        meta = self._load_meta(runtime_id)
        path = self._log_path(runtime_id)
        pos = 0
        while True:
            if path.exists():
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    fh.seek(pos)
                    for line in fh:
                        stripped = line.rstrip("\n")
                        if stripped:
                            yield stripped
                    pos = fh.tell()
            pid = meta.get("pid")
            if not (pid and _pid_alive(int(pid))):
                break
            await asyncio.sleep(0.5)

    async def copy_file(
        self, runtime_id: str, src_path: str, dest_path: str, to_runtime: bool = True
    ) -> None:
        # Local runtime shares the host filesystem — a plain copy.
        self._load_meta(runtime_id)
        shutil.copy2(src_path, dest_path)


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
