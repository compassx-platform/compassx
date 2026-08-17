"""Pod provisioning service for CompassX Apps.

Manages branch-preview pods and production pods.
Each pod runs three supervised processes via supervisord:
  1. uvicorn main:app --reload  (FastAPI backend, port 8000)
  2. vite dev server            (React frontend, port 5173)
  3. pi-agent in RPC/SDK mode  (Pi coding agent, port 9000, localhost-only)

A Caddy reverse proxy routes:
  /api/*    → uvicorn (port 8000)
  /agent/*  → pi-agent (port 9000, not exposed externally)
  /*        → vite (port 5173)
"""

import hashlib
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.apps.models.apps import App, AppBranch, AppCommit, AppPod

logger = logging.getLogger(__name__)

# Fixed scaffold structure (§5 — no flexibility in v1)
SCAFFOLD_FILES = {
    "backend/main.py": '''\
"""CompassX App — FastAPI backend entry point."""
from fastapi import FastAPI

app = FastAPI()


@app.get("/api/hello")
def hello():
    return {"message": "Hello from CompassX App!"}
''',
    "backend/requirements.txt": "fastapi\nuvicorn[standard]\n",
    "frontend/package.json": '''\
{
  "name": "compassx-app",
  "version": "0.1.0",
  "scripts": {
    "dev": "vite"
  },
  "dependencies": {
    "react": "^18.0.0",
    "react-dom": "^18.0.0"
  },
  "devDependencies": {
    "vite": "^5.0.0",
    "@vitejs/plugin-react": "^4.0.0"
  }
}
''',
    "frontend/vite.config.ts": '''\
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});
''',
    "frontend/src/main.tsx": '''\
import React from "react";
import ReactDOM from "react-dom/client";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <h1>CompassX App</h1>
  </React.StrictMode>
);
''',
    "frontend/index.html": '''\
<!DOCTYPE html>
<html lang="en">
  <head><meta charset="UTF-8" /><title>CompassX App</title></head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
''',
}

# Supervisord config template rendered into the pod's ConfigMap
SUPERVISORD_CONF = """\
[supervisord]
nodaemon=true
logfile=/dev/null
logfile_maxbytes=0

[program:backend]
command=uvicorn main:app --reload --host 0.0.0.0 --port 8000
directory=/workspace/backend
autostart=true
autorestart=true
stdout_logfile=/dev/stdout
stdout_logfile_maxbytes=0
stderr_logfile=/dev/stderr
stderr_logfile_maxbytes=0

[program:frontend]
command=npx vite --host 0.0.0.0 --port 5173
directory=/workspace/frontend
autostart=true
autorestart=true
stdout_logfile=/dev/stdout
stdout_logfile_maxbytes=0
stderr_logfile=/dev/stderr
stderr_logfile_maxbytes=0

[program:pi-agent]
command=pi-agent --rpc-port=9000
directory=/workspace
autostart=true
autorestart=true
stdout_logfile=/dev/stdout
stdout_logfile_maxbytes=0
stderr_logfile=/dev/stderr
stderr_logfile_maxbytes=0
"""

CADDYFILE = """\
:80 {
    handle /api/* {
        reverse_proxy localhost:8000
    }
    handle /agent/* {
        reverse_proxy localhost:9000
    }
    handle {
        reverse_proxy localhost:5173
    }
}
"""


