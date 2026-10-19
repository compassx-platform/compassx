"""Backend Detector - Identifies Python and API backend frameworks.

Adheres to Single Responsibility Principle: Specialized exclusively in analyzing
server-side application entrypoints, runtime dependencies, and API frameworks.
"""

import os
import re
from typing import Optional, Dict, Any, Tuple
from .base import BaseDetector
from .models import BackendSpec


class BackendDetector(BaseDetector):
    """Detects backend services and server frameworks."""

    BACKEND_DIR_CANDIDATES = ("backend", "api", "server", ".")
    ENTRY_FILES = ("main.py", "app.py", "server.py", "api.py")

    def _find_backend_dir(self, base_dir: str) -> Optional[Tuple[str, str]]:
        """Find the most likely directory and entry file housing backend code."""
        # 1. Prefer dedicated backend folders
        for sub in ("backend", "api", "server"):
            target = os.path.join(base_dir, sub)
            if os.path.isdir(target):
                for ef in self.ENTRY_FILES:
                    if os.path.isfile(os.path.join(target, ef)):
                        return sub, ef
                if os.path.isfile(os.path.join(target, "requirements.txt")):
                    # Has requirements.txt, check any .py file
                    py_files = [f for f in os.listdir(target) if f.endswith(".py") and not f.startswith("__")]
                    if py_files:
                        return sub, py_files[0]
                    return sub, "app.py"

        # 2. Check root directory
        for ef in self.ENTRY_FILES:
            if os.path.isfile(os.path.join(base_dir, ef)):
                return ".", ef

        if os.path.isfile(os.path.join(base_dir, "requirements.txt")):
            py_files = [f for f in os.listdir(base_dir) if f.endswith(".py") and not f.startswith("__")]
            if py_files:
                return ".", py_files[0]

        return None

    def can_detect(self, base_dir: str, context: Optional[Dict[str, Any]] = None) -> bool:
        return self._find_backend_dir(base_dir) is not None

    def detect(self, base_dir: str, context: Optional[Dict[str, Any]] = None) -> Optional[BackendSpec]:
        res = self._find_backend_dir(base_dir)
        if res is None:
            return None

        rel_dir, entry_file = res
        target_dir = os.path.join(base_dir, rel_dir)
        entry_path = os.path.join(target_dir, entry_file)
        module_name = entry_file[:-3] if entry_file.endswith(".py") else entry_file

        reqs_file = "requirements.txt" if os.path.isfile(os.path.join(target_dir, "requirements.txt")) else None

        # Inspect content of entry file to detect exact framework
        file_content = ""
        if os.path.isfile(entry_path):
            try:
                with open(entry_path, "r", encoding="utf-8", errors="ignore") as fh:
                    file_content = fh.read()
            except Exception:
                pass

        # 1. Streamlit
        if "streamlit" in file_content or (context and context.get("app_type") == "streamlit"):
            return BackendSpec(
                framework="streamlit",
                directory=rel_dir,
                entry_file=entry_file,
                module=module_name,
                dependencies_file=reqs_file,
                port=8000,
                api_prefix="/",
                dev_command=f"streamlit run {entry_file} --server.port 8000 --server.address 0.0.0.0 --server.headless true --server.enableCORS false",
            )

        # 2. FastAPI / Starlette
        if re.search(r"\b(FastAPI|Starlette)\b", file_content):
            return BackendSpec(
                framework="fastapi",
                directory=rel_dir,
                entry_file=entry_file,
                module=f"{module_name}:app",
                dependencies_file=reqs_file,
                port=8000,
                api_prefix="/api",
                dev_command=f"uvicorn {module_name}:app --host 0.0.0.0 --port 8000 --reload --reload-delay 1.0",
            )

        # 3. Flask
        if re.search(r"\b(Flask|flask)\b", file_content):
            return BackendSpec(
                framework="flask",
                directory=rel_dir,
                entry_file=entry_file,
                module=f"{module_name}:app",
                dependencies_file=reqs_file,
                port=8000,
                api_prefix="/api",
                dev_command=f"python3 {entry_file}",
            )

        # 4. Generic Python Web Service
        return BackendSpec(
            framework="generic-python",
            directory=rel_dir,
            entry_file=entry_file,
            module=f"{module_name}:app",
            dependencies_file=reqs_file,
            port=8000,
            api_prefix="/api",
            dev_command=f"uvicorn {module_name}:app --host 0.0.0.0 --port 8000 --reload 2>/dev/null || python3 {entry_file}",
        )
