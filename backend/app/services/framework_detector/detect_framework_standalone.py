#!/usr/bin/env python3
"""Standalone, Zero-Dependency Framework Detector for CompassX.

Can be run in any Python 3 environment (containers, pods, VMs) without third-party dependencies.
Outputs standard JSON to stdout.

Usage:
    python3 detect_framework_standalone.py [directory]
"""

import os
import sys
import json
import re
import shlex


def safe_load_yaml(content):
    try:
        import yaml
        return yaml.safe_load(content)
    except Exception:
        pass
    res = {}
    cur_sec = None
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.endswith(":") and not (" " in line[:-1]):
            cur_sec = line[:-1]
            res[cur_sec] = {}
            continue
        if ":" in line:
            k, v = line.split(":", 1)
            k, v = k.strip(), v.strip().strip("'\"")
            if cur_sec and isinstance(res.get(cur_sec), dict):
                res[cur_sec][k] = v
            else:
                res[k] = v
    return res if res else None


def detect_manifest(base_dir):
    candidates = ["app.yaml", "app.yml", ".compassx/app.yaml", ".compassx/app.yml"]
    for c in candidates:
        p = os.path.join(base_dir, c)
        if os.path.isfile(p):
            try:
                with open(p, "r", encoding="utf-8") as fh:
                    d = safe_load_yaml(fh.read())
                    if isinstance(d, dict):
                        return p, d
            except Exception:
                pass
    return None, None


def detect_frontend(base_dir):
    # Check candidates
    target_rel = None
    for sub in ["frontend", "client", "web", "ui"]:
        t = os.path.join(base_dir, sub)
        if os.path.isdir(t) and os.path.isfile(os.path.join(t, "package.json")):
            target_rel = sub
            break
    if not target_rel and os.path.isfile(os.path.join(base_dir, "package.json")):
        target_rel = "."

    if not target_rel:
        for sub in ["frontend", "client", "web", "ui", "public", "."]:
            t = os.path.join(base_dir, sub)
            if os.path.isdir(t) and os.path.isfile(os.path.join(t, "index.html")):
                return {
                    "framework": "static-html",
                    "directory": sub,
                    "entry_file": "index.html",
                    "package_manager": "none",
                    "port": 8080,
                    "dev_command": f"python3 -m http.server 8080 --directory {sub}",
                    "build_command": None,
                    "dist_dir": sub,
                }
        return None

    tdir = os.path.join(base_dir, target_rel)
    pkg_p = os.path.join(tdir, "package.json")
    pkg = {}
    if os.path.isfile(pkg_p):
        try:
            with open(pkg_p, "r", encoding="utf-8") as pf:
                pkg = json.load(pf)
        except Exception:
            pass

    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    scripts = pkg.get("scripts", {})
    pm = "pnpm" if os.path.isfile(os.path.join(tdir, "pnpm-lock.yaml")) else ("yarn" if os.path.isfile(os.path.join(tdir, "yarn.lock")) else "npm")

    if "next" in deps:
        cmd = "./node_modules/.bin/next dev -p 8080 -H 0.0.0.0" if os.path.isfile(os.path.join(tdir, "node_modules", ".bin", "next")) else "npx next dev -p 8080 -H 0.0.0.0"
        return {
            "framework": "nextjs",
            "directory": target_rel,
            "entry_file": "pages" if os.path.isdir(os.path.join(tdir, "pages")) else "app",
            "package_manager": pm,
            "port": 8080,
            "dev_command": cmd,
            "build_command": f"{pm} run build",
            "dist_dir": ".next",
        }

    has_vite = any(f.startswith("vite.config.") for f in os.listdir(tdir)) if os.path.isdir(tdir) else False
    if "vite" in deps or has_vite:
        fw = "vite-react" if "react" in deps else ("vite-vue" if "vue" in deps else "vite")
        cmd = "./node_modules/.bin/vite --host 0.0.0.0 --port 8080 --cors" if os.path.isfile(os.path.join(tdir, "node_modules", ".bin", "vite")) else f"{pm} run dev -- --host 0.0.0.0 --port 8080"
        return {
            "framework": fw,
            "directory": target_rel,
            "entry_file": "index.html" if os.path.isfile(os.path.join(tdir, "index.html")) else None,
            "package_manager": pm,
            "port": 8080,
            "dev_command": cmd,
            "build_command": f"{pm} run build",
            "dist_dir": "dist",
        }

    if "dev" in scripts:
        return {
            "framework": "generic-npm",
            "directory": target_rel,
            "package_manager": pm,
            "port": 8080,
            "dev_command": f"{pm} run dev -- --host 0.0.0.0 --port 8080",
            "build_command": f"{pm} run build" if "build" in scripts else None,
            "dist_dir": "dist" if os.path.isdir(os.path.join(tdir, "dist")) else "build",
        }
    elif "start" in scripts:
        return {
            "framework": "generic-npm",
            "directory": target_rel,
            "package_manager": pm,
            "port": 8080,
            "dev_command": f"{pm} start -- -p 8080",
            "build_command": f"{pm} run build" if "build" in scripts else None,
            "dist_dir": "build" if os.path.isdir(os.path.join(tdir, "build")) else "dist",
        }

    return None


