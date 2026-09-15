"""Kubernetes runtime drivers for Production Apps and Dev Sandboxes with Subdomain Ingress (SOLID / SRP)."""
import os
import re
import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Callable

from app.config import settings
from app.services.drivers.base import BaseAppDriver, BaseDevDriver
from app.services.ingress_service import ingress_service

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

        # 1. Environment variables
        cfg = dict(app.config or {})
        env_vars = [
            client.V1EnvVar(name="PORT", value="8080"),
            client.V1EnvVar(name="APP_NAME", value=str(app.name)),
            client.V1EnvVar(name="APP_SLUG", value=str(app.slug)),
            client.V1EnvVar(name="APP_ID", value=str(app.id)),
            client.V1EnvVar(name="WORKSPACE_ID", value=str(app.workspace_id)),
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
                f"  echo '[BUILD] [2/3] Building dependencies and compiling assets...' && "
                # 1. Build Frontend if present (supports monorepo frontend, web, client, or root)
                f"  if [ -d /app_src/frontend ] && [ -f /app_src/frontend/package.json ]; then "
                f"    echo '[BUILD] Detected frontend directory. Installing dependencies & building...' && "
                f"    (cd /app_src/frontend && (npm install --legacy-peer-deps --prefer-offline --no-audit || npm install --legacy-peer-deps || npm install --force) && npm run build) || "
                f"    (echo '[ERROR] Frontend build failed in /app_src/frontend' && return 1); "
                f"  elif [ -d /app_src/client ] && [ -f /app_src/client/package.json ]; then "
                f"    echo '[BUILD] Detected client directory. Installing dependencies & building...' && "
                f"    (cd /app_src/client && (npm install --legacy-peer-deps --prefer-offline --no-audit || npm install --legacy-peer-deps || npm install --force) && npm run build) || "
                f"    (echo '[ERROR] Client build failed in /app_src/client' && return 1); "
                f"  elif [ -d /app_src/web ] && [ -f /app_src/web/package.json ]; then "
                f"    echo '[BUILD] Detected web directory. Installing dependencies & building...' && "
                f"    (cd /app_src/web && (npm install --legacy-peer-deps --prefer-offline --no-audit || npm install --legacy-peer-deps || npm install --force) && npm run build) || "
                f"    (echo '[ERROR] Web build failed in /app_src/web' && return 1); "
                f"  elif [ -f /app_src/package.json ]; then "
                f"    echo '[BUILD] Detected root package.json. Installing dependencies & building...' && "
                f"    (cd /app_src && (npm install --legacy-peer-deps --prefer-offline --no-audit || npm install --legacy-peer-deps || npm install --force) && (npm run build --if-present || true)) || "
                f"    (echo '[ERROR] Root frontend build failed' && return 1); "
                f"  fi && "
                # 2. Start Application: Python Backend vs Pure Python / Streamlit vs Node Frontend
                f"  if [ -d /app_src/backend ] && ( [ -f /app_src/backend/main.py ] || [ -f /app_src/backend/app.py ] || [ -f /app_src/backend/requirements.txt ] ); then "
                f"    cd /app_src && "
                f"    (if [ -f backend/requirements.txt ]; then echo '[BUILD] Installing Python dependencies from backend/requirements.txt...' && (pip install --no-cache-dir -r backend/requirements.txt || (echo '[ERROR] pip install failed for backend/requirements.txt' && return 1)); fi) && "
                f"    (pip install --no-cache-dir uvicorn fastapi || true) && "
                f"    echo '[BUILD] [3/3] Build phase completed successfully.' && "
                f"    echo '[BUILD] ========================================================' && "
                f"    echo '[RUNTIME] Launching application server on port 8080...' && "
                f"    export PYTHONPATH=\"/app_src:/app_src/backend:$PYTHONPATH\" && "
                f"    if [ -f backend/main.py ]; then (cd backend && uvicorn main:app --host 0.0.0.0 --port 8080) || uvicorn backend.main:app --host 0.0.0.0 --port 8080; "
                f"    elif [ -f backend/app.py ]; then (cd backend && uvicorn app:app --host 0.0.0.0 --port 8080) || uvicorn backend.app:app --host 0.0.0.0 --port 8080; "
                f"    fi; "
                f"  elif [ -f /app_src/main.py ] || [ -f /app_src/app.py ] || [ -f /app_src/requirements.txt ] || [ '{app_type}' = 'streamlit' ]; then "
                f"    cd /app_src && "
                f"    (if [ -f requirements.txt ]; then echo '[BUILD] Installing Python dependencies from requirements.txt...' && (pip install --no-cache-dir -r requirements.txt || (echo '[ERROR] pip install failed for requirements.txt' && return 1)); fi) && "
                f"    (pip install --no-cache-dir uvicorn fastapi streamlit || true) && "
                f"    echo '[BUILD] [3/3] Build phase completed successfully.' && "
                f"    echo '[BUILD] ========================================================' && "
                f"    echo '[RUNTIME] Launching application server on port 8080...' && "
                f"    if grep -q 'streamlit' app.py 2>/dev/null || [ '{app_type}' = 'streamlit' ]; then "
                f"      streamlit run app.py --server.port=8080 --server.address=0.0.0.0 --server.headless=true; "
                f"    elif [ -f main.py ]; then uvicorn main:app --host 0.0.0.0 --port 8080; "
                f"    elif [ -f app.py ]; then uvicorn app:app --host 0.0.0.0 --port 8080; "
                f"    fi; "
                f"  elif [ -f /app_src/package.json ]; then "
                f"    echo '[BUILD] [3/3] Build phase completed successfully.' && "
                f"    echo '[BUILD] ========================================================' && "
                f"    echo '[RUNTIME] Launching application server on port 8080...' && "
                f"    cd /app_src && (npm start -- -p 8080 || ( [ -d frontend/dist ] && npx --yes serve -l 8080 frontend/dist ) || ( [ -d dist ] && npx --yes serve -l 8080 dist ) || ( [ -d build ] && npx --yes serve -l 8080 build ) || ( [ -d out ] && npx --yes serve -l 8080 out ) || npx --yes serve -l 8080 .); "
                f"  elif [ -d /app_src/frontend/dist ]; then "
                f"    echo '[BUILD] [3/3] Build phase completed successfully.' && "
                f"    echo '[BUILD] ========================================================' && "
                f"    echo '[RUNTIME] Launching application server on port 8080...' && "
                f"    npx --yes serve -l 8080 /app_src/frontend/dist; "
                f"  elif [ -f /app_src/index.html ]; then "
                f"    echo '[BUILD] [3/3] Build phase completed successfully.' && "
                f"    echo '[BUILD] ========================================================' && "
                f"    echo '[RUNTIME] Launching application server on port 8080...' && "
                f"    npx --yes serve -l 8080 /app_src; "
                f"  else "
                f"    echo '[BUILD] [3/3] Build phase completed successfully.' && "
                f"    echo '[BUILD] ========================================================' && "
                f"    echo '[RUNTIME] Launching application server on port 8080...' && "
                f"    echo '<!DOCTYPE html><html><body><h1>{app.name}</h1><p>Running on CompassX</p></body></html>' > /app_src/index.html && npx --yes serve -l 8080 /app_src; "
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
                    spec=client.V1PodSpec(containers=[container]),
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
            k8s.apps().delete_namespaced_deployment(name=name, namespace=ns)
            return True
        except Exception as e:
            logger.warning("Could not delete K8s deployment %s: %s", name, e)
            return False

    def get_status(self, app) -> Dict[str, Any]:
        k8s = self._get_k8s_client()
        clean_id = re.sub(r"[^a-z0-9-]", "-", app.id.lower()).strip("-")
        name = f"compassx-app-{clean_id}"
        ns = settings.K8S_NAMESPACE
        if not k8s:
            return {"status": "unknown", "deployment_name": name}
        try:
            dep = k8s.apps().read_namespaced_deployment(name=name, namespace=ns)
            available = (dep.status and (dep.status.available_replicas or dep.status.ready_replicas or 0) > 0)
            return {"status": "running" if available else "starting", "deployment_name": name}
        except Exception:
            try:
                pods = k8s.core().list_namespaced_pod(namespace=ns, label_selector=f"compassx/app-id={clean_id},compassx/role=prod")
                if pods.items and any(p.status and p.status.phase == "Running" for p in pods.items):
                    return {"status": "running", "deployment_name": name}
            except Exception:
                pass
            return {"status": "stopped", "deployment_name": name}

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
            pod_name = pods.items[0].metadata.name
            raw = k8s.core().read_namespaced_pod_log(name=pod_name, namespace=ns, tail_lines=max_lines)
            return [line for line in raw.splitlines() if line.strip()]
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
                    elif "[ERROR]" in line:
                        build_started = True
                        current_build_lines.append(line)
                        build_finished = True
                    elif "[RUNTIME]" in line:
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

    def start_dev(self, app, repo_dir: str, omnigent_internal_url: str, workspace_folder: str = "", workspace_branch: str = "") -> Dict[str, Any]:
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
                        f"if [ ! -d .git ]; then "
                        f"(git clone --branch '{git_ref}' '{auth_url}' . || git clone '{auth_url}' . || true) && "
                        f"(git checkout -B '{target_branch}' || true); "
                        f"else "
                        f"(git checkout -B '{target_branch}' 2>/dev/null || true); "
                        f"fi; "
                    )

                # Resolve workspace workdir on shared PVC
                if workspace_folder:
                    workdir = f"/workspaces/{workspace_folder}"
                else:
                    import re as _re
                    workdir = f"/workspaces/{_re.sub(r'[^a-z0-9-]', '-', app.id.lower()).strip('-')}/default"

                app_type = getattr(app, "app_type", "custom_web") or "custom_web"

                dev_cmd = (
                    f"mkdir -p /workspaces/.shared_auth/.gemini && "
                    f"cp -rn /root/.gemini/* /workspaces/.shared_auth/.gemini/ 2>/dev/null; "
                    f"rm -rf /root/.gemini && ln -sf /workspaces/.shared_auth/.gemini /root/.gemini; "
                    f"(which agy >/dev/null 2>&1 && ln -sf /usr/local/bin/agy /usr/local/bin/antigravity || true); "
                    f"mkdir -p /root/.omnigent /root/.config/omnigent /root/.config/opencode /root/.opencode && "
                    f"printf 'host:\\n  host_id: {host_id}\\n  name: \"{host_name}\"\\n' | tee /root/.omnigent/config.yaml /root/.config/omnigent/config.yaml /root/.config/opencode/config.yaml /root/.opencode/config.yaml >/dev/null; "
                    f"export OMNIGENT_HOST_ID={host_id} OMNIGENT_HOST_NAME=\"{host_name}\" HOST_ID={host_id} HOST_NAME=\"{host_name}\" OPENCODE_HOST_ID={host_id} OPENCODE_HOST_NAME=\"{host_name}\" "
                    f"CHOKIDAR_USEPOLLING=1 CHOKIDAR_INTERVAL=2000 WATCHPACK_POLLING=true WATCHPACK_POLLING_INTERVAL=2000 WATCHFILES_FORCE_POLLING=true WATCHFILES_POLL_DELAY_MS=2000 "
                    f"NODE_TLS_REJECT_UNAUTHORIZED=0 NPM_CONFIG_STRICT_SSL=false PYTHONHTTPSVERIFY=0 GIT_SSL_NO_VERIFY=true CURL_INSECURE=1; "
                    f"(which opencode >/dev/null 2>&1 || npm install -g opencode-ai@1.18.0 || true); "
                    f"mkdir -p {workdir} && cd {workdir} && "
                    f"{clone_snippet}"
                    # 1. Detect and start Python FastAPI Backend in background (live reload on port 8000)
                    f"BACKEND_DIR=\"\"; "
                    f"if [ -d {workdir}/backend ] && ( [ -f {workdir}/backend/app.py ] || [ -f {workdir}/backend/main.py ] || [ -f {workdir}/backend/requirements.txt ] ); then BACKEND_DIR=\"{workdir}/backend\"; "
                    f"elif [ -d {workdir}/api ] && ( [ -f {workdir}/api/app.py ] || [ -f {workdir}/api/main.py ] ); then BACKEND_DIR=\"{workdir}/api\"; "
                    f"elif [ -d {workdir}/server ] && ( [ -f {workdir}/server/app.py ] || [ -f {workdir}/server/main.py ] ); then BACKEND_DIR=\"{workdir}/server\"; "
                    f"elif [ -f {workdir}/app.py ] || [ -f {workdir}/main.py ]; then BACKEND_DIR=\"{workdir}\"; "
                    f"fi; "
                    f"if [ -n \"$BACKEND_DIR\" ]; then "
                    f"  (cd \"$BACKEND_DIR\" && "
                    f"   export PYTHONPATH=\"{workdir}:{workdir}/backend:{workdir}/api:{workdir}/server:$PYTHONPATH\" && "
                    f"   export DATABASE_URL=\"${{DATABASE_URL:-sqlite:////tmp/app.db}}\" && "
                    f"   (if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; fi) && "
                    f"   (pip install --no-cache-dir uvicorn fastapi || true) && "
                    f"   if [ -f app.py ]; then "
                    f"     (uvicorn app:app --host 0.0.0.0 --port 8000 --reload --reload-delay 2.0 --reload-exclude '**/node_modules/**' --reload-exclude '**/.git/**' || python app.py) & "
                    f"   elif [ -f main.py ]; then "
                    f"     (uvicorn main:app --host 0.0.0.0 --port 8000 --reload --reload-delay 2.0 --reload-exclude '**/node_modules/**' --reload-exclude '**/.git/**' || python main.py) & "
                    f"   fi) & "
                    f"fi; "
                    # 2. Detect and start React / Vite Frontend in background (npm run dev on port 8080)
                    f"FRONTEND_DIR=\"\"; "
                    f"if [ -d {workdir}/frontend ] && [ -f {workdir}/frontend/package.json ]; then FRONTEND_DIR=\"{workdir}/frontend\"; "
                    f"elif [ -d {workdir}/client ] && [ -f {workdir}/client/package.json ]; then FRONTEND_DIR=\"{workdir}/client\"; "
                    f"elif [ -d {workdir}/web ] && [ -f {workdir}/web/package.json ]; then FRONTEND_DIR=\"{workdir}/web\"; "
                    f"elif [ -f {workdir}/package.json ]; then FRONTEND_DIR=\"{workdir}\"; "
                    f"fi; "
                    f"if [ -n \"$FRONTEND_DIR\" ]; then "
                    f"  (cd \"$FRONTEND_DIR\" && "
                    f"   (python3 -c \"import os, re\\nfor f in ['vite.config.ts', 'vite.config.js']:\\n if os.path.exists(f):\\n  c = open(f, 'r').read()\\n  if 'usePolling' not in c: c = re.sub(r'(server:\\\\s*\\\\{{)', r'\\\\\\\\1\\\\\\\\n    allowedHosts: true,\\\\\\\\n    watch: {{ usePolling: true, interval: 2000, ignored: [\\\\\\\"**/node_modules/**\\\\\\\", \\\\\\\"**/.git/**\\\\\\\", \\\\\\\"**/dist/**\\\\\\\", \\\\\\\"**/.cache/**\\\\\\\"] }},\\\\\\\\n    hmr: {{ clientPort: 443 }},', c)\\n  else: c = re.sub(r'watch:\\\\s*\\\\{{[^}}]*\\\\}}', 'watch: {{ usePolling: true, interval: 2000, ignored: [\\\\\\\"**/node_modules/**\\\\\\\", \\\\\\\"**/.git/**\\\\\\\", \\\\\\\"**/dist/**\\\\\\\", \\\\\\\"**/.cache/**\\\\\\\"] }}', c)\\n  c = c.replace('http://localhost:8080', 'http://localhost:8000')\\n  c = c.replace('http://127.0.0.1:8085', 'http://localhost:8000')\\n  open(f, 'w').write(c)\" 2>/dev/null || true) && "
                    f"   (if [ ! -d node_modules ]; then npm install --legacy-peer-deps --prefer-offline --no-audit || npm install --legacy-peer-deps || true; fi) && "
                    f"   (npx --yes vite --host 0.0.0.0 --port 8080 --cors || npm run dev -- --host 0.0.0.0 --port 8080 || npm start -- -p 8080 || npx --yes serve -l 8080 .)) & "
                    f"elif [ -n \"$BACKEND_DIR\" ]; then "
                    # Pure Python app (Streamlit or FastAPI on port 8080)
                    f"  (cd \"$BACKEND_DIR\" && "
                    f"   export PYTHONPATH=\"{workdir}:{workdir}/backend:{workdir}/api:{workdir}/server:$PYTHONPATH\" && "
                    f"   export DATABASE_URL=\"${{DATABASE_URL:-sqlite:////tmp/app.db}}\" && "
                    f"   if grep -q 'streamlit' app.py 2>/dev/null || [ '{app_type}' = 'streamlit' ]; then "
                    f"     pip install --no-cache-dir streamlit && exec streamlit run app.py --server.port=8080 --server.address=0.0.0.0 --server.headless=true; "
                    f"   elif [ -f app.py ]; then "
                    f"     exec uvicorn app:app --host 0.0.0.0 --port 8080 --reload --reload-delay 2.0 --reload-exclude '**/node_modules/**' --reload-exclude '**/.git/**'; "
                    f"   elif [ -f main.py ]; then "
                    f"     exec uvicorn main:app --host 0.0.0.0 --port 8080 --reload --reload-delay 2.0 --reload-exclude '**/node_modules/**' --reload-exclude '**/.git/**'; "
                    f"   fi) & "
                    f"else "
                    # Fallback default web page
                    f"  if [ ! -f {workdir}/index.html ]; then echo '<!DOCTYPE html><html><head><title>Dev Sandbox for {app.name}</title></head><body style=\"font-family:sans-serif;padding:2rem;\"><h1>Dev Sandbox for {app.name}</h1><p style=\"color:green;font-weight:bold;\">Connected to Omnigent Dev Studio</p></body></html>' > {workdir}/index.html; fi; "
                    f"  (python3 -m http.server 8080 --directory {workdir} || npx --yes serve -l 8080 {workdir}) & "
                    f"fi; "
                    # 3. Start Omnigent Host Runner in foreground
                    f"exec omnigent host --server {omnigent_internal_url} --non-interactive"
                )
                # 1b. Dev Deployment Spec (resilient self-healing; /workspaces backed by shared PVC)
                dev_container = client.V1Container(
                    name="dev-host",
                    image="ghcr.io/omnigent-ai/omnigent-host:latest",
                    image_pull_policy="IfNotPresent",
                    command=["/bin/sh", "-c"],
                    args=[dev_cmd],
                    ports=[client.V1ContainerPort(container_port=8080, name="http")],
                    env=[
                        client.V1EnvVar(name="PORT", value="8080"),
                        client.V1EnvVar(name="APP_NAME", value=str(app.name)),
                        client.V1EnvVar(name="APP_SLUG", value=str(app.slug)),
                        client.V1EnvVar(name="APP_ID", value=str(app.id)),
                        client.V1EnvVar(name="OMNIGENT_HOST_ID", value=str(host_id)),
                        client.V1EnvVar(name="OMNIGENT_HOST_NAME", value=str(host_name)),
                        client.V1EnvVar(name="OMNIGENT_SERVER_URL", value=str(omnigent_internal_url)),
                        client.V1EnvVar(name="DEV_WORKSPACE_DIR", value=workdir),
                    ],
                    resources=client.V1ResourceRequirements(
                        requests={"cpu": "200m", "memory": "1024Mi"},
                        limits={"cpu": "4", "memory": "5000Mi"},
                    ),
                    volume_mounts=[
                        client.V1VolumeMount(
                            name="dev-workspaces",
                            mount_path="/workspaces",
                        )
                    ],
                )

                dev_affinity = client.V1Affinity(
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
                    )
                )

                dev_deployment = client.V1Deployment(
                    api_version="apps/v1",
                    kind="Deployment",
                    metadata=client.V1ObjectMeta(name=dev_name, namespace=ns, labels=labels),
                    spec=client.V1DeploymentSpec(
                        replicas=1,
                        selector=client.V1LabelSelector(match_labels={"compassx/app-id": clean_id, "compassx/dev": "true"}),
                        template=client.V1PodTemplateSpec(
                            metadata=client.V1ObjectMeta(labels=labels),
                            spec=client.V1PodSpec(
                                containers=[dev_container],
                                affinity=dev_affinity,
                                restart_policy="Always",
                                volumes=[
                                    client.V1Volume(
                                        name="dev-workspaces",
                                        persistent_volume_claim=client.V1PersistentVolumeClaimVolumeSource(
                                            claim_name="compassx-dev-workspaces",
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

        return {
            "mode": "kubernetes",
            "pod_name": dev_name,
            "container_name": dev_name,
            "dev_url": dev_url,
            "host_id": host_id,
            "host_name": host_name,
            "namespace": ns,
            "status": "active",
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

    def get_dev_status(self, app) -> Dict[str, Any]:
        clean_id = re.sub(r"[^a-z0-9-]", "-", app.id.lower()).strip("-")
        dev_name = f"compassx-app-dev-{clean_id}"
        ns = settings.K8S_NAMESPACE
        k8s = self._get_k8s_client()
        if not k8s:
            return {"status": "inactive", "pod_name": dev_name, "mode": "kubernetes"}

        # 1. Check if dev deployment exists
        try:
            dep = k8s.apps().read_namespaced_deployment(name=dev_name, namespace=ns)
            if dep.metadata and dep.metadata.deletion_timestamp:
                return {"status": "stopping", "pod_name": dev_name, "mode": "kubernetes", "phase": "Terminating"}
            ready = (dep.status and (dep.status.available_replicas or dep.status.ready_replicas or 0) > 0)
            if ready:
                return {"status": "active", "pod_name": dev_name, "mode": "kubernetes", "phase": "Running"}
            else:
                return {"status": "provisioning", "pod_name": dev_name, "mode": "kubernetes", "phase": "Pending"}
        except Exception:
            pass

        # 2. Check standalone pod fallback
        try:
            pod = k8s.core().read_namespaced_pod(name=dev_name, namespace=ns)
            is_terminating = bool(pod.metadata and pod.metadata.deletion_timestamp)
            raw_phase = pod.status.phase if pod.status else "Unknown"
            reason = pod.status.reason if pod.status else None

            if reason == "Evicted" or raw_phase in ["Failed", "Unknown"]:
                try:
                    k8s.core().delete_namespaced_pod(name=dev_name, namespace=ns, grace_period_seconds=0)
                except Exception:
                    pass
                return {"status": "stopped", "pod_name": dev_name, "mode": "kubernetes", "phase": "Evicted"}

            phase = "Terminating" if is_terminating else raw_phase
            is_running = (phase == "Running") and not is_terminating
            is_pending = phase == "Pending"
            return {
                "status": "stopping" if is_terminating else ("active" if is_running else "provisioning" if is_pending else "stopped"),
                "pod_name": dev_name,
                "mode": "kubernetes",
                "phase": phase,
                "pod_ip": pod.status.pod_ip if pod.status else None,
            }
        except Exception:
            pass

        return {"status": "inactive", "pod_name": dev_name, "mode": "kubernetes"}

    def get_dev_url(self, app) -> str:
        return ingress_service.get_app_dev_url(app)

    def get_dev_logs(self, app, max_lines: int = 200) -> str:
        k8s = self._get_k8s_client()
        if not k8s:
            return ""
        ns = settings.K8S_NAMESPACE
        clean_id = re.sub(r"[^a-z0-9-]", "-", app.id.lower()).strip("-")
        try:
            pods = k8s.core().list_namespaced_pod(
                namespace=ns,
                label_selector=f"compassx/app-id={clean_id},compassx/dev=true",
            )
            if pods.items:
                pod_name = pods.items[0].metadata.name
                return k8s.core().read_namespaced_pod_log(name=pod_name, namespace=ns, tail_lines=max_lines)
            name = f"compassx-app-dev-{clean_id}"
            return k8s.core().read_namespaced_pod_log(name=name, namespace=ns, tail_lines=max_lines)
        except Exception:
            return ""

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
        dev_name = f"compassx-app-dev-{clean_id}"
        ns = settings.K8S_NAMESPACE

        try:
            pods = k8s.core().list_namespaced_pod(
                namespace=ns,
                label_selector=f"compassx/app-id={clean_id},compassx/dev=true",
            )
            pod_name = None
            for p in (pods.items or []):
                if p.status and p.status.phase == "Running" and not p.metadata.deletion_timestamp:
                    pod_name = p.metadata.name
                    break
            if not pod_name:
                pod_name = dev_name

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


    def _find_running_pod_name(self, clean_id: str, ns: str) -> Optional[str]:
        k8s = self._get_k8s_client()
        if not k8s:
            return None
        dev_name = f"compassx-app-dev-{clean_id}"
        try:
            pods = k8s.core().list_namespaced_pod(
                namespace=ns,
                label_selector=f"compassx/app-id={clean_id},compassx/dev=true",
            )
            for p in (pods.items or []):
                if p.status and p.status.phase == "Running" and not p.metadata.deletion_timestamp:
                    return p.metadata.name
        except Exception:
            pass
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
                command=["/bin/sh", "-c", f"cd {workdir} 2>/dev/null && git rev-parse --abbrev-ref HEAD 2>/dev/null || echo ''"],
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
        pod_name = self._find_running_pod_name(clean_id, ns) or f"compassx-app-dev-{clean_id}"

        workdir = f"/workspaces/{workspace_folder}" if workspace_folder else f"/workspaces/{clean_id}/default"
        full_cmd = f"cd {workdir} && {command}"

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
                _request_timeout=60,
            )
            return {
                "success": True,
                "exit_code": 0,
                "output": resp or "",
                "workdir": workdir,
            }
        except Exception as exc:
            logger.warning("Failed executing command in dev pod: %s", exc)
            return {"success": False, "exit_code": 1, "output": str(exc), "workdir": workdir}

    def open_terminal_ws_client(
        self,
        app,
        workspace_folder: str = "",
        cols: int = 80,
        rows: int = 24,
    ) -> Any:
        """Open a live bidirectional interactive PTY stream to the dev pod."""
        from kubernetes import stream
        import json
        k8s = self._get_k8s_client()
        if not k8s:
            return None

        clean_id = re.sub(r"[^a-z0-9-]", "-", app.id.lower()).strip("-")
        ns = settings.K8S_NAMESPACE
        pod_name = self._find_running_pod_name(clean_id, ns) or f"compassx-app-dev-{clean_id}"
        workdir = f"/workspaces/{workspace_folder}" if workspace_folder else f"/workspaces/{clean_id}/default"

        shell_cmd = ["/bin/sh", "-c", f"cd {workdir} 2>/dev/null; if [ -x /bin/bash ]; then exec /bin/bash -l; else exec /bin/sh -l; fi"]

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

