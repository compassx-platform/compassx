import os
import sys
import threading

import pytest

from compassx.launchers.local_process import (
    LocalProcessLauncher,
    MacTerminalStrategy,
    VisibleConsoleStrategy,
    WindowsConsoleStrategy,
    _CONSOLE_STRATEGIES,
    _console_strategy,
    _resolve_venv_python,
    _substitute_placeholders,
)
from compassx.models import LauncherError
from compassx.registry.profile import _parse_profile


@pytest.fixture(autouse=True)
def _clear_venv_env(monkeypatch):
    monkeypatch.delenv("BACKEND_VENV_PATH", raising=False)


def _reap_in_background(pid: int) -> None:
    """Reap pid as soon as it exits, from a background thread.

    Tests that spawn a real child and then stop it are, unlike a real
    `compassx` CLI invocation, still the child's actual parent — so without
    this the child sits as a zombie (os.kill(pid, 0) keeps "succeeding")
    until something calls waitpid on it, which would make _pid_alive lie.
    """
    threading.Thread(target=os.waitpid, args=(pid, 0), daemon=True).start()


def _make_venv(root, layout="bin/python"):
    py = root / ".venv" / layout
    py.parent.mkdir(parents=True, exist_ok=True)
    py.touch()
    return py


class TestResolveVenvPython:
    def test_prefers_backend_venv_path(self, tmp_path, monkeypatch):
        external = tmp_path / "external-venv"
        rel = "Scripts/python.exe" if os.name == "nt" else "bin/python"
        (external / rel).parent.mkdir(parents=True, exist_ok=True)
        (external / rel).touch()
        monkeypatch.setenv("BACKEND_VENV_PATH", str(external))
        # Repo-local venv also exists, but BACKEND_VENV_PATH must win.
        _make_venv(tmp_path, rel)

        resolved = _resolve_venv_python(tmp_path)
        assert resolved == str(external / rel)

    def test_falls_back_to_repo_local_venv(self, tmp_path):
        rel = "Scripts/python.exe" if os.name == "nt" else "bin/python"
        expected = _make_venv(tmp_path, rel)

        assert _resolve_venv_python(tmp_path) == str(expected)

    def test_raises_clear_error_when_no_venv_found(self, tmp_path):
        with pytest.raises(LauncherError, match="backend/README.md"):
            _resolve_venv_python(tmp_path)


class TestSubstitutePlaceholders:
    def test_passthrough_tokens_untouched(self, tmp_path):
        # No venv exists — if this touched non-placeholder tokens it would
        # try (and fail) to resolve them as a venv path.
        assert _substitute_placeholders(["npm", "run", "dev"], tmp_path) == [
            "npm",
            "run",
            "dev",
        ]

    def test_replaces_only_the_venv_token(self, tmp_path):
        rel = "Scripts/python.exe" if os.name == "nt" else "bin/python"
        expected = _make_venv(tmp_path, rel)

        assert _substitute_placeholders(["{venv_python}", "app.py"], tmp_path) == [
            str(expected),
            "app.py",
        ]


class TestConsoleStrategyRegistry:
    """These tests exist to pin down the OCP contract: LocalProcessLauncher
    never branches on the OS itself — it only asks the registry for a
    strategy. Adding Linux support later means adding one entry here, not
    touching LocalProcessLauncher.start().
    """

    def test_windows_and_macos_are_registered(self):
        assert isinstance(_CONSOLE_STRATEGIES["win32"], WindowsConsoleStrategy)
        assert isinstance(_CONSOLE_STRATEGIES["darwin"], MacTerminalStrategy)

    def test_linux_has_no_strategy_yet(self):
        # Today: no windowed console on Linux -> LocalProcessLauncher falls
        # back to background+logfile automatically. This is expected to
        # change once a LinuxTerminalStrategy is registered.
        assert "linux" not in _CONSOLE_STRATEGIES

    def test_console_strategy_selects_by_current_platform(self, monkeypatch):
        monkeypatch.setattr(sys, "platform", "darwin")
        assert isinstance(_console_strategy(), MacTerminalStrategy)

        monkeypatch.setattr(sys, "platform", "win32")
        assert isinstance(_console_strategy(), WindowsConsoleStrategy)

        monkeypatch.setattr(sys, "platform", "linux")
        assert _console_strategy() is None

    def test_new_platform_strategy_is_pluggable(self, monkeypatch):
        """Simulates adding Linux support: a new strategy class registered
        under its platform key, with zero changes to LocalProcessLauncher.
        """

        class FakeLinuxStrategy(VisibleConsoleStrategy):
            def open(self, service, cmd, cwd, state_dir):
                return 4242

        monkeypatch.setitem(_CONSOLE_STRATEGIES, "linux", FakeLinuxStrategy())
        monkeypatch.setattr(sys, "platform", "linux")

        strategy = _console_strategy()
        assert isinstance(strategy, FakeLinuxStrategy)
        assert strategy.open("backend", ["true"], cwd=None, state_dir=None) == 4242


