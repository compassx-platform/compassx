"""Manifest Detector - Detects and parses app.yaml / app.yml specifications.

Adheres to Single Responsibility Principle: Solely responsible for finding
and extracting explicit developer-provided service manifests.
"""

import os
import shlex
from typing import Optional, Dict, Any
from .base import BaseDetector
from .models import ManifestSpec, FrontendSpec, BackendSpec


def _safe_load_yaml(content: str) -> Optional[Dict[str, Any]]:
    """Safely load YAML with PyYAML if available, or lightweight line parser fallback."""
    try:
        import yaml
        return yaml.safe_load(content)
    except Exception:
        pass

    # Lightweight fallback parser for basic app.yaml
    result: Dict[str, Any] = {}
    current_section = None
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.endswith(":") and not (" " in line[:-1]):
            current_section = line[:-1]
            result[current_section] = {}
            continue
        if ":" in line:
            k, v = line.split(":", 1)
            k, v = k.strip(), v.strip().strip("'\"")
            if current_section and isinstance(result.get(current_section), dict):
                result[current_section][k] = v
            else:
                result[k] = v
    return result if result else None


class ManifestDetector(BaseDetector):
    """Detects explicit application manifest files."""

    MANIFEST_FILENAMES = ("app.yaml", "app.yml", ".compassx/app.yaml", ".compassx/app.yml")

    def find_manifest_file(self, base_dir: str) -> Optional[str]:
        for fname in self.MANIFEST_FILENAMES:
            candidate = os.path.join(base_dir, fname)
            if os.path.isfile(candidate):
                return candidate

        # Check immediate subdirectories (1 level deep)
        try:
            for item in os.listdir(base_dir):
                item_path = os.path.join(base_dir, item)
                if os.path.isdir(item_path) and item not in ("node_modules", ".git", ".cache"):
                    for fname in ("app.yaml", "app.yml"):
                        cand = os.path.join(item_path, fname)
                        if os.path.isfile(cand):
                            return cand
        except Exception:
            pass

        return None

    def can_detect(self, base_dir: str, context: Optional[Dict[str, Any]] = None) -> bool:
        return self.find_manifest_file(base_dir) is not None

    def detect(self, base_dir: str, context: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        manifest_path = self.find_manifest_file(base_dir)
        if not manifest_path:
            return None

        try:
            with open(manifest_path, "r", encoding="utf-8") as fh:
                data = _safe_load_yaml(fh.read())
        except Exception:
            return None

        if not isinstance(data, dict):
            return None

        manifest_dir = os.path.dirname(manifest_path)
        rel_dir = os.path.relpath(manifest_dir, base_dir) if manifest_dir != base_dir else "."

        install_cmd = data.get("install")
        if isinstance(install_cmd, list):
            install_cmd = " && ".join([str(c).strip() for c in install_cmd if c])
        elif isinstance(install_cmd, str):
            install_cmd = install_cmd.strip()

        env_vars: Dict[str, str] = {}
        raw_env = data.get("env") or {}
        if isinstance(raw_env, list):
            for e in raw_env:
                if isinstance(e, dict) and "name" in e:
                    env_vars[str(e["name"])] = str(e.get("value", ""))
        elif isinstance(raw_env, dict):
            for k, v in raw_env.items():
                env_vars[str(k)] = str(v)

        services = data.get("services") or {}
        frontend_spec = None
        backend_spec = None

        if isinstance(services, dict) and services:
            # Backend service from manifest
            b_svc = services.get("backend") or services.get("api")
            if b_svc:
                b_cmd = b_svc.get("command") if isinstance(b_svc, dict) else str(b_svc)
                b_port = int(b_svc.get("port", 8000)) if isinstance(b_svc, dict) else 8000
                b_path = b_svc.get("path", "/api") if isinstance(b_svc, dict) else "/api"
                b_subdir = b_svc.get("dir", rel_dir) if isinstance(b_svc, dict) else rel_dir
                backend_spec = BackendSpec(
                    framework="manifest-backend",
                    directory=b_subdir,
                    port=b_port,
                    api_prefix=b_path,
                    dev_command=b_cmd if isinstance(b_cmd, str) else " ".join([shlex.quote(str(x)) for x in b_cmd]),
                )

            # Frontend service from manifest
            f_svc = services.get("frontend") or services.get("ui") or services.get("web")
            if f_svc:
                f_cmd = f_svc.get("command") if isinstance(f_svc, dict) else str(f_svc)
                f_port = int(f_svc.get("port", 8080)) if isinstance(f_svc, dict) else 8080
                f_subdir = f_svc.get("dir", rel_dir) if isinstance(f_svc, dict) else rel_dir
                frontend_spec = FrontendSpec(
                    framework="manifest-frontend",
                    directory=f_subdir,
                    port=f_port,
                    dev_command=f_cmd if isinstance(f_cmd, str) else " ".join([shlex.quote(str(x)) for x in f_cmd]),
                )
        elif "command" in data:
            # Legacy single command manifest
            b_cmd = data.get("command")
            b_port = int(data.get("port", data.get("backend_port", 8080)))
            backend_spec = BackendSpec(
                framework="manifest-app",
                directory=rel_dir,
                port=b_port,
                dev_command=b_cmd if isinstance(b_cmd, str) else " ".join([shlex.quote(str(x)) for x in b_cmd]),
            )
            if data.get("frontend"):
                f_cmd = data.get("frontend")
                f_port = int(data.get("frontend_port", 4000))
                frontend_spec = FrontendSpec(
                    framework="manifest-frontend",
                    directory=rel_dir,
                    port=f_port,
                    dev_command=f_cmd if isinstance(f_cmd, str) else " ".join([shlex.quote(str(x)) for x in f_cmd]),
                )

        manifest_spec = ManifestSpec(
            path=os.path.relpath(manifest_path, base_dir),
            install_command=install_cmd,
            env=env_vars,
            services=services if isinstance(services, dict) else {},
        )

        return {
            "manifest": manifest_spec,
            "frontend": frontend_spec,
            "backend": backend_spec,
        }
