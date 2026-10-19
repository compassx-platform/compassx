"""Frontend Detector - Identifies modern web UI frameworks and static sites.

Adheres to Single Responsibility Principle: Specialized exclusively in analyzing
client-side code structures, build configs, and package manifests.
"""

import os
import json
from typing import Optional, Dict, Any, List
from .base import BaseDetector
from .models import FrontendSpec


class FrontendDetector(BaseDetector):
    """Detects frontend web frameworks and entrypoints."""

    FRONTEND_DIR_CANDIDATES = ("frontend", "client", "web", "ui", "src", ".")

    def _find_frontend_dir(self, base_dir: str) -> Optional[str]:
        """Find the most likely directory housing frontend code."""
        # 1. Prefer dedicated frontend folders containing package.json
        for sub in ("frontend", "client", "web", "ui"):
            target = os.path.join(base_dir, sub)
            if os.path.isdir(target) and os.path.isfile(os.path.join(target, "package.json")):
                return sub

        # 2. Check root package.json
        if os.path.isfile(os.path.join(base_dir, "package.json")):
            return "."

        # 3. Check for static HTML (index.html) in dedicated subdirs or root
        for sub in ("frontend", "client", "web", "ui", "public", "."):
            target = os.path.join(base_dir, sub)
            if os.path.isdir(target) and os.path.isfile(os.path.join(target, "index.html")):
                return sub

        return None

    def can_detect(self, base_dir: str, context: Optional[Dict[str, Any]] = None) -> bool:
        return self._find_frontend_dir(base_dir) is not None

    def detect(self, base_dir: str, context: Optional[Dict[str, Any]] = None) -> Optional[FrontendSpec]:
        rel_dir = self._find_frontend_dir(base_dir)
        if rel_dir is None:
            return None

        target_dir = os.path.join(base_dir, rel_dir)
        pkg_path = os.path.join(target_dir, "package.json")

        if os.path.isfile(pkg_path):
            try:
                with open(pkg_path, "r", encoding="utf-8") as pf:
                    pkg_data = json.load(pf)
            except Exception:
                pkg_data = {}

            deps = {**pkg_data.get("dependencies", {}), **pkg_data.get("devDependencies", {})}
            scripts = pkg_data.get("scripts", {})

            # Detect Package Manager
            pm = "npm"
            if os.path.isfile(os.path.join(target_dir, "pnpm-lock.yaml")):
                pm = "pnpm"
            elif os.path.isfile(os.path.join(target_dir, "yarn.lock")):
                pm = "yarn"

            # 1. Next.js
            if "next" in deps:
                dev_cmd = "next dev -p 8080 -H 0.0.0.0" if pm == "npm" else f"{pm} run dev -- -p 8080 -H 0.0.0.0"
                if os.path.isfile(os.path.join(target_dir, "node_modules", ".bin", "next")):
                    dev_cmd = "./node_modules/.bin/next dev -p 8080 -H 0.0.0.0"
                return FrontendSpec(
                    framework="nextjs",
                    directory=rel_dir,
                    entry_file="pages" if os.path.isdir(os.path.join(target_dir, "pages")) else "app",
                    package_manager=pm,
                    port=8080,
                    dev_command=dev_cmd,
                    build_command=f"{pm} run build",
                    dist_dir=".next",
                )

            # 2. Vite (React, Vue, Svelte, Lit, Vanilla)
            has_vite_cfg = any(f.startswith("vite.config.") for f in os.listdir(target_dir)) if os.path.isdir(target_dir) else False
            if "vite" in deps or has_vite_cfg:
                fw = "vite"
                if "react" in deps:
                    fw = "vite-react"
                elif "vue" in deps:
                    fw = "vite-vue"
                elif "svelte" in deps:
                    fw = "vite-svelte"

                dev_cmd = "npx --yes vite --host 0.0.0.0 --port 8080 --cors"
                if os.path.isfile(os.path.join(target_dir, "node_modules", ".bin", "vite")):
                    dev_cmd = "./node_modules/.bin/vite --host 0.0.0.0 --port 8080 --cors"
                elif "dev" in scripts:
                    dev_cmd = f"{pm} run dev -- --host 0.0.0.0 --port 8080"

                return FrontendSpec(
                    framework=fw,
                    directory=rel_dir,
                    entry_file="index.html" if os.path.isfile(os.path.join(target_dir, "index.html")) else None,
                    package_manager=pm,
                    port=8080,
                    dev_command=dev_cmd,
                    build_command=f"{pm} run build",
                    dist_dir="dist",
                )

            # 3. Nuxt
            if "nuxt" in deps or "nuxt3" in deps:
                return FrontendSpec(
                    framework="nuxt",
                    directory=rel_dir,
                    package_manager=pm,
                    port=8080,
                    dev_command=f"{pm} run dev -- -p 8080 --host 0.0.0.0",
                    build_command=f"{pm} run build",
                    dist_dir=".output/public",
                )

            # 4. Standard Scripts ('dev' or 'start')
            if "dev" in scripts:
                return FrontendSpec(
                    framework="generic-npm",
                    directory=rel_dir,
                    package_manager=pm,
                    port=8080,
                    dev_command=f"{pm} run dev -- --host 0.0.0.0 --port 8080",
                    build_command=f"{pm} run build" if "build" in scripts else None,
                    dist_dir="dist" if os.path.isdir(os.path.join(target_dir, "dist")) else "build",
                )
            elif "start" in scripts:
                return FrontendSpec(
                    framework="generic-npm",
                    directory=rel_dir,
                    package_manager=pm,
                    port=8080,
                    dev_command=f"{pm} start -- -p 8080",
                    build_command=f"{pm} run build" if "build" in scripts else None,
                    dist_dir="build" if os.path.isdir(os.path.join(target_dir, "build")) else "dist",
                )

        # 5. Static HTML site fallback
        index_html = os.path.join(target_dir, "index.html")
        if os.path.isfile(index_html):
            return FrontendSpec(
                framework="static-html",
                directory=rel_dir,
                entry_file="index.html",
                package_manager="none",
                port=8080,
                dev_command=f"python3 -m http.server 8080 --directory {rel_dir if rel_dir != '.' else '.'}",
                build_command=None,
                dist_dir=rel_dir,
            )

        return None
