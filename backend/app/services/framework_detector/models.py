"""Data models and serialization for framework detection results.

Adheres to Interface Segregation Principle: Clean, strongly-typed representations
of detected services and diagnostic metadata.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List


@dataclass
class FrontendSpec:
    framework: str  # e.g. "vite", "nextjs", "react", "vue", "static-html", "generic-npm"
    directory: str  # relative directory path, e.g. "frontend" or "."
    entry_file: Optional[str] = None
    package_manager: str = "npm"
    port: int = 8080
    dev_command: str = "npm run dev -- --host 0.0.0.0 --port 8080"
    build_command: Optional[str] = "npm run build"
    dist_dir: Optional[str] = "dist"


@dataclass
class BackendSpec:
    framework: str  # e.g. "fastapi", "flask", "streamlit", "django", "express", "generic-python"
    directory: str  # relative directory path, e.g. "backend" or "."
    entry_file: Optional[str] = None
    module: Optional[str] = None  # e.g. "main:app"
    dependencies_file: Optional[str] = None
    port: int = 8000
    api_prefix: str = "/api"
    dev_command: str = "uvicorn main:app --host 0.0.0.0 --port 8000 --reload"


@dataclass
class ManifestSpec:
    path: str
    install_command: Optional[str] = None
    env: Dict[str, str] = field(default_factory=dict)
    services: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DetectionReport:
    detected: bool
    app_type: str  # "fullstack", "frontend-only", "backend-only", "static-html", "custom-manifest", "unknown"
    has_frontend: bool = False
    has_backend: bool = False
    manifest_found: bool = False
    frontend: Optional[FrontendSpec] = None
    backend: Optional[BackendSpec] = None
    manifest: Optional[ManifestSpec] = None
    diagnostics: Dict[str, Any] = field(default_factory=dict)
    error: Optional[Dict[str, Any]] = None
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert report to standard serializable dictionary."""
        res = {
            "detected": self.detected,
            "app_type": self.app_type,
            "has_frontend": self.has_frontend,
            "has_backend": self.has_backend,
            "manifest_found": self.manifest_found,
            "frontend": asdict(self.frontend) if self.frontend else None,
            "backend": asdict(self.backend) if self.backend else None,
            "manifest": asdict(self.manifest) if self.manifest else None,
            "diagnostics": self.diagnostics,
            "error": self.error,
            "recommendations": self.recommendations,
        }
        return res
