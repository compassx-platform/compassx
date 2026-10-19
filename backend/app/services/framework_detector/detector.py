"""Framework Detector Orchestrator.

Adheres to:
- Single Responsibility: Coordinates independent sub-detectors into a unified report.
- Open/Closed: Can accept custom detectors or rule extensions without modifying existing logic.
- Fault Isolation: Top-level error boundary prevents detector exceptions from crashing the caller.
"""

import os
import logging
from typing import Optional, Dict, Any, List
from .models import DetectionReport, FrontendSpec, BackendSpec, ManifestSpec
from .manifest_detector import ManifestDetector
from .frontend_detector import FrontendDetector
from .backend_detector import BackendDetector

logger = logging.getLogger(__name__)


class FrameworkDetector:
    """Orchestrates detection across manifest, frontend, and backend detectors."""

    def __init__(self, target_dir: str, context: Optional[Dict[str, Any]] = None):
        self.target_dir = os.path.abspath(target_dir)
        self.context = context or {}
        self.manifest_detector = ManifestDetector()
        self.frontend_detector = FrontendDetector()
        self.backend_detector = BackendDetector()

    def _resolve_base_dir(self) -> str:
        """Resolve effective base directory (e.g. if source files are in a configured subdir)."""
        subdir = (self.context.get("git_subdir") or "").strip("/\\")
        if subdir and os.path.isdir(os.path.join(self.target_dir, subdir)):
            return os.path.join(self.target_dir, subdir)

        # If root only has a single non-git directory containing code, inspect that
        try:
            entries = [
                d for d in os.listdir(self.target_dir)
                if os.path.isdir(os.path.join(self.target_dir, d)) and d not in (".git", "node_modules", ".cache", "__pycache__")
            ]
            if len(entries) == 1:
                single_sub = os.path.join(self.target_dir, entries[0])
                if any(os.path.isfile(os.path.join(single_sub, f)) for f in ("package.json", "app.py", "main.py", "requirements.txt", "app.yaml")):
                    return single_sub
        except Exception:
            pass

        return self.target_dir

    def detect(self) -> DetectionReport:
        """Execute detection with complete fault isolation."""
        try:
            if not os.path.exists(self.target_dir):
                return DetectionReport(
                    detected=False,
                    app_type="unknown",
                    error={
                        "code": "DIRECTORY_NOT_FOUND",
                        "title": "Workspace Directory Not Found",
                        "message": f"Target directory does not exist: {self.target_dir}",
                    },
                    recommendations=["Verify workspace path and dev environment mount."],
                )

            base_dir = self._resolve_base_dir()

            # Count files scanned for diagnostics
            files_scanned = 0
            is_empty = True
            EXCLUDED_DIRS = {".git", "node_modules", ".cache", "__pycache__", ".venv", "venv", "env", ".idea", ".vscode"}
            for root, dirs, files in os.walk(base_dir):
                dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
                files_scanned += len(files)
                if files:
                    is_empty = False

            diagnostics = {
                "inspected_dir": base_dir,
                "target_dir": self.target_dir,
                "files_scanned": files_scanned,
                "is_empty": is_empty,
                "warnings": [],
            }

            # 1. Check for Manifest first (explicit developer configuration)
            manifest_res = self.manifest_detector.detect(base_dir, self.context)
            manifest_spec: Optional[ManifestSpec] = None
            frontend_spec: Optional[FrontendSpec] = None
            backend_spec: Optional[BackendSpec] = None

            if manifest_res:
                manifest_spec = manifest_res.get("manifest")
                frontend_spec = manifest_res.get("frontend")
                backend_spec = manifest_res.get("backend")

            # 2. Check for Frontend (if not already defined by manifest)
            if not frontend_spec:
                frontend_spec = self.frontend_detector.detect(base_dir, self.context)

            # 3. Check for Backend (if not already defined by manifest)
            if not backend_spec:
                backend_spec = self.backend_detector.detect(base_dir, self.context)

            has_frontend = frontend_spec is not None
            has_backend = backend_spec is not None
            manifest_found = manifest_spec is not None
            detected = has_frontend or has_backend or manifest_found

            # Classify application type
            if manifest_found and not has_frontend and not has_backend:
                app_type = "custom-manifest"
            elif has_frontend and has_backend:
                app_type = "fullstack"
            elif has_frontend:
                app_type = "static-html" if frontend_spec.framework == "static-html" else "frontend-only"
            elif has_backend:
                app_type = "backend-only"
            else:
                app_type = "unknown"

            # Build error and recommendations if nothing was detected
            error = None
            recommendations: List[str] = []

            if not detected:
                error = {
                    "code": "NO_SERVICE_IDENTIFIED",
                    "title": "No Application Service Identified",
                    "message": "CompassX scanned the workspace but could not identify any frontend or backend entry points.",
                }
                recommendations = [
                    "Ask the Antigravity Agent in the terminal to scaffold your application.",
                    "Add a package.json in the frontend or root directory for web applications.",
                    "Add main.py or app.py with requirements.txt for Python APIs.",
                    "Or create an app.yaml file to define custom startup commands.",
                ]

            return DetectionReport(
                detected=detected,
                app_type=app_type,
                has_frontend=has_frontend,
                has_backend=has_backend,
                manifest_found=manifest_found,
                frontend=frontend_spec,
                backend=backend_spec,
                manifest=manifest_spec,
                diagnostics=diagnostics,
                error=error,
                recommendations=recommendations,
            )

        except Exception as exc:
            logger.exception("Unexpected error during framework detection: %s", exc)
            # Fault isolation: Return safe fallback report rather than crashing
            return DetectionReport(
                detected=False,
                app_type="unknown",
                error={
                    "code": "DETECTION_ERROR",
                    "title": "Framework Detection Error",
                    "message": f"An error occurred while inspecting repository: {str(exc)}",
                },
                diagnostics={"inspected_dir": self.target_dir, "exception": str(exc)},
                recommendations=["Check repository structure and file permissions."],
            )


def detect_framework(target_dir: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Public helper to run framework detection and return standard dictionary."""
    detector = FrameworkDetector(target_dir, context)
    return detector.detect().to_dict()
