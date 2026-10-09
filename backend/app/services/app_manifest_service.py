"""App Manifest Service — Databricks-style app.yaml loader and parser for CompassX."""
import os
import shlex
import logging
from typing import Dict, Any, Optional, List, Union
import yaml

logger = logging.getLogger(__name__)

class AppManifestService:
    """Parses and normalizes Databricks-style app.yaml manifests."""

    MANIFEST_FILENAMES = ["app.yaml", "app.yml"]

    def find_manifest(self, base_dir: str) -> Optional[str]:
        """Check if app.yaml or app.yml exists in the given directory or subdirectories."""
        if not base_dir or not os.path.exists(base_dir):
            return None

        # 1. Check root directory first
        for name in self.MANIFEST_FILENAMES:
            p = os.path.join(base_dir, name)
            if os.path.isfile(p):
                return p

        # 2. Check 1 level down (e.g. monorepo subfolder if workspace is scoped)
        try:
            for entry in os.scandir(base_dir):
                if entry.is_dir() and not entry.name.startswith((".", "node_modules", "venv", ".venv")):
                    for name in self.MANIFEST_FILENAMES:
                        sub_p = os.path.join(entry.path, name)
                        if os.path.isfile(sub_p):
                            return sub_p
        except Exception as e:
            logger.debug("Error scanning for app.yaml in %s: %s", base_dir, e)

        return None

    def load_manifest(self, base_dir: str) -> Optional[Dict[str, Any]]:
        """Find and parse app.yaml from base_dir into a structured dictionary."""
        manifest_path = self.find_manifest(base_dir)
        if not manifest_path:
            return None

        try:
            with open(manifest_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            return self.parse_manifest_text(content, manifest_path=manifest_path)
        except Exception as e:
            logger.warning("Failed to parse app.yaml at %s: %s", manifest_path, e)

        return None

    def parse_manifest_text(self, text: str, manifest_path: str = "app.yaml") -> Optional[Dict[str, Any]]:
        """Parse raw YAML content string into a structured manifest dictionary."""
        if not text or not text.strip():
            return None
        try:
            data = yaml.safe_load(text)
            if isinstance(data, dict):
                data["_manifest_path"] = manifest_path
                data["_manifest_dir"] = os.path.dirname(manifest_path)
                return data
        except Exception as e:
            logger.warning("Failed to parse app.yaml content: %s", e)
        return None

    def normalize_command(self, cmd_value: Union[List[str], str, None]) -> Optional[str]:
        """Convert array of command arguments or raw string into an executable shell string."""
        if not cmd_value:
            return None
        if isinstance(cmd_value, list):
            # If list of args, e.g. ["streamlit", "run", "app.py", "--server.port", "8080"]
            safe_args = [shlex.quote(str(arg)) for arg in cmd_value]
            return " ".join(safe_args)
        if isinstance(cmd_value, str):
            return cmd_value.strip()
        return None

    def get_install_command(self, manifest: Optional[Dict[str, Any]]) -> Optional[str]:
        """Extract custom install/build command line if defined in app.yaml.
        
        Supports:
          install: ["pip install -r requirements.txt", "npm install"]
          install: "pip install -r requirements.txt && npm install"
        """
        if not manifest:
            return None

        install_val = manifest.get("install")
        if not install_val:
            return None

        if isinstance(install_val, list):
            cmds = [self.normalize_command(item) or str(item).strip() for item in install_val if item]
            return " && ".join(cmds) if cmds else None

        if isinstance(install_val, str):
            return install_val.strip()

        return None

    def get_env_exports(self, manifest: Optional[Dict[str, Any]]) -> str:
        """Extract environment variables and return as shell export statements."""
        if not manifest:
            return ""

        env_val = manifest.get("env")
        if not env_val:
            return ""

        exports = []
        if isinstance(env_val, list):
            for item in env_val:
                if isinstance(item, dict) and "name" in item:
                    k = str(item.get("name", "")).strip()
                    v = str(item.get("value", "")).strip()
                    if k:
                        exports.append(f"export {k}={shlex.quote(v)};")
        elif isinstance(env_val, dict):
            for k, v in env_val.items():
                if k:
                    exports.append(f"export {str(k).strip()}={shlex.quote(str(v).strip())};")

        return " ".join(exports)

    def get_run_config(self, manifest: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Extract backend and frontend run configuration from app.yaml.
        
        Supports Databricks single command, full-stack monorepo, or named services:
        1. Databricks standard:
           command: ["streamlit", "run", "app.py"]
           port: 8501
        2. Full-stack:
           command: ["uvicorn", "main:app", "--port", "8000"]
           frontend: ["npx", "vite", "--port", "4000"]
           backend_port: 8000
           frontend_port: 4000
        3. Services dictionary:
           services:
             backend: { command: "...", dir: "backend", port: 8877, path: "/api" }
             frontend: { command: "...", dir: "frontend", port: 4000, path: "/" }
        """
        if not manifest:
            return None

        manifest_dir = manifest.get("_manifest_dir", "")

        # A. Check services map
        services = manifest.get("services")
        if isinstance(services, dict):
            backend_cmd = None
            backend_dir = None
            backend_port = None
            backend_path = "/api"
            frontend_cmd = None
            frontend_dir = None
            frontend_port = None
            frontend_path = "/"

            if "backend" in services and isinstance(services["backend"], dict):
                backend_cmd = self.normalize_command(services["backend"].get("command"))
                backend_dir = services["backend"].get("dir")
                backend_port = services["backend"].get("port") or services["backend"].get("api_port")
                backend_path = services["backend"].get("path") or services["backend"].get("route") or "/api"
            elif "api" in services and isinstance(services["api"], dict):
                backend_cmd = self.normalize_command(services["api"].get("command"))
                backend_dir = services["api"].get("dir")
                backend_port = services["api"].get("port") or services["api"].get("api_port")
                backend_path = services["api"].get("path") or services["api"].get("route") or "/api"

            if "frontend" in services and isinstance(services["frontend"], dict):
                frontend_cmd = self.normalize_command(services["frontend"].get("command"))
                frontend_dir = services["frontend"].get("dir")
                frontend_port = services["frontend"].get("port") or services["frontend"].get("ui_port")
                frontend_path = services["frontend"].get("path") or services["frontend"].get("route") or "/"
            elif "web" in services and isinstance(services["web"], dict):
                frontend_cmd = self.normalize_command(services["web"].get("command"))
                frontend_dir = services["web"].get("dir")
                frontend_port = services["web"].get("port") or services["web"].get("ui_port")
                frontend_path = services["web"].get("path") or services["web"].get("route") or "/"

            # Fallbacks for ports from top-level manifest if not under services
            if not backend_port:
                backend_port = manifest.get("backend_port") or manifest.get("api_port")
            if not frontend_port:
                frontend_port = manifest.get("frontend_port") or manifest.get("ui_port") or manifest.get("port")

            if backend_cmd or frontend_cmd:
                return {
                    "backend_command": backend_cmd,
                    "backend_dir": backend_dir,
                    "backend_port": int(backend_port) if backend_port else 8000,
                    "backend_path": backend_path,
                    "frontend_command": frontend_cmd,
                    "frontend_dir": frontend_dir,
                    "frontend_port": int(frontend_port) if frontend_port else (4000 if frontend_cmd else 8080),
                    "frontend_path": frontend_path,
                    "gateway_port": int(manifest.get("gateway_port", 8080)),
                    "env_exports": self.get_env_exports(manifest),
                    "manifest_path": manifest.get("_manifest_path"),
                }

        # B. Check top-level command and frontend
        raw_cmd = manifest.get("command")
        raw_frontend = manifest.get("frontend") or manifest.get("frontend_command")

        backend_cmd = self.normalize_command(raw_cmd)
        frontend_cmd = self.normalize_command(raw_frontend)

        if not backend_cmd and not frontend_cmd:
            return None

        top_b_port = manifest.get("backend_port") or manifest.get("api_port") or (manifest.get("port") if not frontend_cmd else None)
        top_f_port = manifest.get("frontend_port") or manifest.get("ui_port") or (manifest.get("port") if frontend_cmd else None)

        return {
            "backend_command": backend_cmd,
            "backend_dir": manifest.get("backend_dir"),
            "backend_port": int(top_b_port) if top_b_port else 8000,
            "backend_path": manifest.get("backend_path", "/api"),
            "frontend_command": frontend_cmd,
            "frontend_dir": manifest.get("frontend_dir"),
            "frontend_port": int(top_f_port) if top_f_port else (4000 if frontend_cmd else 8080),
            "frontend_path": manifest.get("frontend_path", "/"),
            "gateway_port": int(manifest.get("gateway_port", 8080)),
            "env_exports": self.get_env_exports(manifest),
            "manifest_path": manifest.get("_manifest_path"),
        }

    def generate_caddyfile(self, run_config: Optional[Dict[str, Any]] = None) -> str:
        """Generate a production-grade Caddyfile reverse proxy configuration for port 8080."""
        cfg = run_config or {}
        gateway_port = cfg.get("gateway_port", 8080)
        backend_port = cfg.get("backend_port", 8000)
        frontend_port = cfg.get("frontend_port", 4000)
        backend_path = cfg.get("backend_path", "/api").rstrip("/")
        frontend_cmd = cfg.get("frontend_command")
        backend_cmd = cfg.get("backend_command")

        # If both frontend and backend are configured
        if frontend_cmd and backend_cmd:
            return (
                f":{gateway_port} {{\n"
                f"    # API and WebSocket routes directed to backend\n"
                f"    handle {backend_path}/* {{\n"
                f"        reverse_proxy 127.0.0.1:{backend_port}\n"
                f"    }}\n"
                f"    handle /ws/* {{\n"
                f"        reverse_proxy 127.0.0.1:{backend_port}\n"
                f"    }}\n"
                f"    handle /docs* {{\n"
                f"        reverse_proxy 127.0.0.1:{backend_port}\n"
                f"    }}\n"
                f"    handle /openapi.json* {{\n"
                f"        reverse_proxy 127.0.0.1:{backend_port}\n"
                f"    }}\n"
                f"    # All other routes directed to frontend\n"
                f"    handle /* {{\n"
                f"        reverse_proxy 127.0.0.1:{frontend_port}\n"
                f"    }}\n"
                f"}}\n"
            )
        elif backend_cmd and not frontend_cmd:
            return (
                f":{gateway_port} {{\n"
                f"    handle /* {{\n"
                f"        reverse_proxy 127.0.0.1:{backend_port}\n"
                f"    }}\n"
                f"}}\n"
            )
        else:
            return (
                f":{gateway_port} {{\n"
                f"    handle /* {{\n"
                f"        reverse_proxy 127.0.0.1:{frontend_port}\n"
                f"    }}\n"
                f"}}\n"
            )

    def generate_proxy_script(self, run_config: Optional[Dict[str, Any]] = None) -> str:
        """Generate a lightweight zero-dependency Python reverse proxy fallback script."""
        cfg = run_config or {}
        gateway_port = cfg.get("gateway_port", 8080)
        backend_port = cfg.get("backend_port", 8000)
        frontend_port = cfg.get("frontend_port", 4000)
        backend_path = cfg.get("backend_path", "/api").rstrip("/")
        has_frontend = bool(cfg.get("frontend_command"))
        has_backend = bool(cfg.get("backend_command"))

        return (
            "import socket, threading, sys, os\n"
            f"GATEWAY_PORT = {gateway_port}\n"
            f"BACKEND_PORT = {backend_port}\n"
            f"FRONTEND_PORT = {frontend_port}\n"
            f"BACKEND_PATH = '{backend_path}'\n"
            f"HAS_FRONTEND = {has_frontend}\n"
            f"HAS_BACKEND = {has_backend}\n"
            "\n"
            "def forward(src, dst):\n"
            "    while True:\n"
            "        try:\n"
            "            data = src.recv(8192)\n"
            "            if not data: break\n"
            "            dst.sendall(data)\n"
            "        except Exception: break\n"
            "    try: src.close()\n"
            "    except Exception: pass\n"
            "    try: dst.close()\n"
            "    except Exception: pass\n"
            "\n"
            "def handle_client(client):\n"
            "    try:\n"
            "        peek = client.recv(1024, socket.MSG_PEEK)\n"
            "        target_port = FRONTEND_PORT if HAS_FRONTEND else BACKEND_PORT\n"
            "        if peek and HAS_FRONTEND and HAS_BACKEND:\n"
            "            try:\n"
            "                first_line = peek.decode('utf-8', errors='ignore').split('\\r\\n')[0]\n"
            "                parts = first_line.split(' ')\n"
            "                if len(parts) >= 2:\n"
            "                    path = parts[1]\n"
            "                    if path.startswith(BACKEND_PATH) or path.startswith('/ws') or path.startswith('/docs') or path.startswith('/openapi.json'):\n"
            "                        target_port = BACKEND_PORT\n"
            "                    else:\n"
            "                        target_port = FRONTEND_PORT\n"
            "            except Exception:\n"
            "                pass\n"
            "        target = socket.create_connection(('127.0.0.1', int(target_port)), timeout=5)\n"
            "        threading.Thread(target=forward, args=(client, target), daemon=True).start()\n"
            "        threading.Thread(target=forward, args=(target, client), daemon=True).start()\n"
            "    except Exception:\n"
            "        try: client.close()\n"
            "        except Exception: pass\n"
            "\n"
            "def main():\n"
            "    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n"
            "    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)\n"
            "    srv.bind(('0.0.0.0', GATEWAY_PORT))\n"
            "    srv.listen(100)\n"
            "    while True:\n"
            "        try:\n"
            "            client, _ = srv.accept()\n"
            "            threading.Thread(target=handle_client, args=(client,), daemon=True).start()\n"
            "        except Exception:\n"
            "            pass\n"
            "\n"
            "if __name__ == '__main__':\n"
            "    main()\n"
        )


app_manifest_service = AppManifestService()

