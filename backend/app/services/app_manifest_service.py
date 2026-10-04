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
        2. Full-stack:
           command: ["uvicorn", "main:app", "--port", "8000"]
           frontend: ["npx", "vite", "--port", "8080"]
        3. Services dictionary:
           services:
             backend: { command: "...", dir: "backend" }
             frontend: { command: "...", dir: "frontend" }
        """
        if not manifest:
            return None

        manifest_dir = manifest.get("_manifest_dir", "")

        # A. Check services map
        services = manifest.get("services")
        if isinstance(services, dict):
            backend_cmd = None
            backend_dir = None
            frontend_cmd = None
            frontend_dir = None

            if "backend" in services and isinstance(services["backend"], dict):
                backend_cmd = self.normalize_command(services["backend"].get("command"))
                backend_dir = services["backend"].get("dir")
            elif "api" in services and isinstance(services["api"], dict):
                backend_cmd = self.normalize_command(services["api"].get("command"))
                backend_dir = services["api"].get("dir")

            if "frontend" in services and isinstance(services["frontend"], dict):
                frontend_cmd = self.normalize_command(services["frontend"].get("command"))
                frontend_dir = services["frontend"].get("dir")
            elif "web" in services and isinstance(services["web"], dict):
                frontend_cmd = self.normalize_command(services["web"].get("command"))
                frontend_dir = services["web"].get("dir")

            if backend_cmd or frontend_cmd:
                return {
                    "backend_command": backend_cmd,
                    "backend_dir": backend_dir,
                    "frontend_command": frontend_cmd,
                    "frontend_dir": frontend_dir,
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

        return {
            "backend_command": backend_cmd,
            "backend_dir": manifest.get("backend_dir"),
            "frontend_command": frontend_cmd,
            "frontend_dir": manifest.get("frontend_dir"),
            "env_exports": self.get_env_exports(manifest),
            "manifest_path": manifest.get("_manifest_path"),
        }


app_manifest_service = AppManifestService()