class TestLocalProcessLauncherBackgroundLifecycle:
    """End-to-end for the non-windowed (background + logfile) path, which is
    what Linux uses today and what macOS/Windows use when windowed=false.
    """

    @pytest.fixture
    def profile(self):
        return _parse_profile(
            "test-local",
            {
                "profile": "test-local",
                "services": {
                    "worker": {
                        "mode": "local",
                        "command": [sys.executable, "-c", "import time; time.sleep(60)"],
                        "cwd": "",
                        "windowed": False,
                    }
                },
            },
        )

    @pytest.fixture
    def launcher(self, profile, tmp_path):
        return LocalProcessLauncher(profile, repo_root=tmp_path)

    async def test_start_status_stop(self, launcher):
        await launcher.start(["worker"])
        status = await launcher.status(["worker"])
        assert status.services[0].running is True

        # We (the test process) are this child's real parent, so nothing
        # reaps it once it exits until we do — a real `compassx` CLI process
        # never hits this because it exits right after `up`, at which point
        # the child is reparented to launchd/init, which reaps it for free.
        # Without this, _pid_alive would see a zombie and report "alive"
        # for the launcher's whole SIGTERM grace window.
        _reap_in_background(launcher._read_pid("worker"))

        await launcher.stop(["worker"])
        status = await launcher.status(["worker"])
        assert status.services[0].running is False

    async def test_missing_command_raises(self, tmp_path):
        profile = _parse_profile(
            "test-local-nocmd",
            {"profile": "test-local-nocmd", "services": {"worker": {"mode": "local"}}},
        )
        launcher = LocalProcessLauncher(profile, repo_root=tmp_path)
        with pytest.raises(LauncherError):
            await launcher.start(["worker"])


class TestMacTerminalStrategyWindowClose:
    """MacTerminalStrategy.close() is what actually fixes 'compassx down
    doesn't close the Terminal window' — Terminal.app, unlike Windows'
    console host, does not close a window just because the process it was
    running has died, so we have to tell it to explicitly.
    """

    def test_close_is_noop_without_a_recorded_window(self, tmp_path):
        strategy = MacTerminalStrategy()
        # No .terminal-window file was ever written for this service — must
        # not raise, must not shell out.
        strategy.close("backend", pid=123, state_dir=tmp_path)

    def test_close_reads_and_clears_the_window_file(self, tmp_path, monkeypatch):
        strategy = MacTerminalStrategy()
        strategy._save_window_id("backend", tmp_path, "26146")

        calls = []
        monkeypatch.setattr(
            "subprocess.run", lambda *a, **k: calls.append((a, k))
        )

        strategy.close("backend", pid=123, state_dir=tmp_path)

        assert len(calls) == 1
        args = calls[0][0][0]
        assert args[0] == "osascript"
        assert "window id 26146" in args[2]
        assert not strategy._window_file("backend", tmp_path).exists()

    def test_open_persists_the_window_id_returned_by_osascript(
        self, tmp_path, monkeypatch
    ):
        strategy = MacTerminalStrategy()
        state_dir = tmp_path
        handshake = state_dir / "backend.handshake"

        def fake_run(cmd, **kwargs):
            handshake.write_text("999", encoding="utf-8")
            return type(
                "R", (), {"stdout": "12345\n", "returncode": 0, "stderr": ""}
            )()

        monkeypatch.setattr("subprocess.run", fake_run)

        pid = strategy.open("backend", ["true"], cwd=tmp_path, state_dir=state_dir)

        assert pid == 999
        assert strategy._load_window_id("backend", state_dir) == "12345"


