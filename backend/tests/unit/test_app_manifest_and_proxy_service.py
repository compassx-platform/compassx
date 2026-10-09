"""Unit tests for AppManifestService custom ports, Caddyfile generation, and In-Pod Reverse Proxy supervisor."""
import os
import unittest
from unittest.mock import MagicMock

from app.services.app_manifest_service import app_manifest_service, AppManifestService
from app.sandbox.drivers.k8s_driver import _sanitize_k8s_label_key, _sanitize_k8s_name
from app.routes.app_dev_routes import _build_app_sandbox_spec
from app.models.app import App


class TestAppManifestAndProxyService(unittest.TestCase):

    def setUp(self):
        self.service = AppManifestService()

    # ==========================================
    # 1. MANIFEST PARSING & PORT EXTRACTION
    # ==========================================
    def test_parse_manifest_named_services_with_custom_ports(self):
        yaml_text = """
version: "1"
name: ane-network-dashboard
services:
  backend:
    command: ["uvicorn", "main:app", "--port", "8877"]
    port: 8877
    dir: "server"
    path: "/api"
  frontend:
    command: "npm run dev -- --port 4000"
    port: 4000
    dir: "client"
    path: "/"
env:
  - name: VITE_API_URL
    value: "/api"
"""
        manifest = self.service.parse_manifest_text(yaml_text, "app.yaml")
        self.assertIsNotNone(manifest)
        run_cfg = self.service.get_run_config(manifest)

        self.assertIsNotNone(run_cfg)
        self.assertEqual(run_cfg["backend_port"], 8877)
        self.assertEqual(run_cfg["frontend_port"], 4000)
        self.assertEqual(run_cfg["backend_dir"], "server")
        self.assertEqual(run_cfg["frontend_dir"], "client")
        self.assertEqual(run_cfg["backend_path"], "/api")
        self.assertEqual(run_cfg["frontend_path"], "/")
        self.assertIn("uvicorn main:app --port 8877", run_cfg["backend_command"])
        self.assertIn("npm run dev -- --port 4000", run_cfg["frontend_command"])

    def test_parse_manifest_single_command_custom_port(self):
        yaml_text = """
command: ["streamlit", "run", "app.py", "--server.port", "8501"]
port: 8501
"""
        manifest = self.service.parse_manifest_text(yaml_text, "app.yaml")
        run_cfg = self.service.get_run_config(manifest)

        self.assertIsNotNone(run_cfg)
        self.assertEqual(run_cfg["backend_port"], 8501)
        self.assertIn("streamlit run app.py", run_cfg["backend_command"])

    def test_parse_manifest_top_level_frontend_and_backend(self):
        yaml_text = """
command: uvicorn main:app
frontend: npm run dev
backend_port: 8000
frontend_port: 3000
"""
        manifest = self.service.parse_manifest_text(yaml_text, "app.yaml")
        run_cfg = self.service.get_run_config(manifest)

        self.assertIsNotNone(run_cfg)
        self.assertEqual(run_cfg["backend_port"], 8000)
        self.assertEqual(run_cfg["frontend_port"], 3000)

    # ==========================================
    # 2. CADDYFILE & PROXY SCRIPT GENERATION
    # ==========================================
    def test_generate_caddyfile_dual_services(self):
        run_cfg = {
            "gateway_port": 8080,
            "backend_port": 8877,
            "frontend_port": 4000,
            "backend_path": "/api",
            "frontend_command": "npm run dev",
            "backend_command": "uvicorn main:app",
        }
        caddyfile = self.service.generate_caddyfile(run_cfg)
        self.assertIn(":8080 {", caddyfile)
        self.assertIn("handle /api/* {", caddyfile)
        self.assertIn("reverse_proxy 127.0.0.1:8877", caddyfile)
        self.assertIn("handle /* {", caddyfile)
        self.assertIn("reverse_proxy 127.0.0.1:4000", caddyfile)

    def test_generate_caddyfile_frontend_only(self):
        run_cfg = {
            "gateway_port": 8080,
            "frontend_port": 4000,
            "frontend_command": "npm run dev",
            "backend_command": None,
        }
        caddyfile = self.service.generate_caddyfile(run_cfg)
        self.assertIn(":8080 {", caddyfile)
        self.assertIn("reverse_proxy 127.0.0.1:4000", caddyfile)

    def test_generate_proxy_script_contains_routing_logic(self):
        run_cfg = {
            "gateway_port": 8080,
            "backend_port": 8877,
            "frontend_port": 4000,
            "backend_path": "/api",
            "frontend_command": "npm run dev",
            "backend_command": "uvicorn main:app",
        }
        script = self.service.generate_proxy_script(run_cfg)
        self.assertIn("GATEWAY_PORT = 8080", script)
        self.assertIn("BACKEND_PORT = 8877", script)
        self.assertIn("FRONTEND_PORT = 4000", script)
        self.assertIn("path.startswith(BACKEND_PATH)", script)

    # ==========================================
    # 3. KUBERNETES LABELS & SANITIZATION
    # ==========================================
    def test_sanitize_k8s_label_key(self):
        self.assertEqual(_sanitize_k8s_label_key("compassx/app-id"), "compassx/app-id")
        self.assertEqual(_sanitize_k8s_label_key("compassx/dev"), "compassx/dev")
        self.assertEqual(_sanitize_k8s_label_key("simple_key"), "simple_key")

    def test_build_app_sandbox_spec_canonical_labels(self):
        app = App(
            id="app_bc48533825834b3f",
            name="ANE",
            slug="ane",
            workspace_id="d1cb29da-3985-41d9-9d8b-329db0541eae",
        )
        spec = _build_app_sandbox_spec(app)
        self.assertEqual(spec.labels["compassx/app-id"], "app-bc48533825834b3f")
        self.assertEqual(spec.labels["compassx/dev"], "true")
        self.assertEqual(spec.labels["compassx/role"], "dev")
        self.assertIn("compassx-app-id", spec.labels)


if __name__ == "__main__":
    unittest.main()
