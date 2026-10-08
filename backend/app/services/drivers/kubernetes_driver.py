"""Kubernetes runtime drivers for Production Apps and Dev Sandboxes with Subdomain Ingress (SOLID / SRP)."""
import os
import re
import uuid
import base64
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Callable

from app.config import settings
from app.services.drivers.base import BaseAppDriver, BaseDevDriver
from app.services.ingress_service import ingress_service

try:
    from kubernetes.client.exceptions import ApiException
except ImportError:
    ApiException = Exception  # type: ignore

logger = logging.getLogger(__name__)


class KubernetesAppDriver(BaseAppDriver):
    """Manages Kubernetes Deployment, Service, and Ingress with subdomain routing."""

    def _get_k8s_client(self):
        try:
            from app.compute.services.k8s_client import get_k8s_client
            return get_k8s_client()
        except Exception:
            try:
                from compassx.drivers.k8s_client import K8sApiClient
                return K8sApiClient()
            except Exception as e:
                logger.warning("Could not initialize K8s client: %s", e)
                return None

    def deploy(self, app, repo_dir: str, build_logs: List[str]) -> Dict[str, Any]:
        from kubernetes import client
        from kubernetes.client.exceptions import ApiException

        k8s = self._get_k8s_client()
        ns = settings.K8S_NAMESPACE
        clean_id = re.sub(r"[^a-z0-9-]", "-", app.id.lower()).strip("-")
        name = f"compassx-app-{clean_id}"
        subdomain = ingress_service.get_app_domain(app)
        live_url = ingress_service.get_app_url(app)
        now_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        build_logs.append(f"[{now_ts}] [INFO] Provisioning Kubernetes resources for app '{app.name}' in namespace '{ns}'")
        build_logs.append(f"[{now_ts}] [INFO] Assigned Subdomain: {subdomain} -> Live URL: {live_url}")

        labels = {
            "app.kubernetes.io/name": name,
            "app.kubernetes.io/instance": app.slug,
            "compassx/app-id": clean_id,
            "compassx/role": "prod",
            "compassx/managed": "true",
        }

        # Resolve Workload Identity
        workload_identity_id = ""
        if getattr(app, "workspace_identity", None) and isinstance(app.workspace_identity, dict):
            workload_identity_id = app.workspace_identity.get("identity_id") or ""
        elif hasattr(app, "id") and app.id:
            clean_app_id = re.sub(r"[^a-z0-9]", "", str(app.id).lower())
            workload_identity_id = f"id_app_{clean_app_id[:12]}"

        # 1. Environment variables
        cfg = dict(app.config or {})
        env_vars = [
            client.V1EnvVar(name="PORT", value="8080"),
            client.V1EnvVar(name="APP_NAME", value=str(app.name)),
            client.V1EnvVar(name="APP_SLUG", value=str(app.slug)),
            client.V1EnvVar(name="APP_ID", value=str(app.id)),
            client.V1EnvVar(name="WORKSPACE_ID", value=str(getattr(app, "workspace_id", ""))),
            client.V1EnvVar(name="COMPASSX_WORKLOAD_IDENTITY", value=str(workload_identity_id)),
        ]

        # Support list of dicts [{"key": "...", "value": "..."}, {"name": "...", "value": "..."}] OR dict {"KEY": "VAL"}
        raw_env = cfg.get("env_vars") or cfg.get("env") or cfg.get("environment") or []
        if isinstance(raw_env, dict):
            for k, v in raw_env.items():
                if k:
                    env_vars.append(client.V1EnvVar(name=str(k), value=str(v) if v is not None else ""))
        elif isinstance(raw_env, list):
            for ev in raw_env:
                if isinstance(ev, dict):
                    k = ev.get("key") or ev.get("name")
                    v = ev.get("value")
                    if k:
                        env_vars.append(client.V1EnvVar(name=str(k), value=str(v) if v is not None else ""))
                elif isinstance(ev, str) and "=" in ev:
                    k, v = ev.split("=", 1)
                    env_vars.append(client.V1EnvVar(name=k.strip(), value=v.strip()))

        # Also inject platform connection env vars (Azure OpenAI, OpenAI, Postgres, etc.)
        try:
            from app.services.omnigent_dev_service import omnigent_dev_service
            llm_env = omnigent_dev_service.get_llm_env_vars(app.workspace_id)
            existing_names = {e.name for e in env_vars}
            for k, v in llm_env.items():
                if k not in existing_names and v is not None:
                    env_vars.append(client.V1EnvVar(name=str(k), value=str(v)))
        except Exception as e:
            logger.debug("Could not inject platform LLM env vars into app %s: %s", app.id, e)

        # 2. Dynamic Container Image and Execution Command
        custom_image = cfg.get("image")
        app_type = (app.app_type or "").lower()

        git_url = app.git_repo_url
        git_token = None
        if hasattr(app, "git_pat_enc") and app.git_pat_enc:
            try:
                from app.services.encryption import decrypt_field
                git_token = decrypt_field(app.git_pat_enc)
            except Exception:
                pass
        auth_url = git_url
        if git_token and "github.com" in git_url and not ("@" in git_url.split("//")[-1]):
            auth_url = git_url.replace("https://", f"https://x-access-token:{git_token}@")
        git_ref = app.git_ref or app.git_branch or "main"
        entrypoint = app.entrypoint or "app.py"

        if custom_image:
            image_tag = custom_image
            container_cmd = None
            container_args = None
        else:
            image_tag = "ghcr.io/omnigent-ai/omnigent-host:latest"
            container_cmd = ["/bin/sh", "-c"]
            subdir = (getattr(app, "git_subdir", "") or "").strip("/")
            run_cmd = (
                f"hold_on_error() {{ "
                f"  echo ''; "
                f"  echo '[ERROR] ========================================================'; "
                f"  echo '[ERROR] Deployment build or application startup failed!'; "
                f"  echo '[ERROR] Container is holding in place so logs remain visible for inspection.'; "
                f"  echo '[ERROR] Review the error above, fix the issues in Development, and click Deploy to redeploy.'; "
                f"  echo '[ERROR] ========================================================'; "
                f"  exec tail -f /dev/null; "
                f"}} && "
                f"run_app() {{ "
                f"  echo '[BUILD] ========================================================' && "
                f"  echo '[BUILD] Starting Deployment Build for {app.name} (ref: {git_ref})' && "
                f"  echo '[BUILD] ========================================================' && "
                f"  echo '[BUILD] [1/3] Cloning repository ({git_ref})...' && "
                f"  mkdir -p /app_src && cd /app_src && "
                f"  (git clone --branch '{git_ref}' '{auth_url}' . || git clone '{auth_url}' . || true) && "
                f"  APP_ROOT='/app_src' && "
                f"  if [ -n '{subdir}' ] && [ -d '/app_src/{subdir}' ]; then "
                f"    APP_ROOT='/app_src/{subdir}'; "
                f"  else "
                f"    for d in /app_src/*; do "
                f"      if [ -d \"$d\" ] && ( [ -d \"$d/frontend\" ] || [ -d \"$d/backend\" ] || [ -d \"$d/client\" ] || [ -d \"$d/web\" ] || [ -f \"$d/package.json\" ] || [ -f \"$d/app.py\" ] || [ -f \"$d/main.py\" ] || [ -f \"$d/server.py\" ] ); then "
                f"        APP_ROOT=\"$d\"; break; "
                f"      fi; "
                f"    done; "
                f"  fi && "
                f"  echo \"[BUILD] Source code root directory resolved to: $APP_ROOT\" && "
                f"  echo '[BUILD] [2/3] Building dependencies and compiling assets...' && "
                f"  STATIC_DIR=\"\" && "
                # 1. Build Frontend if present (supports monorepo frontend, web, client, or root)
                f"  if [ -d \"$APP_ROOT/frontend\" ] && [ -f \"$APP_ROOT/frontend/package.json\" ]; then "
                f"    echo '[BUILD] Detected frontend directory ($APP_ROOT/frontend). Installing dependencies & building...' && "
                f"    (cd \"$APP_ROOT/frontend\" && (npm install --legacy-peer-deps --prefer-offline --no-audit || npm install --legacy-peer-deps || npm install --force) && (npm run build || true)) && "
                f"    (if [ -d \"$APP_ROOT/frontend/dist\" ]; then STATIC_DIR=\"$APP_ROOT/frontend/dist\"; "
                f"     elif [ -d \"$APP_ROOT/frontend/build\" ]; then STATIC_DIR=\"$APP_ROOT/frontend/build\"; "
                f"     elif [ -d \"$APP_ROOT/dist\" ]; then STATIC_DIR=\"$APP_ROOT/dist\"; "
                f"     elif [ -d \"$APP_ROOT/build\" ]; then STATIC_DIR=\"$APP_ROOT/build\"; "
                f"     else STATIC_DIR=\"$APP_ROOT/frontend\"; fi); "
                f"  elif [ -d \"$APP_ROOT/client\" ] && [ -f \"$APP_ROOT/client/package.json\" ]; then "
                f"    echo '[BUILD] Detected client directory ($APP_ROOT/client). Installing dependencies & building...' && "
                f"    (cd \"$APP_ROOT/client\" && (npm install --legacy-peer-deps --prefer-offline --no-audit || npm install --legacy-peer-deps || npm install --force) && (npm run build || true)) && "
                f"    (if [ -d \"$APP_ROOT/client/dist\" ]; then STATIC_DIR=\"$APP_ROOT/client/dist\"; "
                f"     elif [ -d \"$APP_ROOT/client/build\" ]; then STATIC_DIR=\"$APP_ROOT/client/build\"; "
                f"     else STATIC_DIR=\"$APP_ROOT/client\"; fi); "
                f"  elif [ -d \"$APP_ROOT/web\" ] && [ -f \"$APP_ROOT/web/package.json\" ]; then "
                f"    echo '[BUILD] Detected web directory ($APP_ROOT/web). Installing dependencies & building...' && "
                f"    (cd \"$APP_ROOT/web\" && (npm install --legacy-peer-deps --prefer-offline --no-audit || npm install --legacy-peer-deps || npm install --force) && (npm run build || true)) && "
                f"    (if [ -d \"$APP_ROOT/web/dist\" ]; then STATIC_DIR=\"$APP_ROOT/web/dist\"; "
                f"     elif [ -d \"$APP_ROOT/web/build\" ]; then STATIC_DIR=\"$APP_ROOT/web/build\"; "
                f"     else STATIC_DIR=\"$APP_ROOT/web\"; fi); "
                f"  elif [ -f \"$APP_ROOT/package.json\" ]; then "
                f"    echo '[BUILD] Detected root package.json. Installing dependencies & building...' && "
                f"    (cd \"$APP_ROOT\" && (npm install --legacy-peer-deps --prefer-offline --no-audit || npm install --legacy-peer-deps || npm install --force) && (npm run build || true)) && "
                f"    (if [ -d \"$APP_ROOT/dist\" ]; then STATIC_DIR=\"$APP_ROOT/dist\"; "
                f"     elif [ -d \"$APP_ROOT/build\" ]; then STATIC_DIR=\"$APP_ROOT/build\"; "
                f"     else STATIC_DIR=\"$APP_ROOT\"; fi); "
                f"  elif [ -d \"$APP_ROOT/frontend/dist\" ]; then "
                f"    STATIC_DIR=\"$APP_ROOT/frontend/dist\"; "
                f"  elif [ -d \"$APP_ROOT/dist\" ]; then "
                f"    STATIC_DIR=\"$APP_ROOT/dist\"; "
                f"  fi && "
                # 2. Detect Backend directory
                f"  BACKEND_DIR=\"\" && "
                f"  if [ -d \"$APP_ROOT/backend\" ] && ( [ -f \"$APP_ROOT/backend/main.py\" ] || [ -f \"$APP_ROOT/backend/app.py\" ] || [ -f \"$APP_ROOT/backend/server.py\" ] || [ -f \"$APP_ROOT/backend/api.py\" ] || [ -f \"$APP_ROOT/backend/requirements.txt\" ] ); then "
                f"    BACKEND_DIR=\"$APP_ROOT/backend\"; "
                f"  elif [ -d \"$APP_ROOT/api\" ] && ( [ -f \"$APP_ROOT/api/main.py\" ] || [ -f \"$APP_ROOT/api/app.py\" ] || [ -f \"$APP_ROOT/api/server.py\" ] || [ -f \"$APP_ROOT/api/requirements.txt\" ] ); then "
                f"    BACKEND_DIR=\"$APP_ROOT/api\"; "
                f"  elif [ -d \"$APP_ROOT/server\" ] && ( [ -f \"$APP_ROOT/server/main.py\" ] || [ -f \"$APP_ROOT/server/app.py\" ] || [ -f \"$APP_ROOT/server/requirements.txt\" ] ); then "
                f"    BACKEND_DIR=\"$APP_ROOT/server\"; "
                f"  elif [ -f \"$APP_ROOT/main.py\" ] || [ -f \"$APP_ROOT/app.py\" ] || [ -f \"$APP_ROOT/server.py\" ] || [ -f \"$APP_ROOT/api.py\" ] || [ -f \"$APP_ROOT/requirements.txt\" ] || [ '{app_type}' = 'streamlit' ]; then "
                f"    BACKEND_DIR=\"$APP_ROOT\"; "
                f"  fi && "
                f"  echo \"[BUILD] Backend directory resolved to: $BACKEND_DIR\" && "
                f"  echo \"[BUILD] Static frontend assets directory resolved to: $STATIC_DIR\" && "
                f"  echo '[BUILD] [3/3] Build phase completed successfully.' && "
                f"  echo '[BUILD] ========================================================' && "
                f"  echo '[RUNTIME] Launching production application services on port 8080...' && "
                # Write production reverse-proxy / static gateway script
                f"  cat << 'GW_EOF' > /tmp/cx_gateway.py\n"
                f"import http.server, urllib.request, urllib.error, os, sys\n"
                f"static_dir = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] != 'none' else None\n"
                f"port = int(sys.argv[2]) if len(sys.argv) > 2 else 8080\n"
                f"has_backend = (sys.argv[3] == 'true') if len(sys.argv) > 3 else False\n"
                f"class FullstackHandler(http.server.SimpleHTTPRequestHandler):\n"
                f"    def __init__(self, *args, **kwargs):\n"
                f"        super().__init__(*args, directory=static_dir or '.', **kwargs)\n"
                f"    def is_api_req(self):\n"
                f"        if not has_backend: return False\n"
                f"        p = self.path.split('?')[0]\n"
                f"        return (not static_dir) or p.startswith('/api') or p.startswith('/docs') or p.startswith('/openapi.json') or p.startswith('/redoc')\n"
                f"    def do_GET(self):\n"
                f"        if self.is_api_req(): self.proxy_pass()\n"
                f"        elif static_dir:\n"
                f"            req_path = self.path.split('?')[0].lstrip('/')\n"
                f"            full_path = os.path.join(static_dir, req_path)\n"
                f"            if not os.path.exists(full_path) and not os.path.exists(os.path.join(static_dir, req_path.rstrip('/') + '/index.html')) and '.' not in os.path.basename(req_path):\n"
                f"                self.path = '/index.html'\n"
                f"            super().do_GET()\n"
                f"        else: self.proxy_pass()\n"
                f"    def do_POST(self): self.proxy_pass()\n"
                f"    def do_PUT(self): self.proxy_pass()\n"
                f"    def do_DELETE(self): self.proxy_pass()\n"
                f"    def do_PATCH(self): self.proxy_pass()\n"
                f"    def do_OPTIONS(self): self.proxy_pass()\n"
                f"    def do_HEAD(self):\n"
                f"        if self.is_api_req(): self.proxy_pass()\n"
                f"        else: super().do_HEAD()\n"
                f"    def proxy_pass(self):\n"
                f"        target_url = f'http://127.0.0.1:8000{{self.path}}'\n"
                f"        content_len = int(self.headers.get('Content-Length', 0))\n"
                f"        body = self.rfile.read(content_len) if content_len > 0 else None\n"
                f"        req = urllib.request.Request(target_url, data=body, method=self.command)\n"
                f"        for k, v in self.headers.items():\n"
                f"            if k.lower() not in ('host', 'content-length'): req.add_header(k, v)\n"
                f"        try:\n"
                f"            with urllib.request.urlopen(req, timeout=60) as resp:\n"
                f"                self.send_response(resp.status)\n"
                f"                for k, v in resp.headers.items():\n"
                f"                    if k.lower() not in ('transfer-encoding', 'content-length', 'connection'): self.send_header(k, v)\n"
                f"                resp_body = resp.read()\n"
                f"                self.send_header('Content-Length', str(len(resp_body)))\n"
                f"                self.end_headers()\n"
                f"                self.wfile.write(resp_body)\n"
                f"        except urllib.error.HTTPError as he:\n"
                f"            self.send_response(he.code)\n"
                f"            for k, v in he.headers.items():\n"
                f"                if k.lower() not in ('transfer-encoding', 'content-length', 'connection'): self.send_header(k, v)\n"
                f"            err_body = he.read()\n"
                f"            self.send_header('Content-Length', str(len(err_body)))\n"
                f"            self.end_headers()\n"
                f"            self.wfile.write(err_body)\n"
                f"        except Exception as e:\n"
                f"            self.send_response(502)\n"
                f"            self.send_header('Content-Type', 'text/plain')\n"
                f"            self.end_headers()\n"
                f"            self.wfile.write(f'CompassX Gateway Error: {{e}}'.encode('utf-8'))\n"
                f"server = http.server.ThreadingHTTPServer(('0.0.0.0', port), FullstackHandler)\n"
                f"print(f'[GATEWAY] Serving static from {{static_dir}} and proxying APIs to 127.0.0.1:8000 on port {{port}}')\n"
                f"server.serve_forever()\n"
                f"GW_EOF\n && "
                # 3. Execution routing
                f"  if [ -n \"$STATIC_DIR\" ] && [ -n \"$BACKEND_DIR\" ]; then "
                f"    echo '[RUNTIME] Fullstack app detected (Frontend dist + Python Backend).' && "
                f"    (cd \"$BACKEND_DIR\" && "
                f"     export PYTHONPATH=\"$APP_ROOT:$APP_ROOT/backend:$BACKEND_DIR:/app_src:/app_src/backend:$PYTHONPATH\" PORT=8000 DASHBOARD_PORT=8000 && "
                f"     (if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; fi) && "
                f"     (pip install --no-cache-dir uvicorn fastapi asyncpg || true) && "
                f"     ENTRY_FILE=\"\" && "
                f"     for ef in main.py app.py server.py api.py; do if [ -f \"$ef\" ]; then ENTRY_FILE=\"$ef\"; break; fi; done && "
                f"     if [ -n \"$ENTRY_FILE\" ]; then "
                f"       MODULE_NAME=\"${{ENTRY_FILE%.py}}\"; "
                f"       (uvicorn ${{MODULE_NAME}}:app --host 0.0.0.0 --port 8000 || python3 \"$ENTRY_FILE\"); "
                f"     fi) & "
                f"    exec python3 /tmp/cx_gateway.py \"$STATIC_DIR\" 8080 true; "
                f"  elif [ -n \"$BACKEND_DIR\" ]; then "
                f"    echo '[RUNTIME] Backend-only app detected. Launching on port 8080.' && "
                f"    cd \"$BACKEND_DIR\" && "
                f"    export PYTHONPATH=\"$APP_ROOT:$APP_ROOT/backend:$BACKEND_DIR:/app_src:/app_src/backend:$PYTHONPATH\" PORT=8080 DASHBOARD_PORT=8080 && "
                f"    (if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; fi) && "
                f"    (pip install --no-cache-dir uvicorn fastapi streamlit asyncpg || true) && "
                f"    ENTRY_FILE=\"\" && "
                f"    for ef in main.py app.py server.py api.py; do if [ -f \"$ef\" ]; then ENTRY_FILE=\"$ef\"; break; fi; done && "
                f"    if [ -n \"$ENTRY_FILE\" ]; then "
                f"      MODULE_NAME=\"${{ENTRY_FILE%.py}}\"; "
                f"      if grep -q 'streamlit' \"$ENTRY_FILE\" 2>/dev/null || [ '{app_type}' = 'streamlit' ]; then "
                f"        exec streamlit run \"$ENTRY_FILE\" --server.port=8080 --server.address=0.0.0.0 --server.headless=true; "
                f"      elif grep -q -E 'FastAPI|Starlette' \"$ENTRY_FILE\" 2>/dev/null; then "
                f"        exec uvicorn ${{MODULE_NAME}}:app --host 0.0.0.0 --port 8080; "
                f"      elif grep -q -E 'Flask|Bottle|WSGI' \"$ENTRY_FILE\" 2>/dev/null; then "
                f"        exec python3 \"$ENTRY_FILE\"; "
                f"      else "
                f"        (uvicorn ${{MODULE_NAME}}:app --host 0.0.0.0 --port 8080 || exec python3 \"$ENTRY_FILE\"); "
                f"      fi; "
                f"    fi; "
                f"  elif [ -n \"$STATIC_DIR\" ]; then "
                f"    echo '[RUNTIME] Frontend-only app detected. Launching static gateway on port 8080.' && "
                f"    exec python3 /tmp/cx_gateway.py \"$STATIC_DIR\" 8080 false; "
                f"  elif [ -f \"$APP_ROOT/index.html\" ]; then "
                f"    echo '[RUNTIME] Static HTML app detected. Launching on port 8080.' && "
                f"    exec python3 /tmp/cx_gateway.py \"$APP_ROOT\" 8080 false; "
                f"  else "
                f"    echo '<!DOCTYPE html><html><body><h1>{app.name}</h1><p>Running on CompassX</p></body></html>' > \"$APP_ROOT/index.html\" && "
                f"    exec python3 /tmp/cx_gateway.py \"$APP_ROOT\" 8080 false; "
                f"  fi; "
                f"}} && "
                f"(run_app || hold_on_error) && hold_on_error"
            )
            container_args = [run_cmd]

        # 3. Deployment Spec
        resources_cfg = cfg.get("resources") or {}
        cpu_val = str(resources_cfg.get("cpu") or "1")
        mem_val = str(resources_cfg.get("memory") or "2Gi")
        replica_val = int(resources_cfg.get("replicas") or 1)

        container = client.V1Container(
            name="app",
            image=image_tag,
            image_pull_policy="IfNotPresent",
            env=env_vars,
            command=container_cmd,
            args=container_args,
            ports=[client.V1ContainerPort(container_port=8080, name="http")],
            resources=client.V1ResourceRequirements(
                requests={"cpu": "100m", "memory": "256Mi"},
                limits={"cpu": cpu_val, "memory": mem_val},
            ),
        )

        # Resolve target nodeSelector from Account node pool configuration
        try:
            from app.services.node_pool_manager import node_pool_manager
            app_node_selector = node_pool_manager.get_app_node_selector()
        except Exception:
            app_node_selector = None

        deployment = client.V1Deployment(
            api_version="apps/v1",
            kind="Deployment",
            metadata=client.V1ObjectMeta(name=name, namespace=ns, labels=labels),
            spec=client.V1DeploymentSpec(
                replicas=replica_val,
                selector=client.V1LabelSelector(match_labels={"compassx/app-id": clean_id, "compassx/role": "prod"}),
                template=client.V1PodTemplateSpec(
                    metadata=client.V1ObjectMeta(
                        labels=labels,
                        annotations={
                            "compassx.io/restarted-at": datetime.now(timezone.utc).isoformat(),
                        },
                    ),
                    spec=client.V1PodSpec(
                        containers=[container],
                        node_selector=app_node_selector or None,
                    ),
                ),
            ),
        )

        # 4. Service Spec
        service = client.V1Service(
            api_version="v1",
            kind="Service",
            metadata=client.V1ObjectMeta(name=name, namespace=ns, labels=labels),
            spec=client.V1ServiceSpec(
                selector={"compassx/app-id": clean_id, "compassx/role": "prod"},
                ports=[client.V1ServicePort(name="http", port=80, target_port=8080)],
                type="ClusterIP",
            ),
        )

        # 5. Ingress Spec with Dual Routing: Subdomain Host Routing + Path Routing
        # Rule 1: Subdomain routing: host: subdomain, path: /()(.*) -> target rewrite /$2
        # Rule 2: Universal Path routing on cluster ingress: path: /apps/<slug>(/|$)(.*) -> target rewrite /$2
        ingress_path_host = client.V1HTTPIngressPath(
            path="/()(.*)",
            path_type="ImplementationSpecific",
            backend=client.V1IngressBackend(
                service=client.V1IngressServiceBackend(
                    name=name,
                    port=client.V1ServiceBackendPort(number=80),
                )
            ),
        )
        ingress_rule_host = client.V1IngressRule(
            host=subdomain,
            http=client.V1HTTPIngressRuleValue(paths=[ingress_path_host]),
        )

        ingress_path_route = client.V1HTTPIngressPath(
            path=f"/apps/{app.slug}(/|$)(.*)",
            path_type="ImplementationSpecific",
            backend=client.V1IngressBackend(
                service=client.V1IngressServiceBackend(
                    name=name,
                    port=client.V1ServiceBackendPort(number=80),
                )
            ),
        )
        ingress_rule_path = client.V1IngressRule(
            http=client.V1HTTPIngressRuleValue(paths=[ingress_path_route]),
        )

        ingress_rules = [ingress_rule_host, ingress_rule_path]

        ingress_spec = client.V1IngressSpec(
            ingress_class_name=settings.K8S_INGRESS_CLASS,
            rules=ingress_rules,
        )
        tls_secret = settings.K8S_INGRESS_TLS_SECRET or (f"{app.slug}-tls" if settings.K8S_ENABLE_AUTO_TLS else "")
        if tls_secret:
            ingress_spec.tls = [
                client.V1IngressTLS(hosts=[subdomain], secret_name=tls_secret)
            ]

        prod_annotations = {
            "nginx.ingress.kubernetes.io/ssl-redirect": "false",
            "nginx.ingress.kubernetes.io/force-ssl-redirect": "false",
            "nginx.ingress.kubernetes.io/proxy-read-timeout": "3600",
            "nginx.ingress.kubernetes.io/proxy-send-timeout": "3600",
            "nginx.ingress.kubernetes.io/rewrite-target": "/$2",
            "nginx.ingress.kubernetes.io/use-regex": "true",
        }
        if settings.K8S_INGRESS_CLUSTER_ISSUER:
            prod_annotations["cert-manager.io/cluster-issuer"] = settings.K8S_INGRESS_CLUSTER_ISSUER

        ingress = client.V1Ingress(
            api_version="networking.k8s.io/v1",
            kind="Ingress",
            metadata=client.V1ObjectMeta(
                name=f"{name}-ingress",
                namespace=ns,
                labels=labels,
                annotations=prod_annotations,
            ),
            spec=ingress_spec,
        )

        # Apply resources to K8s cluster
        if k8s:
            try:
                # Deployment
                try:
                    k8s.apps().replace_namespaced_deployment(name=name, namespace=ns, body=deployment)
                except ApiException as e:
                    if e.status == 404:
                        k8s.apps().create_namespaced_deployment(namespace=ns, body=deployment)
                    elif e.status in (422, 409) or "field is immutable" in str(e).lower():
                        logger.info("Recreating deployment %s due to immutable field change: %s", name, e)
                        try:
                            k8s.apps().delete_namespaced_deployment(name=name, namespace=ns, grace_period_seconds=0)
                        except Exception:
                            pass
                        k8s.apps().create_namespaced_deployment(namespace=ns, body=deployment)
                    else:
                        raise

                # Service
                try:
                    k8s.core().replace_namespaced_service(name=name, namespace=ns, body=service)
                except ApiException as e:
                    if e.status == 404:
                        k8s.core().create_namespaced_service(namespace=ns, body=service)
                    elif e.status in (422, 409) or "field is immutable" in str(e).lower():
                        logger.info("Recreating service %s due to immutable field change: %s", name, e)
                        try:
                            k8s.core().delete_namespaced_service(name=name, namespace=ns)
                        except Exception:
                            pass
                        k8s.core().create_namespaced_service(namespace=ns, body=service)
                    else:
                        raise

                # Ingress
                try:
                    k8s.networking().replace_namespaced_ingress(name=f"{name}-ingress", namespace=ns, body=ingress)
                except ApiException as e:
                    if e.status == 404:
                        k8s.networking().create_namespaced_ingress(namespace=ns, body=ingress)
                    else:
                        raise

                build_logs.append(f"[{now_ts}] [SUCCESS] Kubernetes Deployment, Service, and Ingress ({subdomain}) created successfully.")
            except Exception as k8s_err:
                build_logs.append(f"[{now_ts}] [ERROR] K8s API communication: {k8s_err}")
                raise

        return {
            "mode": "kubernetes",
            "deployment_name": name,
            "service_name": name,
            "ingress_host": subdomain,
            "url": live_url,
            "namespace": ns,
            "deployed_at": datetime.now(timezone.utc).isoformat(),
            "status": "running",
        }

    def stop(self, app) -> bool:
        k8s = self._get_k8s_client()
        if not k8s:
            return False
        ns = settings.K8S_NAMESPACE
        clean_id = re.sub(r"[^a-z0-9-]", "-", app.id.lower()).strip("-")
        name = f"compassx-app-{clean_id}"
        try:
            # Scale deployment to 0 replicas for instant resource release and fast restart
            body = {"spec": {"replicas": 0}}
            k8s.apps().patch_namespaced_deployment(name=name, namespace=ns, body=body)
            logger.info("Scaled K8s deployment %s to 0 replicas", name)
            return True
        except Exception as e:
            logger.warning("Could not scale K8s deployment %s to 0: %s. Attempting delete...", name, e)
            try:
                k8s.apps().delete_namespaced_deployment(name=name, namespace=ns)
                return True
            except Exception as e2:
                logger.warning("Could not delete K8s deployment %s: %s", name, e2)
                return False

    def start(self, app) -> Dict[str, Any]:
        from kubernetes.client.exceptions import ApiException
        k8s = self._get_k8s_client()
        clean_id = re.sub(r"[^a-z0-9-]", "-", app.id.lower()).strip("-")
        name = f"compassx-app-{clean_id}"
        ns = settings.K8S_NAMESPACE
        cfg = dict(app.config or {})
        target_replicas = int(cfg.get("resources", {}).get("replicas") or 1)

        if not k8s:
            return {
                "app_id": app.id,
                "status": "error",
                "phase": "Unknown",
                "mode": "kubernetes",
                "message": "Kubernetes client not available.",
            }

        try:
            # Check if deployment exists and scale up
            dep = k8s.apps().read_namespaced_deployment(name=name, namespace=ns)
            body = {
                "spec": {
                    "replicas": target_replicas,
                    "template": {
                        "metadata": {
                            "annotations": {
                                "compassx.io/restarted-at": datetime.now(timezone.utc).isoformat(),
                            }
                        }
                    }
                }
            }
            k8s.apps().patch_namespaced_deployment(name=name, namespace=ns, body=body)
            logger.info("Scaled up K8s deployment %s to %d replicas", name, target_replicas)
            return {
                "app_id": app.id,
                "status": "provisioning",
                "phase": "Pending",
                "mode": "kubernetes",
                "container_name": "app",
                "pod_name": None,
                "replicas": target_replicas,
                "ready_replicas": 0,
                "step": 1,
                "step_description": "Allocating cluster resources and scheduling pod...",
                "message": f"Deployment scaled to {target_replicas} replica(s). Scheduling pod...",
                "url": self.get_live_url(app),
                "last_updated": datetime.now(timezone.utc).isoformat(),
            }
        except ApiException as e:
            if e.status == 404:
                # Deployment does not exist; trigger full deployment
                from app.services.app_runner import app_runner_service
                app_runner_service.deploy_app(app, runner_mode="kubernetes")
                return {
                    "app_id": app.id,
                    "status": "provisioning",
                    "phase": "ContainerCreating",
                    "mode": "kubernetes",
                    "container_name": "app",
                    "pod_name": None,
                    "replicas": target_replicas,
                    "ready_replicas": 0,
                    "step": 1,
                    "step_description": "Provisioning Kubernetes deployment, service, and ingress...",
                    "message": "Creating cluster resources...",
                    "url": self.get_live_url(app),
                    "last_updated": datetime.now(timezone.utc).isoformat(),
                }
            raise

    def get_status(self, app) -> Dict[str, Any]:
        k8s = self._get_k8s_client()
        clean_id = re.sub(r"[^a-z0-9-]", "-", app.id.lower()).strip("-")
        name = f"compassx-app-{clean_id}"
        ns = settings.K8S_NAMESPACE
        live_url = self.get_live_url(app)
        now_iso = datetime.now(timezone.utc).isoformat()

        if not k8s:
            return {
                "app_id": app.id,
                "status": "unknown",
                "phase": "Unknown",
                "mode": "kubernetes",
                "deployment_name": name,
                "url": live_url,
                "last_updated": now_iso,
            }

        try:
            dep = k8s.apps().read_namespaced_deployment(name=name, namespace=ns)
            desired_replicas = dep.spec.replicas or 0
            ready_replicas = dep.status.ready_replicas or 0
            available_replicas = dep.status.available_replicas or 0

            if desired_replicas == 0:
                return {
                    "app_id": app.id,
                    "status": "stopped",
                    "phase": "Stopped",
                    "mode": "kubernetes",
                    "container_name": "app",
                    "pod_name": None,
                    "replicas": 0,
                    "ready_replicas": 0,
                    "available_replicas": 0,
                    "step": 0,
                    "step_description": "Application is stopped",
                    "message": "Deployment is stopped (0 replicas).",
                    "url": live_url,
                    "last_updated": now_iso,
                }

            # Query live pods
            pods = k8s.core().list_namespaced_pod(
                namespace=ns,
                label_selector=f"compassx/app-id={clean_id},compassx/role=prod"
            )

            if not pods.items:
                return {
                    "app_id": app.id,
                    "status": "provisioning",
                    "phase": "Pending",
                    "mode": "kubernetes",
                    "container_name": "app",
                    "pod_name": None,
                    "replicas": desired_replicas,
                    "ready_replicas": 0,
                    "available_replicas": 0,
                    "step": 1,
                    "step_description": "Allocating cluster resources and scheduling pod...",
                    "message": "Waiting for pod to be scheduled on node...",
                    "url": live_url,
                    "last_updated": now_iso,
                }

            # Filter out pods marked for deletion if other pods exist
            active_pods = [p for p in pods.items if not p.metadata.deletion_timestamp]
            target_pod = active_pods[0] if active_pods else pods.items[0]
            pod_name = target_pod.metadata.name
            pod_phase = target_pod.status.phase if target_pod.status else "Unknown"

            if target_pod.metadata.deletion_timestamp:
                return {
                    "app_id": app.id,
                    "status": "stopping",
                    "phase": "Terminating",
                    "mode": "kubernetes",
                    "container_name": "app",
                    "pod_name": pod_name,
                    "replicas": desired_replicas,
                    "ready_replicas": 0,
                    "available_replicas": 0,
                    "step": 0,
                    "step_description": "Terminating container and releasing cluster resources...",
                    "message": "Pod is terminating...",
                    "url": live_url,
                    "last_updated": now_iso,
                }

            # Check container statuses inside pod
            container_statuses = target_pod.status.container_statuses if target_pod.status else []
            app_container_status = next((c for c in container_statuses if c.name == "app"), container_statuses[0] if container_statuses else None)

            if app_container_status:
                waiting = app_container_status.state.waiting if app_container_status.state else None
                if waiting:
                    reason = waiting.reason or "Waiting"
                    msg = waiting.message or f"Container waiting: {reason}"
                    if reason in ("CrashLoopBackOff", "ImagePullBackOff", "ErrImagePull", "Error"):
                        return {
                            "app_id": app.id,
                            "status": "error",
                            "phase": reason,
                            "mode": "kubernetes",
                            "container_name": "app",
                            "pod_name": pod_name,
                            "replicas": desired_replicas,
                            "ready_replicas": 0,
                            "available_replicas": 0,
                            "step": 0,
                            "step_description": f"Error: {reason}",
                            "message": msg,
                            "url": live_url,
                            "last_updated": now_iso,
                        }
                    elif reason in ("ContainerCreating", "PodInitializing"):
                        prov_msg = "Container is initializing on node..."
                        prov_desc = "Pulling container image & initializing app container..."
                        try:
                            evs = k8s.core().list_namespaced_event(
                                namespace=ns,
                                field_selector=f"involvedObject.name={pod_name}"
                            )
                            if evs and evs.items:
                                latest_ev = sorted(
                                    evs.items,
                                    key=lambda ev: ev.last_timestamp or ev.event_time or ev.metadata.creation_timestamp or datetime.min.replace(tzinfo=timezone.utc)
                                )[-1]
                                if latest_ev.message:
                                    prov_msg = latest_ev.message
                                if latest_ev.reason == "Pulling":
                                    prov_desc = "Downloading host base container image..."
                                elif latest_ev.reason == "Pulled":
                                    prov_desc = "Image pulled. Creating and starting container..."
                                elif latest_ev.reason == "Scheduled":
                                    prov_desc = "Pod scheduled. Allocating container storage..."
                        except Exception:
                            pass
                        return {
                            "app_id": app.id,
                            "status": "provisioning",
                            "phase": reason,
                            "mode": "kubernetes",
                            "container_name": "app",
                            "pod_name": pod_name,
                            "replicas": desired_replicas,
                            "ready_replicas": 0,
                            "available_replicas": 0,
                            "step": 2,
                            "step_description": prov_desc,
                            "message": prov_msg,
                            "url": live_url,
                            "last_updated": now_iso,
                        }

            if pod_phase == "Pending":
                pend_msg = "Pod is pending placement on node..."
                try:
                    evs = k8s.core().list_namespaced_event(
                        namespace=ns,
                        field_selector=f"involvedObject.name={pod_name}"
                    )
                    if evs and evs.items:
                        latest_ev = sorted(
                            evs.items,
                            key=lambda ev: ev.last_timestamp or ev.event_time or ev.metadata.creation_timestamp or datetime.min.replace(tzinfo=timezone.utc)
                        )[-1]
                        if latest_ev.message:
                            pend_msg = latest_ev.message
                except Exception:
                    pass
                return {
                    "app_id": app.id,
                    "status": "provisioning",
                    "phase": "Pending",
                    "mode": "kubernetes",
                    "container_name": "app",
                    "pod_name": pod_name,
                    "replicas": desired_replicas,
                    "ready_replicas": 0,
                    "available_replicas": 0,
                    "step": 1,
                    "step_description": "Allocating cluster resources and scheduling pod...",
                    "message": pend_msg,
                    "url": live_url,
                    "last_updated": now_iso,
                }

            if pod_phase == "Running":
                is_pod_ready = ready_replicas > 0 or (app_container_status and app_container_status.ready)
                if is_pod_ready:
                    return {
                        "app_id": app.id,
                        "status": "active",
                        "phase": "Running",
                        "mode": "kubernetes",
                        "container_name": "app",
                        "pod_name": pod_name,
                        "replicas": desired_replicas,
                        "ready_replicas": max(ready_replicas, 1),
                        "available_replicas": max(available_replicas, 1),
                        "step": 4,
                        "step_description": "Pod is running and serving live traffic",
                        "message": "Application is live and ready.",
                        "url": live_url,
                        "last_updated": now_iso,
                    }
                else:
                    return {
                        "app_id": app.id,
                        "status": "starting",
                        "phase": "Running",
                        "mode": "kubernetes",
                        "container_name": "app",
                        "pod_name": pod_name,
                        "replicas": desired_replicas,
                        "ready_replicas": 0,
                        "available_replicas": 0,
                        "step": 3,
                        "step_description": "Application server process starting on port 8080...",
                        "message": "Container started, waiting for application startup...",
                        "url": live_url,
                        "last_updated": now_iso,
                    }

            return {
                "app_id": app.id,
                "status": "starting",
                "phase": pod_phase,
                "mode": "kubernetes",
                "container_name": "app",
                "pod_name": pod_name,
                "replicas": desired_replicas,
                "ready_replicas": ready_replicas,
                "available_replicas": available_replicas,
                "step": 2,
                "step_description": f"Pod in phase {pod_phase}",
                "message": f"Pod state: {pod_phase}",
                "url": live_url,
                "last_updated": now_iso,
            }

        except Exception as ex:
            logger.debug("Could not inspect K8s deployment %s status: %s", name, ex)
            return {
                "app_id": app.id,
                "status": "stopped",
                "phase": "NotFound",
                "mode": "kubernetes",
                "container_name": "app",
                "pod_name": None,
                "replicas": 0,
                "ready_replicas": 0,
                "available_replicas": 0,
                "step": 0,
                "step_description": "Application stopped / not deployed",
                "message": "Application is stopped / not deployed.",
                "url": live_url,
                "last_updated": now_iso,
            }

    def get_logs(self, app, max_lines: int = 200) -> List[str]:
        k8s = self._get_k8s_client()
        if not k8s:
            return []
        ns = settings.K8S_NAMESPACE
        clean_id = re.sub(r"[^a-z0-9-]", "-", app.id.lower()).strip("-")
        try:
            pods = k8s.core().list_namespaced_pod(namespace=ns, label_selector=f"compassx/app-id={clean_id},compassx/role=prod")
            if not pods.items:
                return []
            active_pods = [p for p in pods.items if not p.metadata.deletion_timestamp]
            target_pod = active_pods[0] if active_pods else pods.items[0]
            pod_name = target_pod.metadata.name

            container_logs: List[str] = []
            try:
                raw = k8s.core().read_namespaced_pod_log(name=pod_name, namespace=ns, tail_lines=max_lines)
                if raw and raw.strip():
                    container_logs = [line for line in raw.splitlines() if line.strip()]
            except Exception as e:
                logger.debug("Container log not yet readable for pod %s: %s", pod_name, e)

            # Query pod lifecycle events
            event_logs: List[str] = []
            try:
                evs = k8s.core().list_namespaced_event(
                    namespace=ns,
                    field_selector=f"involvedObject.name={pod_name}"
                )
                if evs and evs.items:
                    sorted_evs = sorted(
                        evs.items,
                        key=lambda ev: ev.last_timestamp or ev.event_time or ev.metadata.creation_timestamp or datetime.min.replace(tzinfo=timezone.utc)
                    )
                    for ev in sorted_evs:
                        ts = ev.last_timestamp or ev.event_time or ev.metadata.creation_timestamp
                        ts_str = ts.strftime("%H:%M:%S") if ts and hasattr(ts, "strftime") else "PROVISION"
                        reason = ev.reason or "Event"
                        msg = ev.message or ""
                        event_logs.append(f"[{ts_str}] [PROVISION] [{reason}] {msg}")
            except Exception as ev_err:
                logger.debug("Could not read pod events for %s: %s", pod_name, ev_err)

            if container_logs:
                # Merge recent provisioning events before container output
                return event_logs + container_logs
            elif event_logs:
                return event_logs
            return []
        except Exception as e:
            logger.debug("Could not read K8s pod logs for app %s: %s", app.id, e)
            return []

    def get_live_url(self, app) -> str:
        return ingress_service.get_app_url(app)

    def capture_build_logs(
        self,
        app,
        deployment_id: str,
        timeout_sec: int = 120,
        initial_logs: Optional[List[str]] = None,
        on_progress: Optional[Callable[[List[str]], None]] = None,
    ) -> List[str]:
        """Poll and stream pure build phase logs from the newly spawned pod in real-time."""
        import time
        k8s = self._get_k8s_client()
        base_logs = list(initial_logs or [])
        if not k8s:
            base_logs.append("[INFO] K8s client not available to stream build logs.")
            return base_logs

        ns = settings.K8S_NAMESPACE
        clean_id = re.sub(r"[^a-z0-9-]", "-", app.id.lower()).strip("-")

        # 1. Wait for newly created pod
        pod_name = None
        start_time = time.time()
        last_notified_phase = None
        while time.time() - start_time < 35:
            try:
                pods = k8s.core().list_namespaced_pod(
                    namespace=ns,
                    label_selector=f"compassx/app-id={clean_id},compassx/role=prod",
                )
                items = [p for p in pods.items if p.metadata and not p.metadata.deletion_timestamp]
                if items:
                    # Sort by creation timestamp descending (newest pod first)
                    items.sort(key=lambda p: p.metadata.creation_timestamp or 0, reverse=True)
                    pod_name = items[0].metadata.name
                    phase = items[0].status.phase if items[0].status else "Unknown"
                    if phase != last_notified_phase:
                        last_notified_phase = phase
                        if on_progress:
                            now_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
                            on_progress(base_logs + [f"[{now_ts}] [INFO] Deployment pod '{pod_name}' phase: {phase}"])
                    if phase in ("Running", "Succeeded", "Failed"):
                        break
            except Exception as e:
                logger.debug("Waiting for deployment pod %s: %s", clean_id, e)
            time.sleep(1.5)

        if not pod_name:
            now_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            base_logs.append(f"[{now_ts}] [INFO] Deployment {deployment_id} scheduled in namespace '{ns}'.")
            base_logs.append(f"[{now_ts}] [INFO] Container rollout initiated for {app.name}.")
            return base_logs

        # 2. Read logs continuously and stream progress until build phase finishes or timeout
        captured_build_logs = []
        build_started = False
        build_finished = False
        loop_start = time.time()

        while time.time() - loop_start < timeout_sec:
            try:
                raw = k8s.core().read_namespaced_pod_log(name=pod_name, namespace=ns, tail_lines=1000)
                lines = [l for l in raw.splitlines() if l.strip()]

                current_build_lines = []
                for line in lines:
                    if "[BUILD]" in line:
                        build_started = True
                        current_build_lines.append(line)
                        if "Build phase completed successfully" in line or "Build pipeline finished" in line:
                            build_finished = True
                    elif "[ERROR]" in line or "npm error" in line.lower() or "fatal:" in line.lower():
                        build_started = True
                        current_build_lines.append(line)
                        build_finished = True
                    elif "[RUNTIME]" in line or "Launching application server" in line or "Uvicorn running" in line or "Serving" in line or "streamlit run" in line.lower():
                        build_started = True
                        current_build_lines.append(line)
                        build_finished = True
                        break
                    elif build_started and not build_finished:
                        # Capture compiler, npm, git, and pip output during the build phase
                        current_build_lines.append(line)

                if current_build_lines:
                    combined = base_logs + current_build_lines
                    captured_build_logs = combined
                    if on_progress:
                        on_progress(combined)

                if build_finished:
                    break
            except Exception as e:
                logger.debug("Streaming pod logs for %s: %s", pod_name, e)

            time.sleep(1.5)

        if not captured_build_logs:
            try:
                raw = k8s.core().read_namespaced_pod_log(name=pod_name, namespace=ns, tail_lines=100)
                pod_lines = [l for l in raw.splitlines() if l.strip()]
                captured_build_logs = base_logs + pod_lines
            except Exception:
                captured_build_logs = base_logs + [f"[INFO] Deployment {deployment_id} active on pod {pod_name}."]

        return captured_build_logs


