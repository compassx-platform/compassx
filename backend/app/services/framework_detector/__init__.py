"""Framework Detector Module - Decoupled, SOLID-compliant framework identification.

This module provides detection of web frontend, backend, and manifest services
across application workspaces. It returns a standardized JSON contract.
"""

from .detector import FrameworkDetector, detect_framework
from .models import (
    DetectionReport,
    FrontendSpec,
    BackendSpec,
    ManifestSpec,
)

__all__ = [
    "FrameworkDetector",
    "detect_framework",
    "DetectionReport",
    "FrontendSpec",
    "BackendSpec",
    "ManifestSpec",
]
