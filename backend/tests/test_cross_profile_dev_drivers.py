"""Unit & Integration Tests for Cross-Profile Dev Drivers (Local, Docker, Kubernetes).
Verifies that the Build Page 4-step sequence and app.yaml manifest discovery
work reliably across all 3 runtime environments.
"""
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.drivers.local_driver import LocalDevDriver
from app.services.drivers.docker_driver import DockerDevDriver
from app.services.drivers.kubernetes_driver import KubernetesDevDriver
from app.services.app_manifest_service import app_manifest_service
from app.services.omnigent_dev_service import omnigent_dev_service


class MockApp:
    def __init__(self, app_id="test_app_123", slug="test-app"):
        self.id = app_id
        self.slug = slug
        self.name = "Test App"
        self.git_branch = "main"
        self.workspace_id = None
        self.config = {}


class TestCrossProfileDevDrivers(unittest.TestCase):

    def setUp(self):
        self.app = MockApp()

    # ==========================================
    # 1. LOCAL DEV DRIVER
    # ==========================================
    def test_local_dev_driver_bash_resolution(self):
        driver = LocalDevDriver()
        bash_path = driver._resolve_bash()
        # Should resolve a valid bash binary on Windows (Git Bash) or Unix (/bin/bash)
        self.assertIsNotNone(bash_path, "LocalDevDriver should resolve a POSIX bash shell")
        self.assertTrue(os.path.exists(bash_path), f"Resolved bash path '{bash_path}' must exist on disk")

    def test_local_dev_driver_exec_posix_command(self):
        driver = LocalDevDriver()
        # Test POSIX shell syntax: arithmetic and echo
        res = driver.exec_command_in_dev(self.app, "echo 'hello from local'; echo $((10 + 20))")
        self.assertTrue(res["success"], f"Command failed: {res}")
        self.assertEqual(res["exit_code"], 0)
        self.assertIn("hello from local", res["output"])
        self.assertIn("30", res["output"])

    def test_local_dev_driver_exit_code_propagation(self):
        driver = LocalDevDriver()
        res = driver.exec_command_in_dev(self.app, "exit 77")
        self.assertFalse(res["success"])
        self.assertEqual(res["exit_code"], 77)

    def test_local_dev_driver_workdir_fallback(self):
        driver = LocalDevDriver()
        # Test nested workspace folder format: "app_id/workspace_name"
        workdir = driver._resolve_workdir(self.app, "test_app_123/default")
        self.assertTrue(os.path.isabs(workdir))
        self.assertTrue(os.path.exists(workdir))

    # ==========================================
    # 2. DOCKER DEV DRIVER
    # ==========================================
    @patch("subprocess.run")
    def test_docker_dev_driver_exec_command(self, mock_subproc):
        def fake_run(cmd, *args, **kwargs):
            cmd_str = " ".join(str(c) for c in cmd)
            if "test -d" in cmd_str:
                return MagicMock(returncode=0, stdout="EXISTS", stderr="")
            elif "mkdir -p" in cmd_str:
                return MagicMock(returncode=0, stdout="", stderr="")
            return MagicMock(returncode=0, stdout="installed successfully\n", stderr="")

        mock_subproc.side_effect = fake_run

        driver = DockerDevDriver()
        res = driver.exec_command_in_dev(self.app, "npm install", workspace_folder="default")

        self.assertTrue(res["success"])
        self.assertEqual(res["exit_code"], 0)
        self.assertIn("installed successfully", res["output"])
        self.assertEqual(res["workdir"], "/workspaces/default")

    @patch("subprocess.run")
    def test_docker_dev_driver_non_zero_exit_code(self, mock_subproc):
        def fake_run(cmd, *args, **kwargs):
            cmd_str = " ".join(str(c) for c in cmd)
            if "test -d" in cmd_str:
                return MagicMock(returncode=0, stdout="EXISTS", stderr="")
            elif "mkdir -p" in cmd_str:
                return MagicMock(returncode=0, stdout="", stderr="")
            return MagicMock(returncode=1, stdout="", stderr="npm ERR! missing script: build\n")

        mock_subproc.side_effect = fake_run

        driver = DockerDevDriver()
        res = driver.exec_command_in_dev(self.app, "npm run build", workspace_folder="default")

        self.assertFalse(res["success"])
        self.assertEqual(res["exit_code"], 1)
        self.assertIn("npm ERR!", res["output"])

    # ==========================================
    # 3. KUBERNETES DEV DRIVER
    # ==========================================
    @patch.object(KubernetesDevDriver, "_get_k8s_client")
    def test_k8s_dev_driver_exec_success(self, mock_get_client):
        mock_k8s = MagicMock()
        mock_get_client.return_value = mock_k8s

        # Mock kubernetes.stream.stream output returning stdout + exit marker
        fake_stream_output = "Installed Python packages\n__K8S_CMD_EXIT__:0\n"

        with patch("kubernetes.stream.stream", return_value=fake_stream_output):
            driver = KubernetesDevDriver()
            res = driver.exec_command_in_dev(self.app, "pip install -r requirements.txt", workspace_folder="default")

            self.assertTrue(res["success"])
            self.assertEqual(res["exit_code"], 0)
            self.assertEqual(res["output"], "Installed Python packages")
            self.assertNotIn("__K8S_CMD_EXIT__", res["output"])

    @patch.object(KubernetesDevDriver, "_get_k8s_client")
    def test_k8s_dev_driver_exec_failure_detection(self, mock_get_client):
        mock_k8s = MagicMock()
        mock_get_client.return_value = mock_k8s

        # If a command fails in pod, exit code 1 or 127 must be captured correctly!
        fake_stream_output = "ERROR: No matching distribution found for nonexistent-lib\n__K8S_CMD_EXIT__:1\n"

        with patch("kubernetes.stream.stream", return_value=fake_stream_output):
            driver = KubernetesDevDriver()
            res = driver.exec_command_in_dev(self.app, "pip install nonexistent-lib", workspace_folder="default")

            self.assertFalse(res["success"])
            self.assertEqual(res["exit_code"], 1)
            self.assertIn("ERROR: No matching distribution found", res["output"])
            self.assertNotIn("__K8S_CMD_EXIT__", res["output"])

    @patch.object(KubernetesDevDriver, "_get_k8s_client")
    def test_k8s_dev_driver_host_type_selection(self, mock_get_client):
        mock_k8s = MagicMock()
        mock_get_client.return_value = mock_k8s

        # Mock core_v1 client
        mock_core = MagicMock()
        mock_k8s.return_value = mock_core
        # Pod does not exist initially
        from kubernetes.client.exceptions import ApiException
        mock_core.read_namespaced_pod.side_effect = ApiException(status=404)
        mock_core.read_namespaced_service.side_effect = ApiException(status=404)

        driver = KubernetesDevDriver()

        # Test CompassX host
        res_compassx = driver.start_dev(self.app, repo_dir="/tmp/repo", omnigent_internal_url="http://localhost:8000", host_type="compassx")
        self.assertEqual(res_compassx["host_type"], "compassx")
        self.assertEqual(res_compassx["host_image"], "ghcr.io/omnigent-ai/omnigent-host:latest")

        # Test Omnigent host
        res_omnigent = driver.start_dev(self.app, repo_dir="/tmp/repo", omnigent_internal_url="http://localhost:8000", host_type="omnigent")
        self.assertEqual(res_omnigent["host_type"], "omnigent")
        self.assertEqual(res_omnigent["host_image"], "ghcr.io/omnigent-ai/omnigent-host:latest")

    # ==========================================
    # 3B. DOCKER DRIVER HOST TYPE RESOLUTION
    # ==========================================
    @patch("subprocess.run")
    def test_docker_dev_driver_host_type_selection(self, mock_subproc):
        # Mock inspect commands for container running check
        # Container does not exist initially: inspect returns 1
        mock_subproc.return_value = MagicMock(returncode=0, stdout="compassx-app-dev-test_app_123\n", stderr="")

        driver = DockerDevDriver()

        # Mock image existence checks
        with patch.object(driver, "_image_exists", return_value=True):
            # CompassX host
            res_cx = driver.start_dev(self.app, repo_dir="/tmp/repo", omnigent_internal_url="http://localhost:8000", host_type="compassx")
            self.assertEqual(res_cx["host_type"], "compassx")
            self.assertEqual(res_cx["host_image"], "compassx-host:latest")

            # Omnigent host
            res_omni = driver.start_dev(self.app, repo_dir="/tmp/repo", omnigent_internal_url="http://localhost:8000", host_type="omnigent")
            self.assertEqual(res_omni["host_type"], "omnigent")
            self.assertEqual(res_omni["host_image"], "ghcr.io/omnigent-ai/omnigent-host:latest")

    @patch("subprocess.run")
    def test_docker_dev_driver_get_status_detects_image_and_host_type(self, mock_subproc):
        state = {"count": 0}
        def fake_inspect(cmd, *args, **kwargs):
            cmd_str = " ".join(str(c) for c in cmd)
            if "inspect" in cmd_str:
                state["count"] += 1
                if state["count"] == 1:
                    return MagicMock(returncode=0, stdout="running|compassx-host:latest\n", stderr="")
                return MagicMock(returncode=0, stdout="running|ghcr.io/omnigent-ai/omnigent-host:latest\n", stderr="")
            return MagicMock(returncode=0, stdout="", stderr="")

        mock_subproc.side_effect = fake_inspect

        driver = DockerDevDriver()

        # Check 1: CompassX host
        status_cx = driver.get_dev_status(self.app)
        self.assertEqual(status_cx["status"], "active")
        self.assertEqual(status_cx["host_type"], "compassx")
        self.assertEqual(status_cx["host_image"], "compassx-host:latest")

        # Check 2: Omnigent host
        status_omni = driver.get_dev_status(self.app)
        self.assertEqual(status_omni["status"], "active")
        self.assertEqual(status_omni["host_type"], "omnigent")
        self.assertEqual(status_omni["host_image"], "ghcr.io/omnigent-ai/omnigent-host:latest")

    # ==========================================
    # 4. MANIFEST RESOLUTION ACROSS PROFILES
    # ==========================================
    def test_app_manifest_remote_sandbox_probe(self):
        """Verify that when app.yaml is not on the host filesystem, it probes inside the sandbox container/pod."""
        mock_driver = MagicMock()
        # Mock container probe returning app.yaml contents
        yaml_content = (
            "command: ['uvicorn', 'main:app', '--port', '8000']\n"
            "frontend: ['npx', 'vite', '--port', '8080']\n"
            "install: ['pip install -r requirements.txt && npm install']\n"
        )
        mock_driver.exec_command_in_dev.return_value = {
            "success": True,
            "exit_code": 0,
            "output": f"---MANIFEST_FILE:app.yaml---\n{yaml_content}",
        }

        # Passing non-existent host dirs forces remote probe
        manifest = omnigent_dev_service._resolve_app_manifest(
            self.app,
            mock_driver,
            folder_path="test_app_123/default",
            target_dir="/tmp/nonexistent_dir_123",
            repo_dir="/tmp/nonexistent_dir_456",
        )

        self.assertIsNotNone(manifest)
        self.assertEqual(manifest.get("_manifest_path"), "app.yaml")

        # Test install command extracted from sandbox manifest
        install_cmd = app_manifest_service.get_install_command(manifest)
        self.assertEqual(install_cmd, "pip install -r requirements.txt && npm install")

        # Test run configuration extracted from sandbox manifest
        run_cfg = app_manifest_service.get_run_config(manifest)
        self.assertIsNotNone(run_cfg)
        self.assertEqual(run_cfg["backend_command"], "uvicorn main:app --port 8000")
        self.assertEqual(run_cfg["frontend_command"], "npx vite --port 8080")

    def test_app_manifest_databricks_single_command(self):
        """Test Databricks standard command: ['streamlit', 'run', 'app.py']"""
        yaml_text = "command:\n  - streamlit\n  - run\n  - app.py\n"
        manifest = app_manifest_service.parse_manifest_text(yaml_text, "app.yaml")
        self.assertIsNotNone(manifest)
        run_cfg = app_manifest_service.get_run_config(manifest)
        self.assertIsNotNone(run_cfg)
        self.assertEqual(run_cfg["backend_command"], "streamlit run app.py")
        self.assertIsNone(run_cfg["frontend_command"])

    def test_app_manifest_services_dictionary(self):
        """Test services dict with custom dirs and env vars."""
        yaml_text = """
services:
  backend:
    command: ["python", "server.py"]
    dir: "api"
  frontend:
    command: "npm run start"
    dir: "client"
env:
  - name: PORT
    value: "8080"
  - name: DEBUG
    value: "true"
"""
        manifest = app_manifest_service.parse_manifest_text(yaml_text, "app.yaml")
        self.assertIsNotNone(manifest)
        run_cfg = app_manifest_service.get_run_config(manifest)
        self.assertEqual(run_cfg["backend_command"], "python server.py")
        self.assertEqual(run_cfg["backend_dir"], "api")
        self.assertEqual(run_cfg["frontend_command"], "npm run start")
        self.assertEqual(run_cfg["frontend_dir"], "client")
        self.assertIn("export PORT=8080", run_cfg["env_exports"])
        self.assertIn("export DEBUG=true", run_cfg["env_exports"])


if __name__ == "__main__":
    unittest.main()