class TestLocalProcessLauncherWindowedLifecycle:
    """Confirms LocalProcessLauncher wires strategy.open()/close() correctly
    for a windowed service: start() calls open() and stop() calls close()
    with the pid it tracked, only once the process is actually dead.
    """

    class RecordingStrategy(VisibleConsoleStrategy):
        def __init__(self, pid: int):
            self._pid = pid
            self.open_calls = []
            self.close_calls = []

        def open(self, service, cmd, cwd, state_dir):
            self.open_calls.append((service, cmd, cwd))
            return self._pid

        def close(self, service, pid, state_dir):
            self.close_calls.append((service, pid))

    @pytest.fixture
    def profile(self):
        return _parse_profile(
            "test-windowed",
            {
                "profile": "test-windowed",
                "services": {
                    "worker": {
                        "mode": "local",
                        "command": [sys.executable, "-c", "import time; time.sleep(60)"],
                        "cwd": "",
                        "windowed": True,
                    }
                },
            },
        )

    async def test_start_uses_strategy_and_stop_closes_it(
        self, profile, tmp_path, monkeypatch
    ):
        launcher = LocalProcessLauncher(profile, repo_root=tmp_path)

        # Real long-running process so status()/stop()'s pid-liveness checks
        # (and the SIGTERM-then-wait dance) exercise real behavior; only the
        # "open a console window" part is faked.
        import subprocess as sp

        # start_new_session=True matters here, not just for hygiene: it's
        # what LocalProcessLauncher's own background path uses too, and
        # LocalDriver._terminate() sends SIGTERM via os.killpg() — without
        # a dedicated process group this would signal *this test process's*
        # entire group instead of just real_proc.
        real_proc = sp.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            start_new_session=True,
        )
        threading.Thread(target=real_proc.wait, daemon=True).start()
        strategy = self.RecordingStrategy(pid=real_proc.pid)
        monkeypatch.setattr(
            "compassx.launchers.local_process._console_strategy", lambda: strategy
        )

        await launcher.start(["worker"])
        assert strategy.open_calls and strategy.open_calls[0][0] == "worker"

        await launcher.stop(["worker"])
        assert strategy.close_calls == [("worker", real_proc.pid)]
        real_proc.wait(timeout=5)

    async def test_close_not_called_for_non_windowed_service(self, tmp_path, monkeypatch):
        profile = _parse_profile(
            "test-background",
            {
                "profile": "test-background",
                "services": {
                    "worker": {
                        "mode": "local",
                        "command": [sys.executable, "-c", "import time; time.sleep(60)"],
                        "cwd": "",
                        "windowed": False,
                    }
                },
            },
        )
        launcher = LocalProcessLauncher(profile, repo_root=tmp_path)
        strategy = self.RecordingStrategy(pid=-1)
        monkeypatch.setattr(
            "compassx.launchers.local_process._console_strategy", lambda: strategy
        )

        await launcher.start(["worker"])
        _reap_in_background(launcher._read_pid("worker"))
        await launcher.stop(["worker"])

        assert strategy.close_calls == []


class TestAwaitExit:
    async def test_returns_once_process_exits(self):
        import subprocess as sp

        from compassx.launchers.local_process import LocalProcessLauncher

        proc = sp.Popen([sys.executable, "-c", "pass"])
        proc.wait()
        # Already dead — should return immediately, well under the timeout.
        await LocalProcessLauncher._await_exit(proc.pid, timeout=5.0)

    async def test_escalates_to_sigkill_when_process_ignores_sigterm(self):
        import signal as sig
        import subprocess as sp

        from compassx.launchers.local_process import LocalProcessLauncher, _pid_alive

        proc = sp.Popen(
            [
                sys.executable,
                "-c",
                "import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(30)",
            ],
            start_new_session=True,
        )
        threading.Thread(target=proc.wait, daemon=True).start()
        try:
            # Give the child a moment to install its SIGTERM handler.
            import time as _time

            _time.sleep(0.3)
            proc.send_signal(sig.SIGTERM)  # ignored by the child on purpose
            await LocalProcessLauncher._await_exit(proc.pid, timeout=0.5)
            assert not _pid_alive(proc.pid)
        finally:
            if proc.poll() is None:
                proc.kill()
            proc.wait(timeout=5)