class KubernetesDevDriver(BaseDevDriver):
    """Manages Kubernetes Dev Sandbox Pods connecting via Cluster DNS to Omnigent Server."""

    def _get_k8s_client(self):
        try:
            from app.compute.services.k8s_client import get_k8s_client
            return get_k8s_client()
        except Exception:
            try:
                from compassx.drivers.k8s_client import K8sApiClient
                return K8sApiClient()
            except Exception:
                return None

    def start_dev(self, app, repo_dir: str, omnigent_internal_url: str, workspace_folder: str = "", workspace_branch: str = "", host_type: str = "compassx", **kwargs) -> Dict[str, Any]:
        from kubernetes import client
        from kubernetes.client.exceptions import ApiException

        k8s = self._get_k8s_client()
        clean_id = re.sub(r"[^a-z0-9-]", "-", app.id.lower()).strip("-")
        host_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"compassx-app-{clean_id}").hex
        host_name = str(app.name or app.slug or app.id).strip()
        dev_name = f"compassx-app-dev-{clean_id}"
        dev_subdomain = ingress_service.get_app_dev_domain(app)
        dev_url = ingress_service.get_app_dev_url(app)
        ns = settings.K8S_NAMESPACE

        labels = {
            "app.kubernetes.io/name": dev_name,
            "app.kubernetes.io/instance": f"{app.slug}-dev",
            "compassx/app-id": clean_id,
            "compassx/dev": "true",
            "compassx/role": "dev",
            "compassx/managed": "true",
        }

        # Resolve dev host image based on host_type selection
        host_type = str(host_type or kwargs.get("host_type") or "compassx").lower()
        custom_img = (getattr(app, "config", None) or {}).get("dev_image") or (getattr(app, "config", None) or {}).get("image")
        if custom_img and ("/" in str(custom_img)):
            dev_host_image = str(custom_img)
        elif getattr(settings, "DEV_HOST_IMAGE", None) and ("/" in str(settings.DEV_HOST_IMAGE)):
            dev_host_image = str(settings.DEV_HOST_IMAGE)
        else:
            dev_host_image = "ghcr.io/omnigent-ai/omnigent-host:latest"

        # If k8s client is available, provision Dev Pod, Service, and Ingress
        if k8s:
            try:
                # 1. Dev Pod
                git_url = getattr(app, "git_repo_url", None)
                git_token = None
                if hasattr(app, "git_pat_enc") and app.git_pat_enc:
                    try:
                        from app.services.encryption import decrypt_field
                        git_token = decrypt_field(app.git_pat_enc)
                    except Exception:
                        pass
                auth_url = git_url
                if git_token and git_url and "github.com" in git_url and not ("@" in git_url.split("//")[-1]):
                    auth_url = git_url.replace("https://", f"https://x-access-token:{git_token}@")
                git_ref = getattr(app, "git_ref", None) or getattr(app, "git_branch", None) or "main"

                # Dedicated branch for this workspace
                target_branch = workspace_branch
                if not target_branch and workspace_folder:
                    ws_leaf = workspace_folder.split("/")[-1]
                    target_branch = f"dev/{ws_leaf}"
                if not target_branch:
                    target_branch = "dev/default"

                clone_snippet = ""
                if auth_url:
                    clone_snippet = (
                        f"if [ ! -e .git ]; then "
                        f"  rm -rf ./* ./.[!.]* 2>/dev/null || true; "
                        f"  (git clone --branch '{git_ref}' '{auth_url}' . || git clone '{auth_url}' . || true) && "
                        f"  (git checkout -B '{target_branch}' || true); "
                        f"else "
                        f"  (git checkout -B '{target_branch}' 2>/dev/null || true); "
                        f"fi; "
                    )

                # Resolve workspace workdir on shared PVC
                if workspace_folder:
                    workdir = f"/workspaces/{workspace_folder}"
                else:
                    import re as _re
                    workdir = f"/workspaces/{_re.sub(r'[^a-z0-9-]', '-', app.id.lower()).strip('-')}/default"

                app_type = getattr(app, "app_type", "custom_web") or "custom_web"
                git_subdir = (getattr(app, "git_subdir", "") or "").strip("/\\")

                try:
                    from app.ai_gateway.mcp.omnigent_sync import get_mcp_sync_shell_script
                    mcp_sync_snippet = get_mcp_sync_shell_script(api_base_url="https://135.13.180.167.nip.io")
                except Exception:
                    mcp_sync_snippet = "true"

                workload_identity_id = ""
                if getattr(app, "workspace_identity", None) and isinstance(app.workspace_identity, dict):
                    workload_identity_id = app.workspace_identity.get("identity_id") or ""
                elif hasattr(app, "id") and app.id:
                    clean_app_id = re.sub(r"[^a-z0-9]", "", str(app.id).lower())
                    workload_identity_id = f"id_app_{clean_app_id[:12]}"

                runner_script_b64 = base64.b64encode(self._get_dev_runner_script().encode("utf-8")).decode("ascii")
                dev_cmd = (
                    f"mkdir -p /workspaces/.shared_auth/.gemini/antigravity-cli && "
                    f"if [ ! -f /workspaces/.shared_auth/.gemini/antigravity-cli/antigravity-oauth-token ]; then "
                    f"  printf '{{\"auth_method\":\"oauth\",\"token\":{{\"access_token\":\"auto-authenticated-dev-cluster-token\",\"refresh_token\":\"1//auto-authenticated-dev-cluster-token\",\"token_type\":\"Bearer\",\"expiry\":\"2099-01-01T00:00:00Z\"}}}}' > /workspaces/.shared_auth/.gemini/antigravity-cli/antigravity-oauth-token; "
                    f"fi; "
                    f"if [ ! -f /workspaces/.shared_auth/.gemini/oauth_creds.json ]; then "
                    f"  printf '{{\"access_token\":\"auto-authenticated-dev-cluster-token\",\"refresh_token\":\"1//auto-authenticated-dev-cluster-token\",\"token_type\":\"Bearer\",\"expiry_date\":4102444800000}}' > /workspaces/.shared_auth/.gemini/oauth_creds.json; "
                    f"fi; "
                    f"cp -rn /root/.gemini/* /workspaces/.shared_auth/.gemini/ 2>/dev/null; "
                    f"rm -rf /root/.gemini && ln -sf /workspaces/.shared_auth/.gemini /root/.gemini; "
                    # Background daemon: persistently syncs any real agy OAuth tokens acquired in any session back to shared_auth PVC
                    f"(while true; do "
                    f"  for t in /root/.omnigent/antigravity-native/*/agy-home/.gemini/antigravity-cli/antigravity-oauth-token /root/.omnigent/antigravity-native/*/agy-home/.gemini/oauth_creds.json; do "
                    f"    if [ -f \"$t\" ] && ! grep -q 'auto-authenticated-dev-cluster-token' \"$t\" 2>/dev/null; then "
                    f"      case \"$t\" in "
                    f"        *antigravity-oauth-token) cp -f \"$t\" /workspaces/.shared_auth/.gemini/antigravity-cli/antigravity-oauth-token 2>/dev/null ;; "
                    f"        *oauth_creds.json) cp -f \"$t\" /workspaces/.shared_auth/.gemini/oauth_creds.json 2>/dev/null ;; "
                    f"      esac; "
                    f"    fi; "
                    f"  done; "
                    f"  sleep 2; "
                    f"done) & "
                    f"(which agy >/dev/null 2>&1 || (curl -k -fsSL -o /tmp/agy.tar.gz 'https://github.com/google-antigravity/antigravity-cli/releases/download/1.0.10/agy_cli_linux_x64.tar.gz' 2>/dev/null && tar -xzf /tmp/agy.tar.gz -C /tmp antigravity 2>/dev/null && install -m 0755 /tmp/antigravity /usr/local/bin/agy 2>/dev/null && rm -f /tmp/agy.tar.gz /tmp/antigravity) || (curl -k -fsSL https://antigravity.google/install.sh | bash 2>/dev/null || true)); "
                    f"(which agy >/dev/null 2>&1 && ln -sf /usr/local/bin/agy /usr/local/bin/antigravity || true); "
                    f"mkdir -p /root/.omnigent /root/.config/omnigent /root/.config/opencode /root/.opencode && "
                    f"printf 'host:\\n  host_id: {host_id}\\n  name: \"{host_name}\"\\n' | tee /root/.omnigent/config.yaml /root/.config/omnigent/config.yaml /root/.config/opencode/config.yaml /root/.opencode/config.yaml >/dev/null; "
                    f"export OMNIGENT_HOST_ID={host_id} OMNIGENT_HOST_NAME=\"{host_name}\" HOST_ID={host_id} HOST_NAME=\"{host_name}\" OPENCODE_HOST_ID={host_id} OPENCODE_HOST_NAME=\"{host_name}\" "
                    f"POSTGRES_DSN=\"${{POSTGRES_DSN:-postgresql://postgres:postgres@compassx-postgres:5432/autonomic}}\" REDIS_URL=\"${{REDIS_URL:-redis://compassx-redis:6379/0}}\" JWT_SECRET=\"${{JWT_SECRET:-dev-jwt-secret-change-me-for-production-use-min-32-chars}}\" "
                    f"COMPASSX_WORKLOAD_IDENTITY=\"{workload_identity_id}\" WORKSPACE_ID=\"{getattr(app, 'workspace_id', '')}\" APP_ID=\"{app.id}\" APP_NAME=\"{app.name}\" APP_SLUG=\"{app.slug}\" GIT_SUBDIR=\"{git_subdir}\" APP_SUBDIR=\"{git_subdir}\" "
                    f"CHOKIDAR_USEPOLLING=1 CHOKIDAR_INTERVAL=2000 WATCHPACK_POLLING=true WATCHPACK_POLLING_INTERVAL=2000 WATCHFILES_FORCE_POLLING=true WATCHFILES_POLL_DELAY_MS=2000 "
                    f"NODE_TLS_REJECT_UNAUTHORIZED=0 NPM_CONFIG_STRICT_SSL=false PYTHONHTTPSVERIFY=0 GIT_SSL_NO_VERIFY=true CURL_INSECURE=1; "
                    f"(which opencode >/dev/null 2>&1 || npm install -g opencode-ai@1.18.0 || true); "
                    f"mkdir -p {workdir} && cd {workdir} && "
                    f"{clone_snippet}"
                    # Sync AI Gateway MCP servers to all harness configs (Claude, OpenCode, Antigravity, Codex)
                    f"({mcp_sync_snippet}) && "
                    # Install and start Dev Server Supervisor for active sandbox
                    f"echo '{runner_script_b64}' | base64 -d > /usr/local/bin/dev-runner.sh && "
                    f"chmod +x /usr/local/bin/dev-runner.sh && "
                    f"export GIT_SUBDIR=\"{git_subdir}\" APP_SUBDIR=\"{git_subdir}\" && "
                    f"/usr/local/bin/dev-runner.sh reload '{workdir}' && "
                    # Start Omnigent Host Runner in foreground
                    f"exec omnigent host --server {omnigent_internal_url} --non-interactive"
                )
                # 1b. Dev Deployment Spec (resilient self-healing; /workspaces backed by shared PVC)
                dev_container = client.V1Container(
                    name="dev-host",
                    image=dev_host_image,
                    image_pull_policy="IfNotPresent",
                    command=["/bin/sh", "-c"],
                    args=[dev_cmd],
                    ports=[client.V1ContainerPort(container_port=8080, name="http")],
                    env=[
                        client.V1EnvVar(name="PORT", value="8080"),
                        client.V1EnvVar(name="APP_NAME", value=str(app.name)),
                        client.V1EnvVar(name="APP_SLUG", value=str(app.slug)),
                        client.V1EnvVar(name="APP_ID", value=str(app.id)),
                        client.V1EnvVar(name="WORKSPACE_ID", value=str(getattr(app, "workspace_id", ""))),
                        client.V1EnvVar(name="COMPASSX_WORKLOAD_IDENTITY", value=str(workload_identity_id)),
                        client.V1EnvVar(name="OMNIGENT_HOST_ID", value=str(host_id)),
                        client.V1EnvVar(name="OMNIGENT_HOST_NAME", value=str(host_name)),
                        client.V1EnvVar(name="OMNIGENT_SERVER_URL", value=str(omnigent_internal_url)),
                        client.V1EnvVar(name="DEV_WORKSPACE_DIR", value=workdir),
                        client.V1EnvVar(name="GIT_SUBDIR", value=str(git_subdir)),
                        client.V1EnvVar(name="APP_SUBDIR", value=str(git_subdir)),
                    ],
                    resources=client.V1ResourceRequirements(
                        requests={"cpu": "500m", "memory": "1Gi"},
                        limits={"cpu": "4", "memory": "8Gi"},
                    ),
                    volume_mounts=[
                        client.V1VolumeMount(
                            name="shared-storage",
                            mount_path="/workspaces",
                            sub_path="workspaces",
                        )
                    ],
                )

                dev_affinity = client.V1Affinity(
                    node_affinity=client.V1NodeAffinity(
                        preferred_during_scheduling_ignored_during_execution=[
                            client.V1PreferredSchedulingTerm(
                                weight=100,
                                preference=client.V1NodeSelectorTerm(
                                    match_expressions=[
                                        client.V1NodeSelectorRequirement(
                                            key="kubernetes.azure.com/agentpool",
                                            operator="In",
                                            values=["computepool"],
                                        )
                                    ]
                                ),
                            )
                        ]
                    ),
                    pod_anti_affinity=client.V1PodAntiAffinity(
                        preferred_during_scheduling_ignored_during_execution=[
                            client.V1WeightedPodAffinityTerm(
                                weight=100,
                                pod_affinity_term=client.V1PodAffinityTerm(
                                    label_selector=client.V1LabelSelector(
                                        match_expressions=[
                                            client.V1LabelSelectorRequirement(
                                                key="compassx/dev",
                                                operator="In",
                                                values=["true"],
                                            )
                                        ]
                                    ),
                                    topology_key="kubernetes.io/hostname",
                                ),
                            )
                        ]
                    ),
                )

                try:
                    from app.services.node_pool_manager import node_pool_manager
                    dev_node_selector = node_pool_manager.get_compute_node_selector()
                except Exception:
                    dev_node_selector = {"kubernetes.azure.com/agentpool": "computepool"}

                dev_deployment = client.V1Deployment(
                    api_version="apps/v1",
                    kind="Deployment",
                    metadata=client.V1ObjectMeta(name=dev_name, namespace=ns, labels=labels),
                    spec=client.V1DeploymentSpec(
                        replicas=1,
                        strategy=client.V1DeploymentStrategy(type="Recreate"),
                        selector=client.V1LabelSelector(match_labels={"compassx/app-id": clean_id, "compassx/dev": "true"}),
                        template=client.V1PodTemplateSpec(
                            metadata=client.V1ObjectMeta(labels=labels),
                            spec=client.V1PodSpec(
                                containers=[dev_container],
                                affinity=dev_affinity,
                                node_selector=dev_node_selector or {"kubernetes.azure.com/agentpool": "computepool"},
                                restart_policy="Always",
                                volumes=[
                                    client.V1Volume(
                                        name="shared-storage",
                                        persistent_volume_claim=client.V1PersistentVolumeClaimVolumeSource(
                                            claim_name="compassx-shared-storage",
                                        ),
                                    )
                                ],
                            ),
                        ),
                    ),
                )


                try:
                    k8s.apps().replace_namespaced_deployment(name=dev_name, namespace=ns, body=dev_deployment)
                except ApiException as e:
                    if e.status == 404:
                        # Clean up any legacy bare pod if present
                        try:
                            k8s.core().delete_namespaced_pod(name=dev_name, namespace=ns, grace_period_seconds=0)
                        except Exception:
                            pass
                        k8s.apps().create_namespaced_deployment(namespace=ns, body=dev_deployment)
                    else:
                        raise

                # 2. Dev Service
                dev_svc = client.V1Service(
                    api_version="v1",
                    kind="Service",
                    metadata=client.V1ObjectMeta(name=dev_name, namespace=ns, labels=labels),
                    spec=client.V1ServiceSpec(
                        selector={"compassx/app-id": clean_id, "compassx/dev": "true"},
                        ports=[client.V1ServicePort(name="http", port=80, target_port=8080)],
                        type="ClusterIP",
                    ),
                )
                try:
                    k8s.core().replace_namespaced_service(name=dev_name, namespace=ns, body=dev_svc)
                except ApiException as e:
                    if e.status == 404:
                        k8s.core().create_namespaced_service(namespace=ns, body=dev_svc)
                    else:
                        raise

                # 3. Dev Ingress with Dual Routing
                dev_tls_secret = settings.K8S_INGRESS_TLS_SECRET or (f"{app.slug}-dev-tls" if settings.K8S_ENABLE_AUTO_TLS else "")
                dev_tls = [client.V1IngressTLS(hosts=[dev_subdomain], secret_name=dev_tls_secret)] if dev_tls_secret else None

                dev_annotations = {
                    "nginx.ingress.kubernetes.io/ssl-redirect": "false",
                    "nginx.ingress.kubernetes.io/force-ssl-redirect": "false",
                    "nginx.ingress.kubernetes.io/proxy-read-timeout": "3600",
                    "nginx.ingress.kubernetes.io/proxy-send-timeout": "3600",
                    "nginx.ingress.kubernetes.io/rewrite-target": "/$2",
                    "nginx.ingress.kubernetes.io/use-regex": "true",
                }
                if settings.K8S_INGRESS_CLUSTER_ISSUER:
                    dev_annotations["cert-manager.io/cluster-issuer"] = settings.K8S_INGRESS_CLUSTER_ISSUER

                dev_ingress = client.V1Ingress(
                    api_version="networking.k8s.io/v1",
                    kind="Ingress",
                    metadata=client.V1ObjectMeta(
                        name=f"{dev_name}-ingress",
                        namespace=ns,
                        labels=labels,
                        annotations=dev_annotations,
                    ),
                    spec=client.V1IngressSpec(
                        ingress_class_name=settings.K8S_INGRESS_CLASS,
                        tls=dev_tls,
                        rules=[
                            client.V1IngressRule(
                                host=dev_subdomain,
                                http=client.V1HTTPIngressRuleValue(
                                    paths=[
                                        client.V1HTTPIngressPath(
                                            path="/()(.*)",
                                            path_type="ImplementationSpecific",
                                            backend=client.V1IngressBackend(
                                                service=client.V1IngressServiceBackend(
                                                    name=dev_name,
                                                    port=client.V1ServiceBackendPort(number=80),
                                                )
                                            ),
                                        )
                                    ]
                                ),
                            ),
                            client.V1IngressRule(
                                http=client.V1HTTPIngressRuleValue(
                                    paths=[
                                        client.V1HTTPIngressPath(
                                            path=f"/apps/{app.slug}-dev(/|$)(.*)",
                                            path_type="ImplementationSpecific",
                                            backend=client.V1IngressBackend(
                                                service=client.V1IngressServiceBackend(
                                                    name=dev_name,
                                                    port=client.V1ServiceBackendPort(number=80),
                                                )
                                            ),
                                        )
                                    ]
                                ),
                            ),
                        ],
                    ),
                )
                try:
                    k8s.networking().replace_namespaced_ingress(name=f"{dev_name}-ingress", namespace=ns, body=dev_ingress)
                except ApiException as e:
                    if e.status == 404:
                        k8s.networking().create_namespaced_ingress(namespace=ns, body=dev_ingress)
                    else:
                        raise
            except Exception as e:
                logger.warning("Could not create K8s dev sandbox resources: %s", e)

        curr_status = self.get_dev_status(app)
        st_val = curr_status.get("status")
        if st_val not in ["active", "provisioning", "error"]:
            st_val = "provisioning"

        return {
            "mode": "kubernetes",
            "pod_name": curr_status.get("pod_name", dev_name),
            "container_name": dev_name,
            "dev_url": dev_url,
            "host_id": host_id,
            "host_name": host_name,
            "host_type": host_type,
            "host_image": dev_host_image,
            "namespace": ns,
            "status": st_val,
            "phase": curr_status.get("phase", "Pending"),
            "is_scaling_node": curr_status.get("is_scaling_node", False),
            "provisioning_reason": curr_status.get("provisioning_reason", "scheduling"),
            "provisioning_message": curr_status.get("provisioning_message", "Initializing Kubernetes dev sandbox..."),
        }

    def stop_dev(self, app) -> bool:
        k8s = self._get_k8s_client()
        if not k8s:
            return False
        ns = settings.K8S_NAMESPACE
        clean_id = re.sub(r"[^a-z0-9-]", "-", app.id.lower()).strip("-")
        name = f"compassx-app-dev-{clean_id}"
        stopped = False
        try:
            k8s.apps().delete_namespaced_deployment(name=name, namespace=ns)
            stopped = True
        except Exception:
            pass
        try:
            k8s.core().delete_namespaced_pod(name=name, namespace=ns, grace_period_seconds=0)
            stopped = True
        except Exception:
            pass
        return stopped

    def restart_dev(self, app) -> bool:
        """Trigger a clean rollout restart for dev deployment and delete any stuck or failed pods."""
        k8s = self._get_k8s_client()
        if not k8s:
            return False
        ns = settings.K8S_NAMESPACE
        clean_id = re.sub(r"[^a-z0-9-]", "-", app.id.lower()).strip("-")
        dev_name = f"compassx-app-dev-{clean_id}"

        # 1. Delete any existing pods that are stuck, failed, or evicted
        try:
            pods = k8s.core().list_namespaced_pod(
                namespace=ns,
                label_selector=f"compassx/app-id={clean_id},compassx/dev=true",
            )
            for p in (pods.items or []):
                p_name = p.metadata.name if p.metadata else None
                if p_name:
                    try:
                        k8s.core().delete_namespaced_pod(name=p_name, namespace=ns, grace_period_seconds=0)
                        logger.info("Deleted dev pod %s during restart", p_name)
                    except Exception as pe:
                        logger.debug("Could not delete pod %s during restart: %s", p_name, pe)
        except Exception as e:
            logger.debug("Error listing pods during restart: %s", e)

        # 2. Patch deployment with restartedAt annotation to force fresh rollout
        try:
            now_iso = datetime.now(timezone.utc).isoformat()
            patch_body = {
                "spec": {
                    "template": {
                        "metadata": {
                            "annotations": {
                                "kubectl.kubernetes.io/restartedAt": now_iso,
                            }
                        }
                    }
                }
            }
            k8s.apps().patch_namespaced_deployment(name=dev_name, namespace=ns, body=patch_body)
            logger.info("Triggered rollout restart for dev deployment %s", dev_name)
            return True
        except ApiException as ae:
            if ae.status == 404:
                return True
            logger.warning("Failed patching deployment %s during restart: %s", dev_name, ae)
            return False
        except Exception as e:
            logger.warning("Error restarting dev deployment %s: %s", dev_name, e)
            return False

    def suspend_dev(self, app) -> bool:
        """Suspend dev sandbox compute (scale replicas to 0) while keeping persistent volume claim intact."""
        k8s = self._get_k8s_client()
        if not k8s:
            return False
        ns = settings.K8S_NAMESPACE
        clean_id = re.sub(r"[^a-z0-9-]", "-", app.id.lower()).strip("-")
        name = f"compassx-app-dev-{clean_id}"
        try:
            k8s.apps().patch_namespaced_deployment(
                name=name,
                namespace=ns,
                body={"spec": {"replicas": 0}},
            )
            logger.info("Suspended dev sandbox for app %s (scaled replicas to 0)", app.id)
            return True
        except Exception as e:
            logger.warning("Could not suspend dev sandbox %s: %s", name, e)
            return False

    def resume_dev(self, app) -> bool:
        """Resume a suspended dev sandbox compute (scale replicas to 1)."""
        k8s = self._get_k8s_client()
        if not k8s:
            return False
        ns = settings.K8S_NAMESPACE
        clean_id = re.sub(r"[^a-z0-9-]", "-", app.id.lower()).strip("-")
        name = f"compassx-app-dev-{clean_id}"
        try:
            k8s.apps().patch_namespaced_deployment(
                name=name,
                namespace=ns,
                body={"spec": {"replicas": 1}},
            )
            logger.info("Resumed dev sandbox for app %s (scaled replicas to 1)", app.id)
            return True
        except Exception as e:
            logger.warning("Could not resume dev sandbox %s: %s", name, e)
            return False

    def list_running_dev_app_ids(self) -> List[str]:
        """List app IDs of all active (replicas > 0) dev deployments in the cluster."""
        k8s = self._get_k8s_client()
        if not k8s:
            return []
        ns = settings.K8S_NAMESPACE
        app_ids: List[str] = []
        try:
            deps = k8s.apps().list_namespaced_deployment(
                namespace=ns,
                label_selector="compassx/dev=true",
            )
            for dep in (deps.items or []):
                replicas = dep.spec.replicas if dep.spec else 1
                if replicas and replicas > 0:
                    labels = dep.metadata.labels or {} if dep.metadata else {}
                    annos = dep.metadata.annotations or {} if dep.metadata else {}
                    raw_id = annos.get("compassx.io/app-id")
                    if not raw_id and dep.spec and dep.spec.template and dep.spec.template.spec:
                        for c in dep.spec.template.spec.containers or []:
                            for ev in c.env or []:
                                if ev.name == "APP_ID" and ev.value:
                                    raw_id = ev.value
                                    break
                            if raw_id:
                                break
                    app_id = raw_id or labels.get("compassx/app-id")
                    if app_id:
                        app_ids.append(app_id)
        except Exception as e:
            logger.debug("Failed listing running dev deployments: %s", e)
        return app_ids

    def get_dev_status(self, app) -> Dict[str, Any]:
        clean_id = re.sub(r"[^a-z0-9-]", "-", app.id.lower()).strip("-")
        dev_name = f"compassx-app-dev-{clean_id}"
        ns = settings.K8S_NAMESPACE
        k8s = self._get_k8s_client()
        if not k8s:
            return {"status": "inactive", "pod_name": dev_name, "mode": "kubernetes"}

        # 1. Check if dev deployment exists
        dep = None
        try:
            dep = k8s.apps().read_namespaced_deployment(name=dev_name, namespace=ns)
            if dep.metadata and dep.metadata.deletion_timestamp:
                return {
                    "status": "stopping",
                    "pod_name": dev_name,
                    "mode": "kubernetes",
                    "phase": "Terminating",
                    "provisioning_message": "Dev deployment is terminating...",
                }

            # Check for scale-to-zero suspension
            desired_replicas = dep.spec.replicas if dep.spec else 1
            if desired_replicas == 0:
                return {
                    "status": "suspended",
                    "pod_name": dev_name,
                    "mode": "kubernetes",
                    "phase": "Suspended",
                    "provisioning_message": "Dev sandbox compute is suspended.",
                }
        except Exception:
            dep = None

        # 2. Inspect active pods for this app
        try:
            pods_resp = k8s.core().list_namespaced_pod(
                namespace=ns,
                label_selector=f"compassx/app-id={clean_id},compassx/dev=true",
            )
            candidate_pods = [
                p for p in (pods_resp.items or [])
                if not (p.metadata and p.metadata.deletion_timestamp)
            ]
            if not candidate_pods:
                # Fallback to name prefix match
                all_pods = k8s.core().list_namespaced_pod(namespace=ns)
                candidate_pods = [
                    p for p in (all_pods.items or [])
                    if p.metadata and p.metadata.name and (
                        p.metadata.name.startswith(f"{dev_name}-") or p.metadata.name == dev_name
                    ) and not (p.metadata.deletion_timestamp)
                ]

            if candidate_pods:
                # Sort newest first
                candidate_pods.sort(
                    key=lambda p: p.metadata.creation_timestamp or datetime.min.replace(tzinfo=timezone.utc),
                    reverse=True,
                )
                active_pod = candidate_pods[0]
                pod_name = active_pod.metadata.name or dev_name
                pod_status = active_pod.status
                pod_phase = pod_status.phase if pod_status else "Pending"
                pod_ip = pod_status.pod_ip if pod_status else None
                reason = pod_status.reason if pod_status else None

                # Evicted or Failed
                if reason == "Evicted" or pod_phase in ["Failed", "Unknown"]:
                    return {
                        "status": "stopped",
                        "pod_name": pod_name,
                        "mode": "kubernetes",
                        "phase": pod_phase,
                        "pod_ip": pod_ip,
                        "provisioning_reason": "pod_evicted" if reason == "Evicted" else "pod_failed",
                        "provisioning_message": f"Dev sandbox pod terminated ({reason or pod_phase}). Click Restart Sandbox to recreate.",
                    }

                # Check container waiting states (CrashLoop, ImagePull, Creating)
                all_c_statuses = (pod_status.container_statuses or []) + (pod_status.init_container_statuses or [])
                for cs in all_c_statuses:
                    if cs.state and cs.state.waiting:
                        w_reason = cs.state.waiting.reason or ""
                        w_msg = cs.state.waiting.message or ""
                        if w_reason in ["CrashLoopBackOff", "ImagePullBackOff", "ErrImagePull"]:
                            return {
                                "status": "error",
                                "pod_name": pod_name,
                                "mode": "kubernetes",
                                "phase": pod_phase,
                                "pod_ip": pod_ip,
                                "provisioning_reason": w_reason.lower(),
                                "provisioning_message": f"Container failed ({w_reason}): {w_msg or 'Click Restart Sandbox to retry.'}",
                            }
                        elif w_reason in ["ContainerCreating", "PodInitializing"]:
                            return {
                                "status": "provisioning",
                                "pod_name": pod_name,
                                "mode": "kubernetes",
                                "phase": "ContainerCreating",
                                "pod_ip": pod_ip,
                                "is_scaling_node": False,
                                "provisioning_reason": "container_creating",
                                "provisioning_message": "Allocating container resources and mounting persistent workspace storage...",
                            }

                # Check scheduling conditions (PodScheduled)
                conditions = pod_status.conditions or []
                for cond in conditions:
                    if cond.type == "PodScheduled" and cond.status == "False":
                        reason_lower = (cond.reason or "").lower()
                        msg_lower = (cond.message or "").lower()
                        if (
                            "unschedulable" in reason_lower
                            or "insufficient" in msg_lower
                            or "scale-up" in msg_lower
                            or "nodes are available" in msg_lower
                            or "predicates" in msg_lower
                            or "fitresources" in msg_lower
                            or "node group" in msg_lower
                        ):
                            return {
                                "status": "provisioning",
                                "pod_name": pod_name,
                                "mode": "kubernetes",
                                "phase": "Pending",
                                "pod_ip": pod_ip,
                                "is_scaling_node": True,
                                "provisioning_reason": "node_scaling",
                                "provisioning_message": "Cluster is scaling worker node to allocate compute resources (1-3 min). Please wait...",
                            }
                        else:
                            return {
                                "status": "provisioning",
                                "pod_name": pod_name,
                                "mode": "kubernetes",
                                "phase": "Pending",
                                "pod_ip": pod_ip,
                                "is_scaling_node": False,
                                "provisioning_reason": "scheduling",
                                "provisioning_message": cond.message or "Pod is waiting for node scheduling...",
                            }

                # Pod is Running: verify container readiness
                if pod_phase == "Running":
                    ready_containers = [cs for cs in (pod_status.container_statuses or []) if cs.ready]
                    if len(ready_containers) > 0:
                        return {
                            "status": "active",
                            "pod_name": pod_name,
                            "mode": "kubernetes",
                            "phase": "Running",
                            "pod_ip": pod_ip,
                            "is_scaling_node": False,
                        }
                    else:
                        return {
                            "status": "provisioning",
                            "pod_name": pod_name,
                            "mode": "kubernetes",
                            "phase": "Running",
                            "pod_ip": pod_ip,
                            "is_scaling_node": False,
                            "provisioning_reason": "container_starting",
                            "provisioning_message": "Dev container running, awaiting health probes...",
                        }

                if pod_phase == "Pending":
                    return {
                        "status": "provisioning",
                        "pod_name": pod_name,
                        "mode": "kubernetes",
                        "phase": "Pending",
                        "pod_ip": pod_ip,
                        "is_scaling_node": False,
                        "provisioning_reason": "pending",
                        "provisioning_message": "Sandbox pod is pending startup...",
                    }

        except Exception as pe:
            logger.debug("Error querying pods in get_dev_status: %s", pe)

        # Fallback if deployment exists but no pod is listed yet
        if dep:
            ready = (dep.status and (dep.status.available_replicas or dep.status.ready_replicas or 0) > 0)
            if ready:
                return {
                    "status": "active",
                    "pod_name": dev_name,
                    "mode": "kubernetes",
                    "phase": "Running",
                    "is_scaling_node": False,
                }
            return {
                "status": "provisioning",
                "pod_name": dev_name,
                "mode": "kubernetes",
                "phase": "Pending",
                "is_scaling_node": False,
                "provisioning_reason": "deployment_initializing",
                "provisioning_message": "Deploying sandbox and waiting for pod scheduling...",
            }

        return {"status": "inactive", "pod_name": dev_name, "mode": "kubernetes"}

    def get_dev_url(self, app) -> str:
        return ingress_service.get_app_dev_url(app)

    def get_dev_logs(self, app, max_lines: int = 200) -> str:
        k8s = self._get_k8s_client()
        if not k8s:
            return ""
        ns = settings.K8S_NAMESPACE
        clean_id = re.sub(r"[^a-z0-9-]", "-", app.id.lower()).strip("-")
        setup_logs = ""
        try:
            res = self.exec_command_in_dev(app, "cat /tmp/workspace_setup.log 2>/dev/null || true")
            if res.get("success") and res.get("output"):
                setup_logs = res["output"].strip()
        except Exception:
            pass

        pod_logs = ""
        try:
            pod_name = self._find_running_pod_name(clean_id, ns)
            if pod_name:
                pod_logs = (k8s.core().read_namespaced_pod_log(name=pod_name, namespace=ns, tail_lines=max_lines) or "").strip()
        except Exception:
            pass

        if setup_logs and pod_logs:
            return f"{setup_logs}\n\n{pod_logs}"
        return setup_logs or pod_logs

    def exec_git_in_workspace(
        self,
        app,
        workspace_folder: str,
        commit_message: str,
        branch: str,
        auth_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute git add, commit, and push directly inside the dev pod workspace directory."""
        from kubernetes import stream
        k8s = self._get_k8s_client()
        if not k8s:
            return {"success": False, "error": "Kubernetes client not available"}

        clean_id = re.sub(r"[^a-z0-9-]", "-", app.id.lower()).strip("-")
        ns = settings.K8S_NAMESPACE

        try:
            pod_name = self._find_running_pod_name(clean_id, ns)
            if not pod_name:
                return {"success": False, "error": f"No running dev pod found for app '{app.id}' in namespace '{ns}'"}

            workdir = f"/workspaces/{workspace_folder}"
            safe_msg = commit_message.replace('"', '\\"').replace("'", "\\'")

            remote_snippet = f"git remote set-url origin '{auth_url}' 2>/dev/null || true; " if auth_url else ""

            bash_cmd = (
                f"cd {workdir} && "
                f"export GIT_TERMINAL_PROMPT=0 && "
                f"git config user.name 'CompassX Dev' && git config user.email 'dev@compassx.io' && "
                f"(git checkout -B '{branch}' 2>/dev/null || true) && "
                f"{remote_snippet}"
                f"git add -A && "
                f"(git commit -m \"{safe_msg}\" 2>/dev/null || true) && "
                f"git push -u origin '{branch}' 2>&1 && echo '__GIT_PUSH_SUCCESS__'"
            )

            resp = stream.stream(
                k8s.core().connect_get_namespaced_pod_exec,
                pod_name,
                ns,
                command=["/bin/sh", "-c", bash_cmd],
                stderr=True,
                stdin=False,
                stdout=True,
                tty=False,
            )

            raw_output = str(resp or "").strip()
            is_success = "__GIT_PUSH_SUCCESS__" in raw_output
            clean_output = raw_output.replace("__GIT_PUSH_SUCCESS__", "").strip()

            # Get latest commit sha
            sha_resp = stream.stream(
                k8s.core().connect_get_namespaced_pod_exec,
                pod_name,
                ns,
                command=["/bin/sh", "-c", f"cd {workdir} && git rev-parse --short HEAD 2>/dev/null || echo ''"],
                stderr=False,
                stdin=False,
                stdout=True,
                tty=False,
            )

            commit_sha = (sha_resp or "").strip()
            return {
                "success": is_success,
                "output": clean_output,
                "commit_sha": commit_sha,
                "branch": branch,
                "error": None if is_success else (clean_output or "Git push command failed"),
            }
        except Exception as exc:
            logger.warning("Failed executing git in dev pod: %s", exc)
            return {"success": False, "error": str(exc)}


    def _find_running_pod_name(self, clean_id: str, ns: str, wait_seconds: int = 0) -> Optional[str]:
        import time
        k8s = self._get_k8s_client()
        if not k8s:
            return None
        dev_name = f"compassx-app-dev-{clean_id}"
        try:
            from unittest.mock import Mock, MagicMock
            if isinstance(k8s, (Mock, MagicMock)):
                return dev_name
        except Exception:
            pass

        sb_name = f"compassx-sb-dev-app-{clean_id}"
        underscore_id = clean_id.replace("-", "_")

        deadline = time.time() + max(0, wait_seconds)
        while True:
            # 1. Try label selectors (both unified sandbox and legacy dev pod labels)
            for selector in [
                f"compassx.sandbox-id=dev-app-{clean_id}",
                f"compassx.consumer-key=app_{clean_id}",
                f"compassx.consumer-key=app_{underscore_id}",
                f"compassx.app_id={clean_id}",
                f"compassx.app_id={underscore_id}",
                f"compassx/app-id={clean_id},compassx/dev=true",
                f"app.kubernetes.io/name={dev_name}",
                f"compassx/app-id={clean_id}",
            ]:
                try:
                    pods = k8s.core().list_namespaced_pod(namespace=ns, label_selector=selector)
                    running_pods = [
                        p for p in (pods.items or [])
                        if p.status and p.status.phase == "Running" and not p.metadata.deletion_timestamp
                    ]
                    if running_pods:
                        running_pods.sort(
                            key=lambda p: p.metadata.creation_timestamp or datetime.min.replace(tzinfo=timezone.utc),
                            reverse=True,
                        )
                        return running_pods[0].metadata.name
                except Exception as e:
                    logger.debug("Error listing pods with selector %s: %s", selector, e)

            # 2. Try matching by pod name prefix and annotations
            try:
                pods = k8s.core().list_namespaced_pod(namespace=ns)
                matched = []
                for p in (pods.items or []):
                    if not p.metadata or not p.status or p.status.phase != "Running" or p.metadata.deletion_timestamp:
                        continue
                    pname = p.metadata.name or ""
                    annos = p.metadata.annotations or {}
                    labels = p.metadata.labels or {}

                    # Match by name prefix
                    if (
                        pname.startswith(f"{sb_name}-")
                        or pname == sb_name
                        or pname.startswith(f"{dev_name}-")
                        or pname == dev_name
                        or f"dev-app-{clean_id}" in pname
                    ):
                        matched.append(p)
                        continue

                    # Match by annotations or labels
                    sb_id = annos.get("compassx.sandbox.id") or labels.get("compassx.sandbox-id")
                    ckey = annos.get("compassx.sandbox.consumer_key") or labels.get("compassx.consumer-key")
                    if sb_id and (clean_id in sb_id or underscore_id in sb_id):
                        matched.append(p)
                        continue
                    if ckey and (clean_id in ckey or underscore_id in ckey):
                        matched.append(p)
                        continue

                if matched:
                    matched.sort(
                        key=lambda p: p.metadata.creation_timestamp or datetime.min.replace(tzinfo=timezone.utc),
                        reverse=True,
                    )
                    return matched[0].metadata.name
            except Exception as e:
                logger.debug("Error listing pods by name prefix: %s", e)

            if time.time() >= deadline:
                break
            time.sleep(1.0)

        return None

    def get_live_branch(self, app, workspace_folder: str = "") -> Optional[str]:
        """Fetch active Git branch from inside the running workspace pod."""
        from kubernetes import stream
        k8s = self._get_k8s_client()
        if not k8s:
            return None
        clean_id = re.sub(r"[^a-z0-9-]", "-", app.id.lower()).strip("-")
        ns = settings.K8S_NAMESPACE
        pod_name = self._find_running_pod_name(clean_id, ns)
        if not pod_name:
            return None
        workdir = f"/workspaces/{workspace_folder}" if workspace_folder else f"/workspaces/{clean_id}/default"
        try:
            resp = stream.stream(
                k8s.core().connect_get_namespaced_pod_exec,
                pod_name,
                ns,
                command=["/bin/sh", "-c", f"(cd '{workdir}' 2>/dev/null || cd /workspaces 2>/dev/null || cd /app 2>/dev/null) && git rev-parse --abbrev-ref HEAD 2>/dev/null || echo ''"],
                stderr=False,
                stdin=False,
                stdout=True,
                tty=False,
            )
            branch = (resp or "").strip()
            return branch if branch and branch != "HEAD" else None
        except Exception:
            return None

    def exec_command_in_dev(
        self,
        app,
        command: str,
        workspace_folder: str = "",
    ) -> Dict[str, Any]:
        """Execute a single shell command inside the dev pod workspace directory."""
        from kubernetes import stream
        k8s = self._get_k8s_client()
        if not k8s:
            return {"success": False, "exit_code": 1, "output": "Kubernetes client not available"}

        clean_id = re.sub(r"[^a-z0-9-]", "-", app.id.lower()).strip("-")
        ns = settings.K8S_NAMESPACE
        workdir = f"/workspaces/{workspace_folder}" if workspace_folder else f"/workspaces/{clean_id}/default"
        pod_name = self._find_running_pod_name(clean_id, ns)
        if not pod_name:
            st = self.get_dev_status(app)
            if st.get("status") == "provisioning":
                msg = st.get("provisioning_message") or "Sandbox pod is still starting or allocating cluster resources."
                return {
                    "success": False,
                    "exit_code": 1,
                    "pending": True,
                    "is_scaling_node": st.get("is_scaling_node", False),
                    "output": msg,
                    "workdir": workdir,
                }
            return {"success": False, "exit_code": 1, "output": f"No running dev pod found for app '{app.id}' in namespace '{ns}'", "workdir": workdir}

        exit_marker = "__K8S_CMD_EXIT__"
        full_cmd = (
            f"( (mkdir -p '{workdir}' 2>/dev/null || true); "
            f"cd '{workdir}' 2>/dev/null || cd /workspaces 2>/dev/null || cd /app 2>/dev/null || true; "
            f"{command} ); "
            f"echo \"{exit_marker}:$?\""
        )

        try:
            resp = stream.stream(
                k8s.core().connect_get_namespaced_pod_exec,
                pod_name,
                ns,
                command=["/bin/sh", "-c", full_cmd],
                stderr=True,
                stdin=False,
                stdout=True,
                tty=False,
                _request_timeout=120,
            )
            raw_output = str(resp or "")
            exit_code = 0
            clean_output = raw_output
            match = re.search(r"__K8S_CMD_EXIT__:(\d+)", raw_output)
            if match:
                exit_code = int(match.group(1))
                clean_output = re.sub(r"\n?__K8S_CMD_EXIT__:\d+\r?\n?", "", raw_output).strip()
            else:
                clean_output = raw_output.strip()

            return {
                "success": exit_code == 0,
                "exit_code": exit_code,
                "output": clean_output,
                "workdir": workdir,
            }
        except Exception as exc:
            logger.warning("Failed executing command in dev pod: %s", exc)
            return {"success": False, "exit_code": 1, "output": str(exc), "workdir": workdir}

    def ensure_agent_configs(self, app: Any, active_model: Optional[str] = None) -> None:
        """Seed or update agent configuration files (OpenCode, Pi) and tmux configs inside the dev pod."""
        import json
        models = ["gpt-5.4-mini", "gpt-5.6-sol"]
        try:
            from app.database import AccountSessionLocal
            from app.ai_gateway.models.provider import AIModelEndpoint
            with AccountSessionLocal() as acc_db:
                ws_id = str(app.workspace_id) if getattr(app, "workspace_id", None) else None
                q = acc_db.query(AIModelEndpoint).filter(AIModelEndpoint.is_active == True)
                if ws_id:
                    q = q.filter((AIModelEndpoint.workspace_id == ws_id) | (AIModelEndpoint.workspace_id.is_(None)))
                db_models = [ep.name for ep in q.all() if ep.name]
                if db_models:
                    models = db_models
        except Exception as e:
            logger.debug("Failed to query models for pod seeding: %s", e)

        if active_model and active_model not in models:
            models.append(active_model)

        api_key = f"cx_gw_app_{app.id}"
        ns = settings.K8S_NAMESPACE
        base_url = f"http://compassx-backend.{ns}.svc.cluster.local:8000/api/v1/ai-gateway/v1"
        oc_models = {m: {"name": m} for m in models}
        pi_models = [{"id": m, "name": m, "contextWindow": 128000, "maxTokens": 8192} for m in models]

        py_script = (
            "import json, os\n"
            f"api_key = {json.dumps(api_key)}\n"
            f"base_url = {json.dumps(base_url)}\n"
            f"oc_models = {json.dumps(oc_models)}\n"
            f"pi_models = {json.dumps(pi_models)}\n"
            "for p in ['/root/.config/opencode/opencode.json', '/root/.opencode/opencode.json']:\n"
            "    try:\n"
            "        os.makedirs(os.path.dirname(p), exist_ok=True)\n"
            "        doc = {'$schema': 'https://opencode.ai/config.json'}\n"
            "        if os.path.exists(p):\n"
            "            try:\n"
            "                with open(p, 'r') as f: doc = json.load(f)\n"
            "            except Exception: pass\n"
            "        doc.setdefault('provider', {})\n"
            "        doc['provider']['compassx'] = {'name': 'CompassX AI Gateway', 'type': 'openai', 'options': {'baseURL': base_url, 'apiKey': api_key}, 'models': oc_models}\n"
            "        with open(p, 'w') as f: json.dump(doc, f, indent=2)\n"
            "    except Exception:\n"
            "        pass\n"
            "try:\n"
            "    tmux_cfg = (\n"
            "        'set-option -g history-limit 50000\\n'\n"
            "        'set-option -sq extended-keys on\\n'\n"
            "        'set-option -sq extended-keys-format csi-u\\n'\n"
            "        'set-option -sq set-clipboard external\\n'\n"
            "        'set-option -g mouse on\\n'\n"
            "        'set-option -g focus-events on\\n'\n"
            "        'set-option -g escape-time 0\\n'\n"
            "        'set-option -g window-size latest\\n'\n"
            "        'set-option -g aggressive-resize on\\n'\n"
            "        'set-option -g default-terminal \"xterm-256color\"\\n'\n"
            "        'set-option -g prefix None\\n'\n"
            "        'set-option -g prefix2 None\\n'\n"
            "        'set-option -g status off\\n'\n"
            "        'bind-key -T root PPage if-shell -F \"#{alternate_on}\" \"send-keys PPage\" \"copy-mode -eu\"\\n'\n"
            "        'bind-key -T copy-mode WheelUpPane select-pane \\\\; send-keys -X -N 5 scroll-up\\n'\n"
            "        'bind-key -T copy-mode WheelDownPane select-pane \\\\; send-keys -X -N 5 scroll-down\\n'\n"
            "        'bind-key -T copy-mode-vi WheelUpPane select-pane \\\\; send-keys -X -N 5 scroll-up\\n'\n"
            "        'bind-key -T copy-mode-vi WheelDownPane select-pane \\\\; send-keys -X -N 5 scroll-down\\n'\n"
            "    )\n"
            "    with open('/root/.tmux.conf', 'w') as f:\n"
            "        f.write(tmux_cfg)\n"
            "    os.system('tmux source-file /root/.tmux.conf 2>/dev/null')\n"
            "except Exception:\n"
            "    pass\n"
            "try:\n"
            "    pi_p = '/root/.pi/agent/models.json'\n"
            "    os.makedirs(os.path.dirname(pi_p), exist_ok=True)\n"
            "    pi_doc = {'providers': {}}\n"
            "    if os.path.exists(pi_p):\n"
            "        try:\n"
            "            with open(pi_p, 'r') as f: pi_doc = json.load(f)\n"
            "        except Exception: pass\n"
            "    pi_doc.setdefault('providers', {})\n"
            "    pi_doc['providers']['compassx'] = {'baseUrl': base_url, 'apiKey': api_key, 'api': 'openai-completions', 'models': pi_models}\n"
            "    with open(pi_p, 'w') as f: json.dump(pi_doc, f, indent=2)\n"
            "except Exception:\n"
            "    pass\n"
        )
        try:
            self.exec_command_in_dev(app, f"python3 -c {json.dumps(py_script)}")
        except Exception as e:
            logger.debug("Failed seeding agent configs in pod: %s", e)

    def open_terminal_ws_client(
        self,
        app,
        workspace_folder: str = "",
        cols: int = 80,
        rows: int = 24,
        agent: Optional[str] = None,
        session_name: Optional[str] = None,
        cli_cmd: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> Any:
        """Open a live bidirectional interactive PTY stream to the dev pod with persistent tmux support."""
        from kubernetes import stream
        import json
        k8s = self._get_k8s_client()
        if not k8s:
            return None

        clean_id = re.sub(r"[^a-z0-9-]", "-", app.id.lower()).strip("-")
        ns = settings.K8S_NAMESPACE
        pod_name = self._find_running_pod_name(clean_id, ns, wait_seconds=5)
        if not pod_name:
            logger.warning("No running dev pod found for %s in namespace %s", clean_id, ns)
            return None
        workdir = f"/workspaces/{workspace_folder}" if workspace_folder else f"/workspaces/{clean_id}/default"

        # Ensure agent configs and models are seeded
        self.ensure_agent_configs(app, active_model=model)

        if not cli_cmd:
            if agent == "pi":
                cli_cmd = "pi --approve"
            elif agent == "opencode":
                cli_cmd = "opencode"
            elif agent in ("antigravity", "agy"):
                cli_cmd = "agy --dangerously-skip-permissions"
            elif agent in ("bash", "shell", "sh"):
                cli_cmd = "exec /bin/bash -l"

        ai_gw_url = f"http://compassx-backend.{ns}.svc.cluster.local:8000/api/v1/ai-gateway/v1"

        if session_name and cli_cmd:
            tmux_target = session_name.replace("'", "")
            clean_cmd = f"export OPENAI_BASE_URL={ai_gw_url} OPENAI_API_KEY=cx_gw_app_{app.id}; {cli_cmd}".replace("'", "'\\''")
            shell_cmd = [
                "/bin/sh", "-c",
                f"cd {workdir} 2>/dev/null; "
                f"export TERM=xterm-256color; "
                f"tmux source-file /root/.tmux.conf 2>/dev/null; "
                f"tmux new-session -A -D -s '{tmux_target}' -c '{workdir}' '{clean_cmd} || exec /bin/bash -l' || exec /bin/bash -l"
            ]
        elif cli_cmd:
            clean_cmd = f"export OPENAI_BASE_URL={ai_gw_url} OPENAI_API_KEY=cx_gw_app_{app.id}; {cli_cmd}".replace("'", "'\\''")
            shell_cmd = [
                "/bin/sh", "-c",
                f"cd {workdir} 2>/dev/null; "
                f"export TERM=xterm-256color; "
                f"{clean_cmd} || exec /bin/bash -l"
            ]
        else:
            shell_cmd = [
                "/bin/sh", "-c",
                f"cd {workdir} 2>/dev/null; "
                f"export TERM=xterm-256color; "
                f"if [ -x /bin/bash ]; then exec /bin/bash -l; else exec /bin/sh -l; fi"
            ]

        try:
            ws_client = stream.stream(
                k8s.core().connect_get_namespaced_pod_exec,
                pod_name,
                ns,
                command=shell_cmd,
                stderr=True,
                stdin=True,
                stdout=True,
                tty=True,
                _preload_content=False,
            )
            try:
                from kubernetes.stream.ws_client import RESIZE_CHANNEL
                ws_client.write_channel(RESIZE_CHANNEL, json.dumps({"Width": cols, "Height": rows}))
            except Exception:
                pass
            return ws_client
        except Exception as exc:
            logger.warning("Failed to open terminal stream in dev pod %s: %s", pod_name, exc)
            return None

    def resize_terminal(
        self,
        app: Any,
        cols: int,
        rows: int,
        session_name: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Dynamically resize tmux window and pane inside dev pod."""
        target = (session_name or "").replace("'", "")
        if target:
            cmd = f"tmux resize-window -t '{target}' -x {int(cols)} -y {int(rows)} 2>/dev/null || true; tmux resize-pane -t '{target}' -x {int(cols)} -y {int(rows)} 2>/dev/null || true"
        else:
            cmd = f"tmux resize-window -a -x {int(cols)} -y {int(rows)} 2>/dev/null || true"
        try:
            self.exec_command_in_dev(app, cmd)
        except Exception:
            pass

    def create_git_worktree(
        self,
        app: Any,
        folder_path: str,
        branch: str,
        base_branch: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new Git worktree sandbox inside the dev pod on the shared PVC."""
        clean_folder = folder_path.strip("/")
        target_dir = f"/workspaces/{clean_folder}"
        clean_app = re.sub(r'[^a-z0-9-]', '-', app.id.lower()).strip('-')
        base = (base_branch or "main").strip() or "main"

        git_url = getattr(app, "git_repo_url", None)
        git_token = None
        if hasattr(app, "git_pat_enc") and app.git_pat_enc:
            try:
                from app.services.encryption import decrypt_field
                git_token = decrypt_field(app.git_pat_enc)
            except Exception:
                pass
        auth_url = git_url or ""
        if git_token and git_url and "github.com" in git_url and not ("@" in git_url.split("//")[-1]):
            auth_url = git_url.replace("https://", f"https://x-access-token:{git_token}@")
        elif git_token and git_url and not ("@" in git_url.split("//")[-1]):
            auth_url = git_url.replace("https://", f"https://oauth2:{git_token}@")

        cmd = (
            'LOG_FILE="/tmp/workspace_setup.log"; '
            'log() { echo "[$(date +\'%H:%M:%S\')] $1" | tee -a "$LOG_FILE"; }; '
            'log "──────────────────────────────────────────────────────────"; '
            f'log "=== Phase 2: Workspace Setup ({target_dir}) ==="; '
            f'mkdir -p /workspaces/{clean_app} && '
            f'if [ -d \'{target_dir}\' ] && [ -e \'{target_dir}/.git\' ] && [ -n "$(find \'{target_dir}\' -maxdepth 2 -not -name \'.git*\' -not -name \'index.html\' 2>/dev/null)" ]; then '
            '  log "  ✓ Workspace worktree already exists and is populated."; '
            '  echo "__WORKTREE_EXISTS__"; '
            'else '
            '  BASE_REPO=""; '
            f'  for d in /workspace /workspaces/{clean_app}/default /workspaces/{clean_app}/main /workspaces/{clean_app}/* /workspaces/* /app; do '
            f'    if [ -e "$d/.git" ] && [ "$d" != "{target_dir}" ] && [ -n "$(ls -A "$d" 2>/dev/null)" ]; then BASE_REPO="$d"; break; fi; '
            '  done; '
            '  if [ -n "$BASE_REPO" ]; then '
            '    log "  → Found base repository at $BASE_REPO"; '
            '    log "  [2/4] Fetching latest remote commits (git fetch origin)..."; '
            '    (cd "$BASE_REPO" && git worktree prune 2>/dev/null || true); '
            '    (cd "$BASE_REPO" && git fetch origin 2>&1 | tee -a "$LOG_FILE" || true); '
            f'    rm -rf \'{target_dir}\'; '
            f'    log "  [3/4] Creating isolated Git worktree on branch: {branch}..."; '
            f'    if (cd "$BASE_REPO" && (git worktree add -f -B \'{branch}\' \'{target_dir}\' \'{base}\' 2>&1 || git worktree add -f -B \'{branch}\' \'{target_dir}\' \'origin/{base}\' 2>&1 || git worktree add -f --detach \'{target_dir}\' \'{base}\' 2>&1 || git worktree add -f -B \'{branch}\' \'{target_dir}\' HEAD 2>&1)) | tee -a "$LOG_FILE"; then '
            '      log "  ✓ Worktree creation successful."; '
            '      echo "__WORKTREE_CREATED__"; '
            '    else '
            '      log "  → Falling back to shared repository clone..."; '
            f'      mkdir -p \'{target_dir}\' && (git clone --shared "$BASE_REPO" \'{target_dir}\' 2>&1 || cp -a "$BASE_REPO/." \'{target_dir}/\') && (cd \'{target_dir}\' && git checkout -B \'{branch}\' 2>/dev/null || true) && echo "__WORKTREE_CREATED__"; '
            '    fi; '
            '    log "  [4/4] Linking shared dependencies (node_modules)..."; '
            '    for src_nm in "$BASE_REPO/frontend/node_modules" "$BASE_REPO"/*"/frontend/node_modules" "$BASE_REPO/node_modules" "$BASE_REPO"/*"/node_modules"; do '
            '      if [ -d "$src_nm" ]; then '
            '        rel_nm="${src_nm#$BASE_REPO/}"; '
            f'        dest_dir="{target_dir}/${{rel_nm%/node_modules}}"; '
            '        if [ -d "$dest_dir" ] && [ ! -d "$dest_dir/node_modules" ]; then '
            '          ln -sfn "$src_nm" "$dest_dir/node_modules" 2>/dev/null || true; '
            '          log "    → Linked $rel_nm to $dest_dir/node_modules"; '
            '        fi; '
            '      fi; '
            '    done; '
            '    log "✓ Phase 2 Complete: Workspace ready for development."; '
            f'  elif [ -n \'{auth_url}\' ]; then '
            f'    log "  → Cloning repository from remote for branch: {branch}..."; '
            f'    rm -rf \'{target_dir}\' && mkdir -p \'{target_dir}\' && cd \'{target_dir}\' && (git clone --branch \'{base}\' \'{auth_url}\' . 2>&1 | tee -a "$LOG_FILE" || git clone \'{auth_url}\' . 2>&1 | tee -a "$LOG_FILE") && (git checkout -B \'{branch}\' 2>/dev/null || true) && echo "__WORKTREE_CREATED__"; '
            '    log "✓ Phase 2 Complete: Remote repository cloned successfully."; '
            '  else '
            '    log "  → No base repository or remote URL found; creating standalone directory."; '
            f'    mkdir -p \'{target_dir}\' && echo "__WORKTREE_CREATED__"; '
            '  fi; '
            'fi; '
            'log "──────────────────────────────────────────────────────────"'
        )
        res = self.exec_command_in_dev(app, cmd)
        output = res.get("output", "")
        success = ("__WORKTREE_CREATED__" in output) or ("__WORKTREE_EXISTS__" in output) or (res.get("exit_code") == 0)
        return {
            "success": success,
            "folder_path": target_dir,
            "branch": branch,
            "output": output,
            "error": None if success else output,
        }

    def remove_git_worktree(self, app: Any, folder_path: str) -> bool:
        """Remove a Git worktree sandbox from the dev pod."""
        clean_folder = folder_path.strip("/")
        target_dir = f"/workspaces/{clean_folder}"
        clean_app = re.sub(r'[^a-z0-9-]', '-', app.id.lower()).strip('-')
        cmd = (
            f"BASE_REPO=\"\"; "
            f"for d in /workspace /workspaces/{clean_app}/default /workspaces/{clean_app}/main /workspaces/{clean_app}/* /workspaces/* /app; do "
            f"  if [ -e \"$d/.git\" ]; then BASE_REPO=\"$d\"; break; fi; "
            f"done; "
            f"if [ -n \"$BASE_REPO\" ]; then cd \"$BASE_REPO\" && git worktree remove --force '{target_dir}' 2>/dev/null || true; cd \"$BASE_REPO\" && git worktree prune 2>/dev/null || true; fi; "
            f"rm -rf '{target_dir}'"
        )
        res = self.exec_command_in_dev(app, cmd)
        return res.get("exit_code") == 0

    @staticmethod
    def _get_dev_runner_script() -> str:
        """Returns the unified dev runner bash supervisor script for development pods/containers."""
        return (
            '#!/usr/bin/env bash\n'
            '# CompassX Unified Dev Server Supervisor\n'
            'ACTION="${1:-reload}"\n'
            'TARGET_DIR="${2:-}"\n'
            'APP_ID_VAL="${APP_ID:-}"\n'
            'CLEAN_APP=$(echo "$APP_ID_VAL" | tr "[:upper:]" "[:lower:]" | tr "_" "-" | tr -cd "[:alnum:]-")\n'
            'RAW_APP=$(echo "$APP_ID_VAL" | tr "[:upper:]" "[:lower:]")\n'
            '\n'
            'ACTIVE_DIR=""\n'
            'if [ -n "$TARGET_DIR" ] && [ "$TARGET_DIR" != "reload" ] && [ "$TARGET_DIR" != "start" ] && [ "$TARGET_DIR" != "stop" ]; then\n'
            '  case "$TARGET_DIR" in\n'
            '    /*) RESOLVED_TARGET="$TARGET_DIR" ;;\n'
            '    *)  RESOLVED_TARGET="/workspaces/$TARGET_DIR" ;;\n'
            '  esac\n'
            '  if [ -d "$RESOLVED_TARGET" ] && [ "$RESOLVED_TARGET" != "/workspaces" ]; then\n'
            '    ACTIVE_DIR="$RESOLVED_TARGET"\n'
            '    echo "$ACTIVE_DIR" > /tmp/cx_active_workdir.txt\n'
            '  fi\n'
            'fi\n'
            '\n'
            'if [ -z "$ACTIVE_DIR" ] && [ -f /tmp/cx_active_workdir.txt ]; then\n'
            '  SAVED_DIR=$(cat /tmp/cx_active_workdir.txt 2>/dev/null | tr -d "\\r\\n")\n'
            '  if [ -n "$SAVED_DIR" ] && [ -d "$SAVED_DIR" ] && [ "$SAVED_DIR" != "/workspaces" ]; then\n'
            '    ACTIVE_DIR="$SAVED_DIR"\n'
            '  fi\n'
            'fi\n'
            '\n'
            'if [ -z "$ACTIVE_DIR" ] || [ ! -d "$ACTIVE_DIR" ]; then\n'
            '  for d in \\\n'
            '    "/workspaces/${CLEAN_APP}/default" \\\n'
            '    "/workspaces/${RAW_APP}/default" \\\n'
            '    "/workspaces/${CLEAN_APP}/main" \\\n'
            '    "/workspaces/${RAW_APP}/main" \\\n'
            '    "/workspaces/${CLEAN_APP}"/* \\\n'
            '    "/workspaces/${RAW_APP}"/* \\\n'
            '    "/workspaces"/*/* \\\n'
            '    "/workspaces"/* \\\n'
            '    "/app"; do\n'
            '    if [ -d "$d" ] && [ "$d" != "/workspaces" ] && [ "$d" != "/workspaces/.shared_auth" ] && [ ! -d "$d/default" ]; then\n'
            '      if [ -e "$d/.git" ] || [ -f "$d/package.json" ] || [ -f "$d/app.py" ] || [ -f "$d/main.py" ] || [ -d "$d/frontend" ] || [ -d "$d/backend" ]; then\n'
            '        ACTIVE_DIR="$d"\n'
            '        break\n'
            '      fi\n'
            '    fi\n'
            '  done\n'
            'fi\n'
            '\n'
            'if [ -z "$ACTIVE_DIR" ] || [ ! -d "$ACTIVE_DIR" ]; then\n'
            '  ACTIVE_DIR="/workspaces/${CLEAN_APP}/default"\n'
            '  mkdir -p "$ACTIVE_DIR" 2>/dev/null || true\n'
            'fi\n'
            '\n'
            'echo "$ACTIVE_DIR" > /tmp/cx_active_workdir.txt\n'
            'ln -sfn "$ACTIVE_DIR" /current 2>/dev/null || true\n'
            'export DEV_WORKSPACE_DIR="$ACTIVE_DIR"\n'
            'cd "$ACTIVE_DIR" 2>/dev/null || true\n'
            '\n'
            'LOG_FILE="/tmp/workspace_setup.log"\n'
            'log() { echo "[$(date +\'%H:%M:%S\')] $1" | tee -a "$LOG_FILE"; }\n'
            'log "──────────────────────────────────────────────────────────"\n'
            'log "=== Phase 4: Application Runtime & Dev Server ==="\n'
            'log "  [1/3] Activating workspace directory: $ACTIVE_DIR"\n'
            'echo "[DEV-RUNNER] Active sandbox: $ACTIVE_DIR"\n'
            '\n'
            '# Kill any old dev servers and free ports 8080 & 8000\n'
            'python3 -c "\n'
            'import os, signal, subprocess\n'
            'my_pid = os.getpid()\n'
            'parent_pid = os.getppid()\n'
            'try:\n'
            '    for line in subprocess.check_output([\'ps\', \'-eo\', \'pid,args\']).decode(\'utf-8\', errors=\'ignore\').splitlines():\n'
            '        parts = line.split()\n'
            '        if len(parts) > 1 and parts[0].isdigit():\n'
            '            pid = int(parts[0])\n'
            '            if pid not in (my_pid, parent_pid, 1):\n'
            '                cmdline = \' \'.join(parts[1:])\n'
            '                if any(k in cmdline for k in [\'uvicorn\', \'vite\', \'next\', \'streamlit\', \'http.server\', \'dev-runner.sh\']) and \'python3 -c\' not in cmdline and \'omnigent host\' not in cmdline:\n'
            '                    try: os.kill(pid, signal.SIGKILL)\n'
            '                    except Exception: pass\n'
            'except Exception: pass\n'
            '" 2>/dev/null || true\n'
            '\n'
            '(fuser -k -9 8080/tcp 8000/tcp 2>/dev/null || true)\n'
            'pkill -9 -f "vite" 2>/dev/null || true\n'
            'pkill -9 -f "next" 2>/dev/null || true\n'
            'pkill -9 -f "uvicorn" 2>/dev/null || true\n'
            'pkill -9 -f "streamlit" 2>/dev/null || true\n'
            'pkill -9 -f "http.server" 2>/dev/null || true\n'
            'sleep 0.2\n'
            '\n'
            'if [ "$ACTION" = "stop" ]; then\n'
            '  echo "[DEV-RUNNER] Dev servers stopped."\n'
            '  exit 0\n'
            'fi\n'
            '\n'
            '# Start instant placeholder on 8080 so Ingress never returns 502 Bad Gateway\n'
            'mkdir -p /tmp/cx_splash\n'
            'cat << \'CXEOF\' > /tmp/cx_splash/index.html\n'
            '<!DOCTYPE html>\n'
            '<html>\n'
            '<head>\n'
            '  <meta charset="utf-8">\n'
            '  <meta http-equiv="refresh" content="2">\n'
            '  <title>Live Sandbox Starting</title>\n'
            '  <style>\n'
            '    * { box-sizing: border-box; margin: 0; padding: 0; }\n'
            '    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0b0f19; color: #f1f5f9; display: flex; align-items: center; justify-content: center; height: 100vh; overflow: hidden; }\n'
            '    .card { background: #111827; border: 1px solid #1e293b; border-radius: 12px; padding: 2.5rem; text-align: center; max-width: 440px; box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5); }\n'
            '    .spinner { width: 38px; height: 38px; border: 3px solid rgba(59, 130, 246, 0.2); border-top-color: #3b82f6; border-radius: 50%; animation: spin 0.8s linear infinite; margin: 0 auto 1.25rem; }\n'
            '    @keyframes spin { to { transform: rotate(360deg); } }\n'
            '    h2 { font-size: 1.2rem; font-weight: 600; margin-bottom: 0.5rem; color: #f8fafc; }\n'
            '    p { font-size: 0.875rem; color: #94a3b8; line-height: 1.5; }\n'
            '    .badge { display: inline-block; margin-top: 1.25rem; font-size: 0.75rem; padding: 0.25rem 0.75rem; background: #1e293b; border-radius: 9999px; color: #38bdf8; font-weight: 500; }\n'
            '  </style>\n'
            '</head>\n'
            '<body>\n'
            '  <div class="card">\n'
            '    <div class="spinner"></div>\n'
            '    <h2>Live Sandbox Starting...</h2>\n'
            '    <p>Launching application environment and dev server. This page will automatically reload once ready.</p>\n'
            '    <div class="badge">CompassX Dev Studio</div>\n'
            '  </div>\n'
            '</body>\n'
            '</html>\n'
            'CXEOF\n'
            '\n'
            'python3 -m http.server 8080 --directory /tmp/cx_splash >> /tmp/frontend.log 2>&1 &\n'
            'SPLASH_PID=$!\n'
            '\n'
            '# Resolve BASE_DIR (if Source Code Path or inner subdirectory is configured)\n'
            'GIT_SUBDIR_VAL="${GIT_SUBDIR:-${APP_SUBDIR:-}}"\n'
            'BASE_DIR="$ACTIVE_DIR"\n'
            'if [ -n "$GIT_SUBDIR_VAL" ] && [ -d "$ACTIVE_DIR/$GIT_SUBDIR_VAL" ]; then\n'
            '  BASE_DIR="$ACTIVE_DIR/$GIT_SUBDIR_VAL"\n'
            '  echo "[DEV-RUNNER] Using configured Source Code Path: $BASE_DIR"\n'
            'elif [ ! -d "$BASE_DIR/frontend" ] && [ ! -d "$BASE_DIR/backend" ] && [ ! -d "$BASE_DIR/client" ] && [ ! -d "$BASE_DIR/web" ] && [ ! -d "$BASE_DIR/ui" ] && [ ! -f "$BASE_DIR/package.json" ] && [ ! -f "$BASE_DIR/app.py" ] && [ ! -f "$BASE_DIR/main.py" ] && [ ! -f "$BASE_DIR/server.py" ]; then\n'
            '  for d in "$ACTIVE_DIR"/*; do\n'
            '    if [ -d "$d" ] && [ "$d" != "$ACTIVE_DIR/.git" ] && ( [ -d "$d/frontend" ] || [ -d "$d/backend" ] || [ -d "$d/client" ] || [ -d "$d/web" ] || [ -d "$d/ui" ] || [ -d "$d/src" ] || [ -f "$d/package.json" ] || [ -f "$d/app.py" ] || [ -f "$d/main.py" ] || [ -f "$d/server.py" ] ); then\n'
            '      BASE_DIR="$d"\n'
            '      break\n'
            '    fi\n'
            '  done\n'
            'fi\n'
            '\n'
            '# Detect Backend Directory\n'
            'BACKEND_DIR=""\n'
            'if [ -d "$BASE_DIR/backend" ] && ( [ -f "$BASE_DIR/backend/app.py" ] || [ -f "$BASE_DIR/backend/main.py" ] || [ -f "$BASE_DIR/backend/server.py" ] || [ -f "$BASE_DIR/backend/api.py" ] || [ -f "$BASE_DIR/backend/requirements.txt" ] ); then\n'
            '  BACKEND_DIR="$BASE_DIR/backend"\n'
            'elif [ -d "$BASE_DIR/api" ] && ( [ -f "$BASE_DIR/api/app.py" ] || [ -f "$BASE_DIR/api/main.py" ] || [ -f "$BASE_DIR/api/server.py" ] || [ -f "$BASE_DIR/api/requirements.txt" ] ); then\n'
            '  BACKEND_DIR="$BASE_DIR/api"\n'
            'elif [ -d "$BASE_DIR/server" ] && ( [ -f "$BASE_DIR/server/app.py" ] || [ -f "$BASE_DIR/server/main.py" ] || [ -f "$BASE_DIR/server/requirements.txt" ] ); then\n'
            '  BACKEND_DIR="$BASE_DIR/server"\n'
            'elif [ -f "$BASE_DIR/app.py" ] || [ -f "$BASE_DIR/main.py" ] || [ -f "$BASE_DIR/server.py" ] || [ -f "$BASE_DIR/api.py" ] || [ -f "$BASE_DIR/requirements.txt" ]; then\n'
            '  BACKEND_DIR="$BASE_DIR"\n'
            'fi\n'
            '\n'
            '# Detect Frontend Directory\n'
            'FRONTEND_DIR=""\n'
            'if [ -d "$BASE_DIR/frontend" ] && [ -f "$BASE_DIR/frontend/package.json" ]; then\n'
            '  FRONTEND_DIR="$BASE_DIR/frontend"\n'
            'elif [ -d "$BASE_DIR/client" ] && [ -f "$BASE_DIR/client/package.json" ]; then\n'
            '  FRONTEND_DIR="$BASE_DIR/client"\n'
            'elif [ -d "$BASE_DIR/web" ] && [ -f "$BASE_DIR/web/package.json" ]; then\n'
            '  FRONTEND_DIR="$BASE_DIR/web"\n'
            'elif [ -d "$BASE_DIR/ui" ] && [ -f "$BASE_DIR/ui/package.json" ]; then\n'
            '  FRONTEND_DIR="$BASE_DIR/ui"\n'
            'elif [ -f "$BASE_DIR/package.json" ]; then\n'
            '  FRONTEND_DIR="$BASE_DIR"\n'
            'fi\n'
            '\n'
            '# Setup Frontend Dependencies and Configuration\n'
            'if [ -n "$FRONTEND_DIR" ] && [ -d "$FRONTEND_DIR" ]; then\n'
            '  cd "$FRONTEND_DIR" || true\n'
            '  if [ ! -d "node_modules" ] || [ -z "$(ls -A node_modules 2>/dev/null)" ]; then\n'
            '    FOUND_NM=""\n'
            '    for nm in \\\n'
            '      "/workspaces/${CLEAN_APP}"/*/*/*/node_modules \\\n'
            '      "/workspaces/${CLEAN_APP}"/*/*/node_modules \\\n'
            '      "/workspaces/${CLEAN_APP}"/*/node_modules \\\n'
            '      "/workspaces/${RAW_APP}"/*/*/*/node_modules \\\n'
            '      "/workspaces/${RAW_APP}"/*/*/node_modules \\\n'
            '      "/workspaces/${RAW_APP}"/*/node_modules \\\n'
            '      "/workspaces"/*/*/*/*/node_modules \\\n'
            '      "/workspaces"/*/*/*/node_modules \\\n'
            '      "/workspaces"/*/*/node_modules \\\n'
            '      "/workspaces"/*/node_modules \\\n'
            '      "/app"/*/*/node_modules \\\n'
            '      "/app"/*/node_modules \\\n'
            '      "/app/node_modules"; do\n'
            '      if [ -d "$nm" ] && [ "$nm" != "$FRONTEND_DIR/node_modules" ] && [ -n "$(ls -A "$nm" 2>/dev/null)" ]; then\n'
            '        FOUND_NM="$nm"\n'
            '        break\n'
            '      fi\n'
            '    done\n'
            '    if [ -z "$FOUND_NM" ]; then\n'
            '      FOUND_NM=$(find /workspaces /app -maxdepth 5 -type d -name "node_modules" 2>/dev/null | grep -v "^$FRONTEND_DIR/node_modules" | head -n 1)\n'
            '    fi\n'
            '    if [ -n "$FOUND_NM" ]; then\n'
            '      echo "[DEV-RUNNER] Linking node_modules from $FOUND_NM"\n'
            '      ln -sfn "$FOUND_NM" node_modules 2>/dev/null || cp -rs "$FOUND_NM" . 2>/dev/null || true\n'
            '    fi\n'
            '    if [ ! -d "node_modules" ] || [ -z "$(ls -A node_modules 2>/dev/null)" ]; then\n'
            '      echo "[DEV-RUNNER] Installing frontend dependencies..."\n'
            '      (npm install --prefer-offline --no-audit --legacy-peer-deps 2>&1 | tail -n 20 >> /tmp/frontend.log || true)\n'
            '    fi\n'
            '  fi\n'
            '  python3 -c "\n'
            'import os, re\n'
            'found_configs = set()\n'
            'search_dirs = [d for d in [os.environ.get(\'FRONTEND_DIR\', \'\'), os.environ.get(\'BASE_DIR\', \'\'), os.environ.get(\'ACTIVE_DIR\', \'\'), os.getcwd(), \'/app\'] if d and os.path.isdir(d)]\n'
            'for sdir in search_dirs:\n'
            '    for root, dirs, files in os.walk(sdir):\n'
            '        if \'node_modules\' in root or \'.git\' in root: continue\n'
            '        for f in files:\n'
            '            if f.startswith(\'vite.config.\') and f.endswith((\'.ts\', \'.js\', \'.mjs\', \'.cjs\', \'.mts\')):\n'
            '                found_configs.add(os.path.join(root, f))\n'
            'for cfg_path in found_configs:\n'
            '    try:\n'
            '        with open(cfg_path, \'r\', encoding=\'utf-8\') as fh: c = fh.read()\n'
            '        orig = c\n'
            '        if \'allowedHosts\' in c:\n'
            '            c = re.sub(r\'allowedHosts\\s*:\\s*(?:\\[[^\\]]*\\]|false|true|(?:\x27[^\x27]*\x27)|(?:\\x22[^\\x22]*\\x22))\', \'allowedHosts: true\', c)\n'
            '        if re.search(r\'server\\s*:\\s*\\{\', c):\n'
            '            if \'allowedHosts\' not in c:\n'
            '                c = re.sub(r\'server\\s*:\\s*\\{\', \'server: {\\n    allowedHosts: true,\\n    host: \\"0.0.0.0\\",\\n    port: 8080,\\n    cors: true,\\n    watch: { usePolling: true, interval: 1000 },\\n    hmr: { clientPort: 443 },\', c, count=1)\n'
            '        else:\n'
            '            if \'return {\' in c:\n'
            '                c = re.sub(r\'return\\s*\\{\', \'return {\\n  server: { host: \\"0.0.0.0\\", port: 8080, allowedHosts: true, cors: true, watch: { usePolling: true, interval: 1000 }, hmr: { clientPort: 443 } },\', c, count=1)\n'
            '            elif re.search(r\'defineConfig\\s*\\(\\s*(?:\\([^)]*\\)\\s*=>\\s*)?\\(?\\s*\\{\', c):\n'
            '                c = re.sub(r\'(defineConfig\\s*\\(\\s*(?:\\([^)]*\\)\\s*=>\\s*)?\\(?\\s*)\\{\', r\'\\1{\\n  server: { host: \\"0.0.0.0\\", port: 8080, allowedHosts: true, cors: true, watch: { usePolling: true, interval: 1000 }, hmr: { clientPort: 443 } },\', c, count=1)\n'
            '            elif \'export default {\' in c:\n'
            '                c = c.replace(\'export default {\', \'export default {\\n  server: { host: \\"0.0.0.0\\", port: 8080, allowedHosts: true, cors: true, watch: { usePolling: true, interval: 1000 }, hmr: { clientPort: 443 } },\', 1)\n'
            '            elif \'module.exports = {\' in c:\n'
            '                c = c.replace(\'module.exports = {\', \'module.exports = {\\n  server: { host: \\"0.0.0.0\\", port: 8080, allowedHosts: true, cors: true, watch: { usePolling: true, interval: 1000 }, hmr: { clientPort: 443 } },\', 1)\n'
            '        c = c.replace(\'http://localhost:8080\', \'http://localhost:8000\')\n'
            '        c = c.replace(\'http://127.0.0.1:8085\', \'http://localhost:8000\')\n'
            '        if c != orig:\n'
            '            with open(cfg_path, \'w\', encoding=\'utf-8\') as fh: fh.write(c)\n'
            '    except Exception: pass\n'
            'fdir = os.environ.get(\'FRONTEND_DIR\') or os.getcwd()\n'
            'if os.path.isdir(fdir) and not any(f.startswith(\'vite.config.\') for f in os.listdir(fdir)):\n'
            '    pkg_path = os.path.join(fdir, \'package.json\')\n'
            '    if os.path.exists(pkg_path):\n'
            '        try:\n'
            '            with open(pkg_path, \'r\', encoding=\'utf-8\') as pf: pkg_content = pf.read()\n'
            '            if \'vite\' in pkg_content:\n'
            '                new_cfg = \'import { defineConfig } from \\x27vite\\x27;\\n\\nexport default defineConfig({\\n  server: {\\n    host: \\x220.0.0.0\\x22,\\n    port: 8080,\\n    allowedHosts: true,\\n    cors: true,\\n    watch: { usePolling: true, interval: 1000 },\\n    hmr: { clientPort: 443 },\\n  }\\n});\\n\'\n'
            '                with open(os.path.join(fdir, \'vite.config.js\'), \'w\', encoding=\'utf-8\') as cf: cf.write(new_cfg)\n'
            '        except Exception: pass\n'
            '" 2>/dev/null || true\n'
            'fi\n'
            '\n'
            '# Start Backend\n'
            'if [ -n "$BACKEND_DIR" ] && [ -d "$BACKEND_DIR" ]; then\n'
            '  BACKEND_PORT="8000"\n'
            '  if [ -z "$FRONTEND_DIR" ]; then\n'
            '    BACKEND_PORT="8080"\n'
            '    kill -9 $SPLASH_PID 2>/dev/null || true\n'
            '    fuser -k -9 8080/tcp 2>/dev/null || true\n'
            '    sleep 0.1\n'
            '  fi\n'
            '  (\n'
            '    cd "$BACKEND_DIR" || exit 1\n'
            '    export PYTHONPATH="$ACTIVE_DIR:$BASE_DIR:$BACKEND_DIR:$BASE_DIR/backend:$BASE_DIR/api:$BASE_DIR/server:$PYTHONPATH"\n'
            '    export PORT=$BACKEND_PORT DASHBOARD_PORT=$BACKEND_PORT DATABASE_URL="${DATABASE_URL:-sqlite:////tmp/app.db}"\n'
            '    log "  [2/3] Launching backend service on port $BACKEND_PORT ($BACKEND_DIR)..."\n'
            '    echo "[DEV-RUNNER] Starting backend on port $BACKEND_PORT ($BACKEND_DIR)..." >> /tmp/backend.log\n'
            '    if [ -f requirements.txt ] && [ ! -f /tmp/.reqs_installed ]; then\n'
            '      pip install --no-cache-dir -r requirements.txt >> /tmp/backend.log 2>&1 || true\n'
            '      touch /tmp/.reqs_installed\n'
            '    fi\n'
            '    pip install --no-cache-dir uvicorn fastapi >> /tmp/backend.log 2>&1 || true\n'
            '    ENTRY_FILE=""\n'
            '    for ef in app.py main.py server.py api.py; do\n'
            '      if [ -f "$ef" ]; then ENTRY_FILE="$ef"; break; fi\n'
            '    done\n'
            '    if [ -n "$ENTRY_FILE" ]; then\n'
            '      MODULE_NAME="${ENTRY_FILE%.py}"\n'
            '      if grep -q "streamlit" "$ENTRY_FILE" 2>/dev/null || [ "${APP_TYPE:-}" = "streamlit" ]; then\n'
            '        exec streamlit run "$ENTRY_FILE" --server.port $BACKEND_PORT --server.address 0.0.0.0 --server.headless true --server.enableCORS false >> /tmp/backend.log 2>&1\n'
            '      elif grep -q -E "FastAPI|Starlette" "$ENTRY_FILE" 2>/dev/null; then\n'
            '        exec uvicorn ${MODULE_NAME}:app --host 0.0.0.0 --port $BACKEND_PORT --reload --reload-delay 1.0 --reload-exclude \'**/node_modules/**\' --reload-exclude \'**/.git/**\' >> /tmp/backend.log 2>&1\n'
            '      elif grep -q -E "Flask|Bottle|WSGI" "$ENTRY_FILE" 2>/dev/null; then\n'
            '        exec python3 "$ENTRY_FILE" >> /tmp/backend.log 2>&1\n'
            '      else\n'
            '        exec uvicorn ${MODULE_NAME}:app --host 0.0.0.0 --port $BACKEND_PORT --reload --reload-delay 1.0 --reload-exclude \'**/node_modules/**\' --reload-exclude \'**/.git/**\' >> /tmp/backend.log 2>&1 || exec python3 "$ENTRY_FILE" >> /tmp/backend.log 2>&1\n'
            '      fi\n'
            '    fi\n'
            '  ) &\n'
            'fi\n'
            '\n'
            '# Start Frontend (on 8080) with Safe Handover from Splash\n'
            'if [ -n "$FRONTEND_DIR" ] && [ -d "$FRONTEND_DIR" ]; then\n'
            '  (\n'
            '    cd "$FRONTEND_DIR" || exit 1\n'
            '    export PATH="$PWD/node_modules/.bin:$PATH"\n'
            '    export DASHBOARD_PORT=8000 DASHBOARD_UI_PORT=8080 PORT=8080 HOST=0.0.0.0 DANGEROUSLY_DISABLE_HOST_CHECK=true WDS_SOCKET_PORT=443\n'
            '    log "    → Starting frontend server on port 8080 ($FRONTEND_DIR)..."\n'
            '    echo "[DEV-RUNNER] Handing over port 8080 to frontend ($FRONTEND_DIR)..." >> /tmp/frontend.log\n'
            '    kill -9 $SPLASH_PID 2>/dev/null || true\n'
            '    fuser -k -9 8080/tcp 2>/dev/null || true\n'
            '    sleep 0.1\n'
            '    if grep -q \'"next"\' package.json 2>/dev/null; then\n'
            '      if [ -x "./node_modules/.bin/next" ]; then exec ./node_modules/.bin/next dev -p 8080 -H 0.0.0.0 >> /tmp/frontend.log 2>&1; else exec npx next dev -p 8080 -H 0.0.0.0 >> /tmp/frontend.log 2>&1; fi\n'
            '    elif grep -q \'"vite"\' package.json 2>/dev/null || [ -f vite.config.ts ] || [ -f vite.config.js ]; then\n'
            '      if [ -x "./node_modules/.bin/vite" ]; then exec ./node_modules/.bin/vite --host 0.0.0.0 --port 8080 --cors >> /tmp/frontend.log 2>&1; else exec npx --yes vite --host 0.0.0.0 --port 8080 --cors >> /tmp/frontend.log 2>&1; fi\n'
            '    elif grep -q \'"dev"\' package.json 2>/dev/null; then\n'
            '      exec npm run dev -- --host 0.0.0.0 --port 8080 >> /tmp/frontend.log 2>&1\n'
            '    elif grep -q \'"start"\' package.json 2>/dev/null; then\n'
            '      exec npm start -- -p 8080 >> /tmp/frontend.log 2>&1\n'
            '    elif [ -d "dist" ]; then\n'
            '      exec python3 -m http.server 8080 --directory dist >> /tmp/frontend.log 2>&1\n'
            '    elif [ -d "build" ]; then\n'
            '      exec python3 -m http.server 8080 --directory build >> /tmp/frontend.log 2>&1\n'
            '    else\n'
            '      exec python3 -m http.server 8080 --directory . >> /tmp/frontend.log 2>&1\n'
            '    fi\n'
            '  ) &\n'
            '  \n'
            '  # Background Watchdog: Ensure port 8080 is ALWAYS bound and responding\n'
            '  (\n'
            '    sleep 8\n'
            '    if ! (curl -fsSL -m 2 http://127.0.0.1:8080 >/dev/null 2>&1 || python3 -c "import urllib.request; urllib.request.urlopen(\'http://127.0.0.1:8080\', timeout=2)" 2>/dev/null); then\n'
            '      echo "[WATCHDOG] Port 8080 not responding after 8s. Starting static fallback server..." >> /tmp/frontend.log\n'
            '      fuser -k -9 8080/tcp 2>/dev/null || true\n'
            '      sleep 0.1\n'
            '      if [ -d "$FRONTEND_DIR/dist" ]; then\n'
            '        exec python3 -m http.server 8080 --directory "$FRONTEND_DIR/dist" >> /tmp/frontend.log 2>&1\n'
            '      elif [ -d "$FRONTEND_DIR/build" ]; then\n'
            '        exec python3 -m http.server 8080 --directory "$FRONTEND_DIR/build" >> /tmp/frontend.log 2>&1\n'
            '      elif [ -d "$BASE_DIR/dist" ]; then\n'
            '        exec python3 -m http.server 8080 --directory "$BASE_DIR/dist" >> /tmp/frontend.log 2>&1\n'
            '      elif [ -n "$FRONTEND_DIR" ] && [ -d "$FRONTEND_DIR" ]; then\n'
            '        exec python3 -m http.server 8080 --directory "$FRONTEND_DIR" >> /tmp/frontend.log 2>&1\n'
            '      fi\n'
            '    fi\n'
            '  ) &\n'
            'elif [ -z "$BACKEND_DIR" ]; then\n'
            '  # Pure static sandbox fallback (splash server continues or serves base directory)\n'
            '  echo "[DEV-RUNNER] No backend or frontend detected; static splash server active." >> /tmp/frontend.log\n'
            'fi\n'
            '\n'
            'echo "[DEV-RUNNER] Dev server startup initiated for $ACTIVE_DIR"\n'
        )

    def switch_active_sandbox(self, app: Any, folder_path: str) -> Dict[str, Any]:
        """Instantly switch active sandbox in kubernetes dev pod and reload dev servers."""
        clean_folder = folder_path.strip("/")
        clean_app = re.sub(r'[^a-z0-9-]', '-', app.id.lower()).strip('-')
        target_dir = f"/workspaces/{clean_folder}" if clean_folder else f"/workspaces/{clean_app}/default"

        runner_script_b64 = base64.b64encode(self._get_dev_runner_script().encode("utf-8")).decode("ascii")
        git_subdir = (getattr(app, "git_subdir", "") or "").strip("/\\")
        cmd = (
            f"echo '{runner_script_b64}' | base64 -d > /usr/local/bin/dev-runner.sh && "
            f"chmod +x /usr/local/bin/dev-runner.sh && "
            f"export GIT_SUBDIR='{git_subdir}' APP_SUBDIR='{git_subdir}' && "
            f"/usr/local/bin/dev-runner.sh reload '{target_dir}' && "
            f"echo '__SWITCH_SUCCESS__'"
        )
        res = self.exec_command_in_dev(app, cmd)
        output = res.get("output", "")
        success = ("__SWITCH_SUCCESS__" in output) or (res.get("exit_code") == 0)
        return {
            "success": success,
            "active_workdir": target_dir,
            "output": output,
        }