def detect_backend(base_dir):
    entry_files = ["main.py", "app.py", "server.py", "api.py"]
    target_rel = None
    target_ef = None
    for sub in ["backend", "api", "server"]:
        t = os.path.join(base_dir, sub)
        if os.path.isdir(t):
            for ef in entry_files:
                if os.path.isfile(os.path.join(t, ef)):
                    target_rel, target_ef = sub, ef
                    break
            if target_rel:
                break
            if os.path.isfile(os.path.join(t, "requirements.txt")):
                py_files = [f for f in os.listdir(t) if f.endswith(".py") and not f.startswith("__")]
                target_rel, target_ef = sub, (py_files[0] if py_files else "app.py")
                break

    if not target_rel:
        for ef in entry_files:
            if os.path.isfile(os.path.join(base_dir, ef)):
                target_rel, target_ef = ".", ef
                break
        if not target_rel and os.path.isfile(os.path.join(base_dir, "requirements.txt")):
            py_files = [f for f in os.listdir(base_dir) if f.endswith(".py") and not f.startswith("__")]
            if py_files:
                target_rel, target_ef = ".", py_files[0]

    if not target_rel:
        return None

    tdir = os.path.join(base_dir, target_rel)
    ef_path = os.path.join(tdir, target_ef)
    mod_name = target_ef[:-3] if target_ef.endswith(".py") else target_ef
    reqs = "requirements.txt" if os.path.isfile(os.path.join(tdir, "requirements.txt")) else None

    content = ""
    if os.path.isfile(ef_path):
        try:
            with open(ef_path, "r", encoding="utf-8", errors="ignore") as fh:
                content = fh.read()
        except Exception:
            pass

    if "streamlit" in content:
        return {
            "framework": "streamlit",
            "directory": target_rel,
            "entry_file": target_ef,
            "module": mod_name,
            "dependencies_file": reqs,
            "port": 8000,
            "api_prefix": "/",
            "dev_command": f"streamlit run {target_ef} --server.port 8000 --server.address 0.0.0.0 --server.headless true --server.enableCORS false",
        }

    if re.search(r"\b(FastAPI|Starlette)\b", content):
        return {
            "framework": "fastapi",
            "directory": target_rel,
            "entry_file": target_ef,
            "module": f"{mod_name}:app",
            "dependencies_file": reqs,
            "port": 8000,
            "api_prefix": "/api",
            "dev_command": f"uvicorn {mod_name}:app --host 0.0.0.0 --port 8000 --reload --reload-delay 1.0",
        }

    if re.search(r"\b(Flask|flask)\b", content):
        return {
            "framework": "flask",
            "directory": target_rel,
            "entry_file": target_ef,
            "module": f"{mod_name}:app",
            "dependencies_file": reqs,
            "port": 8000,
            "api_prefix": "/api",
            "dev_command": f"python3 {target_ef}",
        }

    return {
        "framework": "generic-python",
        "directory": target_rel,
        "entry_file": target_ef,
        "module": f"{mod_name}:app",
        "dependencies_file": reqs,
        "port": 8000,
        "api_prefix": "/api",
        "dev_command": f"uvicorn {mod_name}:app --host 0.0.0.0 --port 8000 --reload 2>/dev/null || python3 {target_ef}",
    }