def _lockfile_hash(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


class PodService:
    """Provisions and manages branch-preview and production pods in Kubernetes."""

    def __init__(self, db: Session):
        self._db = db

    # ------------------------------------------------------------------
    # Branch cap enforcement (§5)
    # ------------------------------------------------------------------

    def check_branch_cap(self, app_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Raise ValueError if user is at the branch cap for this app."""
        app: Optional[App] = self._db.query(App).filter(App.app_id == app_id).one_or_none()
        if app is None:
            raise ValueError(f"App {app_id} not found")

        active_count = (
            self._db.query(AppBranch)
            .filter(AppBranch.app_id == app_id, AppBranch.created_by == user_id)
            .count()
        )
        if active_count >= app.max_concurrent_branches:
            raise ValueError(
                f"Branch cap reached: you already have {active_count} active branches "
                f"for this app (max {app.max_concurrent_branches}). "
                "Delete an existing branch before creating a new one."
            )

    # ------------------------------------------------------------------
    # Branch pod provisioning
    # ------------------------------------------------------------------

    async def provision_branch_pod(
        self,
        app_id: uuid.UUID,
        branch_id: uuid.UUID,
        commit_id: Optional[uuid.UUID],
        scoped_token: str,
        terminal_enabled: bool = True,
    ) -> AppPod:
        """Create a Kubernetes pod for a branch-preview environment."""
        k8s_name = f"app-{app_id}-branch-{branch_id}".replace("-", "")[:63]
        preview_url = f"/pods/{k8s_name}"

        pod = AppPod(
            app_id=app_id,
            branch_id=branch_id,
            pod_kind="branch",
            k8s_pod_name=k8s_name,
            preview_url=preview_url,
            terminal_enabled=terminal_enabled,
            status="starting",
            commit_id=commit_id,
        )
        self._db.add(pod)
        self._db.flush()

        await self._create_k8s_pod(
            pod=pod,
            scoped_token=scoped_token,
            namespace="compassx-apps",
        )
        logger.info("Branch pod provisioned: %s (app=%s branch=%s)", k8s_name, app_id, branch_id)
        return pod

    # ------------------------------------------------------------------
    # Production pod provisioning
    # ------------------------------------------------------------------

    async def provision_production_pod(
        self,
        app_id: uuid.UUID,
        commit_id: uuid.UUID,
        scoped_token: str,
    ) -> AppPod:
        """Create a dedicated production pod. Never reuses a branch-preview pod."""
        app: App = self._db.query(App).filter(App.app_id == app_id).one()
        k8s_name = f"app-{app_id}-prod-{uuid.uuid4().hex[:8]}"[:63]
        preview_url = f"/pods/{k8s_name}"

        pod = AppPod(
            app_id=app_id,
            branch_id=None,
            pod_kind="production",
            k8s_pod_name=k8s_name,
            preview_url=preview_url,
            terminal_enabled=app.terminal_enabled_prod,
            status="starting",
            commit_id=commit_id,
        )
        self._db.add(pod)
        self._db.flush()

        await self._create_k8s_pod(
            pod=pod,
            scoped_token=scoped_token,
            namespace="compassx-apps",
        )
        logger.info("Production pod provisioned: %s (app=%s commit=%s)", k8s_name, app_id, commit_id)
        return pod

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    async def wait_for_ready(self, pod: AppPod, timeout_seconds: int = 120) -> bool:
        """Poll pod health endpoint until ready or timeout. Updates pod.status."""
        import asyncio, httpx
        deadline = datetime.now(timezone.utc).timestamp() + timeout_seconds
        url = f"http://{pod.k8s_pod_name}.compassx-apps.svc.cluster.local/api/healthcheck"

        async with httpx.AsyncClient(timeout=5.0) as client:
            while datetime.now(timezone.utc).timestamp() < deadline:
                try:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        pod.status = "running"
                        self._db.flush()
                        return True
                except Exception:
                    pass
                await asyncio.sleep(3)

        pod.status = "failed"
        self._db.flush()
        return False

    # ------------------------------------------------------------------
    # Terminate pod
    # ------------------------------------------------------------------

    async def terminate_pod(self, pod_id: uuid.UUID) -> None:
        """Mark pod as terminated and delete K8s resource."""
        pod: Optional[AppPod] = self._db.query(AppPod).filter(AppPod.pod_id == pod_id).one_or_none()
        if pod is None:
            return
        pod.status = "terminated"
        self._db.flush()
        await self._delete_k8s_pod(pod.k8s_pod_name, namespace="compassx-apps")
        logger.info("Pod terminated: %s", pod.k8s_pod_name)

    # ------------------------------------------------------------------
    # K8s helpers (thin wrappers — use kubernetes-asyncio in production)
    # ------------------------------------------------------------------

    async def _create_k8s_pod(self, pod: AppPod, scoped_token: str, namespace: str) -> None:
        """Submit the pod manifest to Kubernetes.

        In production this calls the kubernetes-asyncio client.
        The pod spec includes:
          - Base image with Python, Node, supervisord, Caddy, pi-agent
          - Env vars: SCOPED_TOKEN, APP_ID, BRANCH_ID
          - Shared dependency cache PVC mounted at /dep-cache
          - App source PVC mounted at /workspace (or init container materializes from blob)
          - Supervisor config and Caddyfile mounted via ConfigMap
          - Terminal enabled/disabled via env var
        """
        try:
            from kubernetes_asyncio import client as k8s_client, config as k8s_config
            await k8s_config.load_incluster_config()
            v1 = k8s_client.CoreV1Api()

            pod_manifest = {
                "apiVersion": "v1",
                "kind": "Pod",
                "metadata": {
                    "name": pod.k8s_pod_name,
                    "namespace": namespace,
                    "labels": {
                        "app": "compassx-app-pod",
                        "app_id": str(pod.app_id),
                        "pod_kind": pod.pod_kind,
                    },
                },
                "spec": {
                    "restartPolicy": "Always",
                    "containers": [{
                        "name": "app",
                        "image": "compassx/apps-base:latest",
                        "command": ["supervisord", "-c", "/etc/supervisord.conf"],
                        "env": [
                            {"name": "SCOPED_TOKEN", "value": scoped_token},
                            {"name": "APP_ID", "value": str(pod.app_id)},
                            {"name": "TERMINAL_ENABLED", "value": str(pod.terminal_enabled).lower()},
                        ],
                        "ports": [{"containerPort": 80}],
                        "volumeMounts": [
                            {"name": "supervisor-config", "mountPath": "/etc/supervisord.conf", "subPath": "supervisord.conf"},
                            {"name": "caddy-config", "mountPath": "/etc/caddy/Caddyfile", "subPath": "Caddyfile"},
                            {"name": "dep-cache", "mountPath": "/dep-cache"},
                            {"name": "workspace", "mountPath": "/workspace"},
                        ],
                    }],
                    "volumes": [
                        {"name": "supervisor-config", "configMap": {"name": "apps-supervisor-config"}},
                        {"name": "caddy-config", "configMap": {"name": "apps-caddy-config"}},
                        {"name": "dep-cache", "persistentVolumeClaim": {"claimName": "apps-dep-cache"}},
                        {"name": "workspace", "emptyDir": {}},
                    ],
                },
            }
            await v1.create_namespaced_pod(namespace=namespace, body=pod_manifest)
        except ImportError:
            logger.warning("kubernetes_asyncio not installed — skipping K8s pod creation (dev mode)")
        except Exception as exc:
            logger.error("Failed to create K8s pod %s: %s", pod.k8s_pod_name, exc)
            raise

    async def _delete_k8s_pod(self, k8s_pod_name: str, namespace: str) -> None:
        try:
            from kubernetes_asyncio import client as k8s_client, config as k8s_config
            await k8s_config.load_incluster_config()
            v1 = k8s_client.CoreV1Api()
            await v1.delete_namespaced_pod(name=k8s_pod_name, namespace=namespace)
        except ImportError:
            logger.warning("kubernetes_asyncio not installed — skipping K8s pod deletion (dev mode)")
        except Exception as exc:
            logger.warning("Failed to delete K8s pod %s: %s", k8s_pod_name, exc)
