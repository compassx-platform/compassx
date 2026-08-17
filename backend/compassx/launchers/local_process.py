"""Local Process Launcher — runs platform services as native OS processes.

Used in the local-dev profile for backend/frontend. PIDs and logs are
kept under .compassx/services/ so `compassx status/down` work across CLI
invocations.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shlex
import shutil
import signal
import subprocess
import sys
import time
from abc import ABC, abstractmethod
from pathlib import Path

from compassx.interfaces.launcher import Launcher, LauncherStatus, ServiceStatus
from compassx.models import LauncherError
from compassx.registry.profile import DeploymentProfile

logger = logging.getLogger(__name__)

_VENV_PYTHON_TOKEN = "{venv_python}"


def _resolve_venv_python(cwd: Path) -> str:
    """Resolve the backend virtualenv Python interpreter for the current OS.

    Mirrors backend/scripts/Get-BackendPython.ps1: prefer BACKEND_VENV_PATH,
    then a repo-local .venv next to the service's cwd, each using the
    OS-appropriate venv layout (Scripts\\python.exe on Windows, bin/python
    on macOS/Linux).
    """
    rel = Path("Scripts/python.exe") if os.name == "nt" else Path("bin/python")
    candidates = []
    venv_path = os.environ.get("BACKEND_VENV_PATH")
    if venv_path:
        candidates.append(Path(venv_path) / rel)
    candidates.append(cwd / ".venv" / rel)
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    raise LauncherError(
        "Could not find a backend Python interpreter. Set BACKEND_VENV_PATH to an "
        f"external venv, or create one at {cwd / '.venv'} (see backend/README.md)."
    )


def _substitute_placeholders(command: list[str], cwd: Path) -> list[str]:
    return [
        _resolve_venv_python(cwd) if token == _VENV_PYTHON_TOKEN else token
        for token in command
    ]


def _resolve_command(command: list[str]) -> list[str]:
    """On Windows, resolve bare executables (npm, node, python) to their
    .cmd/.exe equivalents so Popen(shell=False) works."""
    if os.name != "nt" or not command:
        return command
    exe = command[0].replace("/", "\\")
    command = [exe, *command[1:]]
    # Already has extension or is an absolute path — use as-is.
    if os.path.splitext(exe)[1] or os.path.isabs(exe):
        return command
    # Try .cmd first (npm, npx, yarn, etc.), then .exe, then plain.
    for ext in (".cmd", ".exe", ""):
        resolved = shutil.which(exe + ext)
        if resolved:
            return [resolved] + command[1:]
    return command


def _pid_alive(pid: int) -> bool:
    from compassx.drivers.local import _pid_alive as impl

    return impl(pid)


class VisibleConsoleStrategy(ABC):
    """Opens a service's process in a console window the developer can watch.

    Console mechanics are entirely OS-specific (a new cmd.exe window on
    Windows, a new Terminal.app window on macOS, a terminal emulator on
    Linux, ...). Each OS gets its own strategy implementing this single
    method; `LocalProcessLauncher` only ever talks to the interface. Adding
    a new OS means adding a new strategy class and registering it in
    `_CONSOLE_STRATEGIES` below — nothing in `LocalProcessLauncher` changes.
    """

    @abstractmethod
    def open(self, service: str, cmd: list[str], cwd: Path, state_dir: Path) -> int:
        """Start cmd in a new visible console and return its PID.

        Raises LauncherError if the console could not be opened.
        """

    def close(self, service: str, pid: int, state_dir: Path) -> None:
        """Best-effort cleanup once the service's process has been stopped.

        Called after the process is confirmed dead (or was already dead).
        Default: nothing to do — e.g. on Windows, killing the console's
        owning process already closes the console window for free. Override
        when the OS needs an explicit extra step (see MacTerminalStrategy).
        """


class WindowsConsoleStrategy(VisibleConsoleStrategy):
    """Opens a new cmd.exe console window (CREATE_NEW_CONSOLE)."""

    def open(self, service: str, cmd: list[str], cwd: Path, state_dir: Path) -> int:
        # Keep the console open only while the service is alive. Using /k
        # leaves an idle cmd.exe after a failed child process, which makes
        # status checks incorrectly report the service as running.
        console_cmd = ["cmd", "/c"] + cmd
        try:
            proc = subprocess.Popen(
                console_cmd,
                cwd=str(cwd),
                shell=False,
                creationflags=(
                    subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NEW_CONSOLE
                ),
            )
        except OSError as exc:
            raise LauncherError(
                f"Failed to start '{service}' ({' '.join(cmd)}) in {cwd}: {exc}. "
                f"Is the executable installed and on PATH?"
            ) from exc
        return proc.pid


class MacTerminalStrategy(VisibleConsoleStrategy):
    """Opens a new Terminal.app window via AppleScript.

    The launched shell writes its own PID to a handshake file before
    exec-ing into the real command (exec replaces the shell's process
    image, so the PID stays valid for the service's lifetime — a
    self-reporting daemon script would use the same trick). We poll for
    that handshake file instead of trusting osascript's return value,
    since `do script` only confirms the window opened, not that our
    command started running inside it.

    Unlike Windows (where killing the console's owning process closes the
    console for free), Terminal.app does not auto-close a window just
    because the process inside it died — so we also remember which window
    we opened (its AppleScript `id`) and explicitly close it in `close()`.
    """

    handshake_timeout_seconds = 15.0

    def open(self, service: str, cmd: list[str], cwd: Path, state_dir: Path) -> int:
        handshake = state_dir / f"{service}.handshake"
        handshake.unlink(missing_ok=True)
        try:
            window_id = self._tell_terminal(cmd, cwd, handshake)
        except (OSError, subprocess.CalledProcessError) as exc:
            raise LauncherError(
                f"Failed to open Terminal.app for '{service}' ({' '.join(cmd)}) in "
                f"{cwd}: {exc}. If macOS is blocking automation, grant access under "
                f"System Settings > Privacy & Security > Automation."
            ) from exc
        pid = self._wait_for_handshake(handshake)
        handshake.unlink(missing_ok=True)
        if pid is None:
            raise LauncherError(
                f"Timed out waiting for '{service}' to start in Terminal.app. "
                f"Check System Settings > Privacy & Security > Automation for "
                f"Terminal access, then retry."
            )
        self._save_window_id(service, state_dir, window_id)
        return pid

    def close(self, service: str, pid: int, state_dir: Path) -> None:
        window_id = self._load_window_id(service, state_dir)
        self._window_file(service, state_dir).unlink(missing_ok=True)
        if window_id is None:
            return
        # By the time we get here the process is already dead (the caller
        # waits for that), so Terminal closes the window without popping
        # its "processes are still running" confirmation dialog.
        subprocess.run(
            [
                "osascript",
                "-e",
                f'tell application "Terminal" to close (window id {window_id})',
            ],
            check=False,
            capture_output=True,
            timeout=5,
        )

    @staticmethod
    def _tell_terminal(cmd: list[str], cwd: Path, handshake_path: Path) -> str:
        """Runs cmd in a new Terminal window and returns that window's id."""
        shell_cmd = " ".join(shlex.quote(part) for part in cmd)
        script = (
            f"cd {shlex.quote(str(cwd))} && "
            f"echo $$ > {shlex.quote(str(handshake_path))} && "
            f"exec {shell_cmd}"
        )
        apple_script = (
            'tell application "Terminal"\n'
            "  do script " + json.dumps(script, ensure_ascii=False) + "\n"
            # AppleScript double-quoted strings use the same \" / \\ escaping
            # as JSON; ensure_ascii=False keeps unicode paths literal
            # (AppleScript doesn't support \uXXXX escapes).
            "  return id of front window\n"
            "end tell"
        )
        result = subprocess.run(
            ["osascript", "-e", apple_script],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    @classmethod
    def _wait_for_handshake(cls, handshake_path: Path) -> int | None:
        deadline = time.monotonic() + cls.handshake_timeout_seconds
        while time.monotonic() < deadline:
            if handshake_path.exists():
                try:
                    return int(handshake_path.read_text(encoding="utf-8").strip())
                except ValueError:
                    pass
            time.sleep(0.1)
        return None

    @staticmethod
    def _window_file(service: str, state_dir: Path) -> Path:
        return state_dir / f"{service}.terminal-window"

    @classmethod
    def _save_window_id(cls, service: str, state_dir: Path, window_id: str) -> None:
        cls._window_file(service, state_dir).write_text(window_id, encoding="utf-8")

    @classmethod
    def _load_window_id(cls, service: str, state_dir: Path) -> str | None:
        path = cls._window_file(service, state_dir)
        if not path.exists():
            return None
        text = path.read_text(encoding="utf-8").strip()
        return text or None


# Platform key (sys.platform) -> strategy. A platform with no entry here
# simply has no "windowed" mode; LocalProcessLauncher falls back to running
# the service in the background with output captured to a log file. To add
# Linux support, implement a strategy (e.g. spawning $TERMINAL/gnome-terminal
# with the same handshake-file trick as MacTerminalStrategy) and register it
# under "linux" — LocalProcessLauncher.start() requires no changes.
_CONSOLE_STRATEGIES: dict[str, VisibleConsoleStrategy] = {
    "win32": WindowsConsoleStrategy(),
    "darwin": MacTerminalStrategy(),
}


def _console_strategy() -> VisibleConsoleStrategy | None:
    return _CONSOLE_STRATEGIES.get(sys.platform)


class LocalProcessLauncher(Launcher):
    name = "local"

    def __init__(self, profile: DeploymentProfile, repo_root: Path) -> None:
        self._profile = profile
        self._repo_root = repo_root
        self._state_dir = repo_root / ".compassx" / "services"
        self._state_dir.mkdir(parents=True, exist_ok=True)

    def _pid_file(self, service: str) -> Path:
        return self._state_dir / f"{service}.json"

    def _log_file(self, service: str) -> Path:
        return self._state_dir / f"{service}.log"

    def _read_pid(self, service: str) -> int | None:
        path = self._pid_file(service)
        if not path.exists():
            return None
        try:
            return int(json.loads(path.read_text(encoding="utf-8"))["pid"])
        except (json.JSONDecodeError, KeyError, ValueError):
            return None

    def _record_pid(self, service: str, pid: int, command: list[str]) -> None:
        self._pid_file(service).write_text(
            json.dumps({"pid": pid, "command": command}), encoding="utf-8"
        )

    async def start(self, services: list[str]) -> None:
        for service in services:
            entry = self._profile.services.get(service)
            if entry is None or not entry.command:
                raise LauncherError(
                    f"Service '{service}' has no local command configured in "
                    f"profile '{self._profile.name}'. Add services.{service}.command."
                )
            pid = self._read_pid(service)
            if pid and _pid_alive(pid):
                logger.info("local: %s already running (pid=%s)", service, pid)
                continue
            cwd = self._repo_root / entry.cwd if entry.cwd else self._repo_root
            cmd = _resolve_command(_substitute_placeholders(entry.command, cwd))

            strategy = _console_strategy() if entry.windowed else None
            if strategy is not None:
                pid = strategy.open(service, cmd, cwd, self._state_dir)
                self._record_pid(service, pid, entry.command)
                logger.info(
                    "local: started %s pid=%s (%s)",
                    service,
                    pid,
                    type(strategy).__name__,
                )
                continue

            # No visible-console strategy for this OS (or windowed not
            # requested): run in the background, output captured to a file.
            log_file = open(self._log_file(service), "ab")
            try:
                kwargs: dict = {}
                if os.name == "nt":
                    kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
                else:
                    kwargs["start_new_session"] = True
                proc = subprocess.Popen(
                    cmd,
                    cwd=str(cwd),
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    shell=False,
                    **kwargs,
                )
            except OSError as exc:
                raise LauncherError(
                    f"Failed to start '{service}' ({' '.join(cmd)}) in {cwd}: {exc}. "
                    f"Is the executable installed and on PATH?"
                ) from exc
            finally:
                log_file.close()
            self._record_pid(service, proc.pid, entry.command)
            logger.info("local: started %s pid=%s", service, proc.pid)

    async def stop(self, services: list[str]) -> None:
        from compassx.drivers.local import LocalDriver

        for service in services:
            pid = self._read_pid(service)
            if pid and _pid_alive(pid):
                LocalDriver._terminate(pid)
                await self._await_exit(pid)
                logger.info("local: stopped %s pid=%s", service, pid)

            entry = self._profile.services.get(service)
            strategy = _console_strategy() if entry and entry.windowed else None
            if strategy is not None and pid is not None:
                strategy.close(service, pid, self._state_dir)

            self._pid_file(service).unlink(missing_ok=True)

    @staticmethod
    async def _await_exit(pid: int, timeout: float = 5.0) -> None:
        """Wait for pid to die, escalating to SIGKILL if it ignores SIGTERM.

        Gives a windowed console (e.g. Terminal.app) a clean, already-dead
        process to close against — closing a window Terminal still
        considers "running" pops a confirmation dialog that would otherwise
        block `compassx down` from ever actually closing it.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not _pid_alive(pid):
                return
            await asyncio.sleep(0.1)
        if os.name == "nt" or not _pid_alive(pid):
            return
        try:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
        except OSError:
            return
        # SIGKILL can't be caught or ignored, so this only needs to outrun
        # the kernel actually tearing the process down — a couple seconds
        # is generous, not a real wait for a slow shutdown.
        kill_deadline = time.monotonic() + 2.0
        while time.monotonic() < kill_deadline:
            if not _pid_alive(pid):
                return
            await asyncio.sleep(0.05)

    async def restart(self, services: list[str]) -> None:
        await self.stop(services)
        await self.start(services)

    async def status(self, services: list[str]) -> LauncherStatus:
        statuses = []
        for service in services:
            pid = self._read_pid(service)
            running = bool(pid and _pid_alive(pid))
            statuses.append(
                ServiceStatus(
                    name=service,
                    running=running,
                    detail=f"pid={pid}" if running else "not running",
                )
            )
        return LauncherStatus(launcher=self.name, services=statuses)

    async def logs(self, service: str, tail: int = 200) -> str:
        path = self._log_file(service)
        if not path.exists():
            return ""
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(lines[-tail:])
