"""Tests for CompassXProcessProxy.

Mocks kubernetes.stream.stream and kubernetes.client.CoreV1Api.
"""
import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from services.enterprise_gateway.config import JOB_ID_LABEL, eg_settings


def _make_pod(phase="Running", pod_ip="10.244.0.47", name="compassx-spark-abc12345"):
    pod = MagicMock()
    pod.metadata.name = name
    pod.status.phase = phase
    pod.status.pod_ip = pod_ip
    return pod


class TestCompassXProcessProxy:
    """Unit tests for CompassXProcessProxy methods."""

    def _make_proxy(self):
        """Create proxy instance with mocked base class."""
        with patch(
            "services.enterprise_gateway.process_proxy.KubernetesProcessProxy",
            MagicMock,
        ):
            from services.enterprise_gateway.process_proxy import CompassXProcessProxy

            proxy = CompassXProcessProxy.__new__(CompassXProcessProxy)
            proxy.kernel_id = "test-kernel-123"
            proxy.pod_name = None
            proxy.pod_ip = None
            proxy.job_id = None
            proxy.local_conn = None
            return proxy

    # ── _get_pod ───────────────────────────────────────────────────────────────

    def test_get_pod_found_running(self):
        proxy = self._make_proxy()
        pod = _make_pod()
        with patch("services.enterprise_gateway.process_proxy.k8s_client.CoreV1Api") as mock_api:
            mock_api.return_value.list_namespaced_pod.return_value.items = [pod]
            result = proxy._get_pod("abc12345")
        assert result is pod
        mock_api.return_value.list_namespaced_pod.assert_called_once_with(
            namespace=eg_settings.KERNEL_NAMESPACE,
            label_selector=f"{JOB_ID_LABEL}=abc12345",
        )

    def test_get_pod_not_found_raises(self):
        proxy = self._make_proxy()
        with patch("services.enterprise_gateway.process_proxy.k8s_client.CoreV1Api") as mock_api:
            mock_api.return_value.list_namespaced_pod.return_value.items = []
            with pytest.raises(RuntimeError, match="not found"):
                proxy._get_pod("missing-job")

    def test_get_pod_not_running_raises(self):
        proxy = self._make_proxy()
        pod = _make_pod(phase="Pending")
        with patch("services.enterprise_gateway.process_proxy.k8s_client.CoreV1Api") as mock_api:
            mock_api.return_value.list_namespaced_pod.return_value.items = [pod]
            with pytest.raises(RuntimeError, match="Pending"):
                proxy._get_pod("pending-job")

    # ── launch_process ─────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_launch_process_missing_job_id_raises(self):
        proxy = self._make_proxy()
        with pytest.raises(RuntimeError, match="COMPASSX_JOB_ID is required"):
            await proxy.launch_process([], env={})

    @pytest.mark.asyncio
    async def test_launch_process_finds_pod_and_execs(self):
        proxy = self._make_proxy()
        pod = _make_pod(pod_ip="10.1.2.3", name="compassx-spark-abc12345")
        conn_data = {
            "ip": "127.0.0.1",
            "shell_port": 50000,
            "iopub_port": 50001,
            "stdin_port": 50002,
            "control_port": 50003,
            "hb_port": 50004,
            "key": "test-key",
            "transport": "tcp",
            "signature_scheme": "hmac-sha256",
            "kernel_name": "",
        }

        with (
            patch.object(proxy, "_get_pod", return_value=pod),
            patch.object(proxy, "_exec_in_pod_background"),
            patch.object(proxy, "_exec_in_pod", side_effect=[
                "",  # test -f: success (file exists)
                json.dumps(conn_data),  # cat connection file
            ]),
            patch("asyncio.sleep", AsyncMock()),
            patch("builtins.open", unittest.mock.mock_open()),
            patch("json.dump"),
        ):
            result = await proxy.launch_process([], env={"COMPASSX_JOB_ID": "abc12345"})

        assert result is proxy
        assert proxy.pod_name == "compassx-spark-abc12345"
        assert proxy.pod_ip == "10.1.2.3"
        assert proxy.job_id == "abc12345"

    @pytest.mark.asyncio
    async def test_launch_process_replaces_ip_with_pod_ip(self):
        proxy = self._make_proxy()
        pod = _make_pod(pod_ip="10.5.6.7")
        conn_data = {"ip": "127.0.0.1", "shell_port": 50000, "key": "k"}

        written = {}

        def fake_dump(data, f):
            written.update(data)

        with (
            patch.object(proxy, "_get_pod", return_value=pod),
            patch.object(proxy, "_exec_in_pod_background"),
            patch.object(proxy, "_exec_in_pod", side_effect=["", json.dumps(conn_data)]),
            patch("asyncio.sleep", AsyncMock()),
            patch("builtins.open", unittest.mock.mock_open()),
            patch("json.dump", side_effect=fake_dump),
        ):
            await proxy.launch_process([], env={"COMPASSX_JOB_ID": "abc12345"})

        assert written.get("ip") == "10.5.6.7"

    # ── kill ──────────────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_kill_execs_kill_and_removes_file(self):
        proxy = self._make_proxy()
        proxy.pod_name = "compassx-spark-abc12345"
        proxy.local_conn = "/tmp/eg-kernel-test-kernel-123.json"

        exec_calls = []

        def fake_exec(pod_name, command, timeout=30):
            exec_calls.append(command)
            if command[0] == "pgrep":
                return "12345\n"
            return ""

        with (
            patch.object(proxy, "_exec_in_pod", side_effect=fake_exec),
            patch("os.path.exists", return_value=True),
            patch("os.remove"),
        ):
            await proxy.kill()

        pgrep_call = next(c for c in exec_calls if c[0] == "pgrep")
        kill_call = next(c for c in exec_calls if c[0] == "kill" and c[1] == "-9")
        rm_call = next(c for c in exec_calls if c[0] == "rm")

        assert "test-kernel-123.json" in " ".join(pgrep_call)
        assert "12345" in kill_call
        assert "test-kernel-123.json" in " ".join(rm_call)

    @pytest.mark.asyncio
    async def test_kill_does_not_delete_pod(self):
        """Killing kernel must NOT delete the compute pod."""
        proxy = self._make_proxy()
        proxy.pod_name = "compassx-spark-abc12345"
        proxy.local_conn = "/tmp/test.json"

        with (
            patch.object(proxy, "_exec_in_pod", return_value="99\n"),
            patch("os.path.exists", return_value=False),
        ):
            with patch("kubernetes.client.CoreV1Api") as mock_api:
                await proxy.kill()
                # delete_namespaced_pod must never be called
                mock_api.return_value.delete_namespaced_pod.assert_not_called()

    # ── poll ──────────────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_poll_returns_none_when_process_found(self):
        proxy = self._make_proxy()
        proxy.pod_name = "compassx-spark-abc12345"
        with patch.object(proxy, "_exec_in_pod", return_value="12345\n"):
            result = await proxy.poll()
        assert result is None

    @pytest.mark.asyncio
    async def test_poll_returns_1_when_process_not_found(self):
        proxy = self._make_proxy()
        proxy.pod_name = "compassx-spark-abc12345"
        with patch.object(proxy, "_exec_in_pod", side_effect=RuntimeError("not found")):
            result = await proxy.poll()
        assert result == 1

    # ── _exec_in_pod ──────────────────────────────────────────────────────────

    def test_exec_in_pod_uses_correct_namespace(self):
        proxy = self._make_proxy()
        with (
            patch("services.enterprise_gateway.process_proxy.k8s_client.CoreV1Api") as mock_api,
            patch("services.enterprise_gateway.process_proxy.k8s_stream.stream", return_value="ok"),
        ):
            from services.enterprise_gateway.process_proxy import k8s_stream

            result = proxy._exec_in_pod("my-pod", ["echo", "hi"])
            # stream called with correct namespace
            call_kwargs = k8s_stream.stream.call_args
            assert eg_settings.KERNEL_NAMESPACE in str(call_kwargs)