def run_detection(target_dir):
    try:
        target_dir = os.path.abspath(target_dir)
        if not os.path.exists(target_dir):
            return {
                "detected": False,
                "app_type": "unknown",
                "error": {
                    "code": "DIRECTORY_NOT_FOUND",
                    "title": "Directory Not Found",
                    "message": f"Path does not exist: {target_dir}",
                },
                "recommendations": ["Check workspace path."],
            }

        # Resolve base dir
        base_dir = target_dir
        try:
            subdirs = [d for d in os.listdir(target_dir) if os.path.isdir(os.path.join(target_dir, d)) and d not in (".git", "node_modules", ".cache")]
            if len(subdirs) == 1:
                single_sub = os.path.join(target_dir, subdirs[0])
                if any(os.path.isfile(os.path.join(single_sub, f)) for f in ("package.json", "app.py", "main.py", "requirements.txt", "app.yaml")):
                    base_dir = single_sub
        except Exception:
            pass

        files_scanned = 0
        EXCLUDED_DIRS = {".git", "node_modules", ".cache", "__pycache__", ".venv", "venv", "env", ".idea", ".vscode"}
        for root, dirs, files in os.walk(base_dir):
            dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
            files_scanned += len(files)

        # 1. Manifest
        manifest_p, manifest_d = detect_manifest(base_dir)
        manifest_spec = None
        frontend_spec = None
        backend_spec = None

        if manifest_d:
            rel_m_dir = os.path.relpath(os.path.dirname(manifest_p), base_dir) if os.path.dirname(manifest_p) != base_dir else "."
            manifest_spec = {
                "path": os.path.relpath(manifest_p, base_dir),
                "install_command": manifest_d.get("install"),
                "env": manifest_d.get("env") or {},
                "services": manifest_d.get("services") or {},
            }
            services = manifest_d.get("services") or {}
            if isinstance(services, dict) and services:
                b_svc = services.get("backend") or services.get("api")
                if b_svc:
                    b_cmd = b_svc.get("command") if isinstance(b_svc, dict) else str(b_svc)
                    backend_spec = {
                        "framework": "manifest-backend",
                        "directory": b_svc.get("dir", rel_m_dir) if isinstance(b_svc, dict) else rel_m_dir,
                        "port": int(b_svc.get("port", 8000)) if isinstance(b_svc, dict) else 8000,
                        "api_prefix": b_svc.get("path", "/api") if isinstance(b_svc, dict) else "/api",
                        "dev_command": b_cmd if isinstance(b_cmd, str) else " ".join([shlex.quote(str(x)) for x in b_cmd]),
                    }
                f_svc = services.get("frontend") or services.get("ui") or services.get("web")
                if f_svc:
                    f_cmd = f_svc.get("command") if isinstance(f_svc, dict) else str(f_svc)
                    frontend_spec = {
                        "framework": "manifest-frontend",
                        "directory": f_svc.get("dir", rel_m_dir) if isinstance(f_svc, dict) else rel_m_dir,
                        "port": int(f_svc.get("port", 8080)) if isinstance(f_svc, dict) else 8080,
                        "dev_command": f_cmd if isinstance(f_cmd, str) else " ".join([shlex.quote(str(x)) for x in f_cmd]),
                    }

        if not frontend_spec:
            frontend_spec = detect_frontend(base_dir)
        if not backend_spec:
            backend_spec = detect_backend(base_dir)

        has_f = frontend_spec is not None
        has_b = backend_spec is not None
        has_m = manifest_spec is not None
        detected = has_f or has_b or has_m

        if has_m and not has_f and not has_b:
            app_type = "custom-manifest"
        elif has_f and has_b:
            app_type = "fullstack"
        elif has_f:
            app_type = "static-html" if frontend_spec.get("framework") == "static-html" else "frontend-only"
        elif has_b:
            app_type = "backend-only"
        else:
            app_type = "unknown"

        error = None
        recommendations = []
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

        return {
            "detected": detected,
            "app_type": app_type,
            "has_frontend": has_f,
            "has_backend": has_b,
            "manifest_found": has_m,
            "frontend": frontend_spec,
            "backend": backend_spec,
            "manifest": manifest_spec,
            "diagnostics": {
                "inspected_dir": base_dir,
                "target_dir": target_dir,
                "files_scanned": files_scanned,
                "is_empty": files_scanned == 0,
            },
            "error": error,
            "recommendations": recommendations,
        }
    except Exception as exc:
        return {
            "detected": False,
            "app_type": "unknown",
            "has_frontend": False,
            "has_backend": False,
            "manifest_found": False,
            "frontend": None,
            "backend": None,
            "manifest": None,
            "diagnostics": {"inspected_dir": target_dir, "exception": str(exc)},
            "error": {
                "code": "DETECTION_ERROR",
                "title": "Framework Detection Error",
                "message": f"An error occurred while inspecting repository: {str(exc)}",
            },
            "recommendations": ["Check repository structure and file permissions."],
        }


if __name__ == "__main__":
    t = sys.argv[1] if len(sys.argv) > 1 else "."
    print(json.dumps(run_detection(t), indent=2))
