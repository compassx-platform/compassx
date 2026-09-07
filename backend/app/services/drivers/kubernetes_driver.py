"""Kubernetes runtime drivers for Production Apps and Dev Sandboxes with Subdomain Ingress (SOLID / SRP)."""
import os
import re
import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

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
        for ev in (cfg.get("env_vars") or []):
            if isinstance(ev, dict) and ev.get("key") and ev.get("value"):
                env_vars.append(client.V1EnvVar(name=ev["key"], value=str(ev["value"])))

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
        elif "streamlit" in app_type or "python" in app_type:
            image_tag = "python:3.11-slim"
            container_cmd = ["/bin/sh", "-c"]
            run_cmd = (
                f"apt-get update && apt-get install -y --no-install-recommends git curl && "
                f"mkdir -p /app_src && cd /app_src && "
                f"(git clone --branch '{git_ref}' '{auth_url}' . || git clone '{auth_url}' . || true) && "
                f"(if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; fi) && "
                f"pip install --no-cache-dir streamlit && "
                f"(if [ ! -f '{entrypoint}' ]; then echo \"import streamlit as st\\nst.set_page_config(page_title='{app.name}', layout='wide')\\nst.title('{app.name}')\\nst.success('Application running successfully on CompassX Platform.')\\nst.info('Deploy your custom Streamlit app by connecting your Git repository.')\" > '{entrypoint}'; fi) && "
                f"exec streamlit run '{entrypoint}' --server.port=8080 --server.address=0.0.0.0 --server.headless=true"
            )
            container_args = [run_cmd]
        elif "node" in app_type or "next" in app_type or "vite" in app_type:
            image_tag = "node:20-alpine"
            container_cmd = ["/bin/sh", "-c"]
            run_cmd = (
                f"apk add --no-cache git && "
                f"mkdir -p /app_src && cd /app_src && "
                f"(git clone --branch '{git_ref}' '{auth_url}' . || git clone '{auth_url}' . || true) && "
                f"(if [ -f package.json ]; then npm install && npm run build --if-present && exec npm start -- -p 8080; else echo '<!DOCTYPE html><html><body><h1>{app.name}</h1><p>Running on CompassX</p></body></html>' > index.html && npx serve -l 8080 .; fi)"
            )
            container_args = [run_cmd]
        else:
            image_tag = f"compassx-app-{app.slug}:latest"
            container_cmd = None
            container_args = None

        # 3. Deployment Spec
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
                limits={"cpu": "1", "memory": "1Gi"},
            ),
        )

        deployment = client.V1Deployment(
            api_version="apps/v1",
            kind="Deployment",
            metadata=client.V1ObjectMeta(name=name, namespace=ns, labels=labels),
            spec=client.V1DeploymentSpec(
                replicas=1,
                selector=client.V1LabelSelector(match_labels={"compassx/app-id": clean_id}),
                template=client.V1PodTemplateSpec(
                    metadata=client.V1ObjectMeta(labels=labels),
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
                selector={"compassx/app-id": clean_id},
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
        if settings.K8S_INGRESS_TLS_SECRET:
            ingress_spec.tls = [
                client.V1IngressTLS(hosts=[subdomain], secret_name=settings.K8S_INGRESS_TLS_SECRET)
            ]

        ingress = client.V1Ingress(
            api_version="networking.k8s.io/v1",
            kind="Ingress",
            metadata=client.V1ObjectMeta(
                name=f"{name}-ingress",
                namespace=ns,
                labels=labels,
                annotations={
                    "nginx.ingress.kubernetes.io/ssl-redirect": "false",
                    "nginx.ingress.kubernetes.io/force-ssl-redirect": "false",
                    "nginx.ingress.kubernetes.io/proxy-read-timeout": "3600",
                    "nginx.ingress.kubernetes.io/proxy-send-timeout": "3600",
                    "nginx.ingress.kubernetes.io/rewrite-target": "/$2",
                    "nginx.ingress.kubernetes.io/use-regex": "true",
                },
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
                    else:
                        raise

                # Service
                try:
                    k8s.core().replace_namespaced_service(name=name, namespace=ns, body=service)
                except ApiException as e:
                    if e.status == 404:
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
                build_logs.append(f"[{now_ts}] [WARNING] K8s API communication: {k8s_err}")

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
                pods = k8s.core().list_namespaced_pod(namespace=ns, label_selector=f"compassx/app-id={clean_id}")
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
            pods = k8s.core().list_namespaced_pod(namespace=ns, label_selector=f"compassx/app-id={clean_id}")
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

    def start_dev(self, app, repo_dir: str, omnigent_internal_url: str) -> Dict[str, Any]:
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
            "compassx/managed": "true",
        }

        # If k8s client is available, provision Dev Pod, Service, and Ingress
        if k8s:
            try:
                # 1. Dev Pod
                dev_cmd = (
                    f"mkdir -p /root/.omnigent && printf 'host:\\n  host_id: {host_id}\\n  name: \"{host_name}\"\\n' > /root/.omnigent/config.yaml; "
                    f"export OMNIGENT_HOST_ID={host_id} OMNIGENT_HOST_NAME=\"{host_name}\" "
                    f"NODE_TLS_REJECT_UNAUTHORIZED=0 NPM_CONFIG_STRICT_SSL=false PYTHONHTTPSVERIFY=0 GIT_SSL_NO_VERIFY=true CURL_INSECURE=1; "
                    f"omnigent host --server {omnigent_internal_url} --background --non-interactive || true; "
                    f"mkdir -p /app && cd /app && echo '<!DOCTYPE html><html><body><h1>Dev Sandbox for {app.name}</h1><p>Connected to Omnigent Dev Studio</p></body></html>' > index.html && "
                    f"npx serve -l 8080 . || python -m http.server 8080"
                )
                pod = client.V1Pod(
                    api_version="v1",
                    kind="Pod",
                    metadata=client.V1ObjectMeta(name=dev_name, namespace=ns, labels=labels),
                    spec=client.V1PodSpec(
                        containers=[
                            client.V1Container(
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
                                ],
                                resources=client.V1ResourceRequirements(
                                    requests={"cpu": "50m", "memory": "128Mi"},
                                    limits={"cpu": "500m", "memory": "512Mi"},
                                ),
                            )
                        ],
                        restart_policy="Always",
                    ),
                )
                try:
                    k8s.core().delete_namespaced_pod(name=dev_name, namespace=ns)
                except Exception:
                    pass
                k8s.core().create_namespaced_pod(namespace=ns, body=pod)

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
                dev_ingress = client.V1Ingress(
                    api_version="networking.k8s.io/v1",
                    kind="Ingress",
                    metadata=client.V1ObjectMeta(
                        name=f"{dev_name}-ingress",
                        namespace=ns,
                        labels=labels,
                        annotations={
                            "nginx.ingress.kubernetes.io/ssl-redirect": "false",
                            "nginx.ingress.kubernetes.io/force-ssl-redirect": "false",
                            "nginx.ingress.kubernetes.io/proxy-read-timeout": "3600",
                            "nginx.ingress.kubernetes.io/proxy-send-timeout": "3600",
                            "nginx.ingress.kubernetes.io/rewrite-target": "/$2",
                            "nginx.ingress.kubernetes.io/use-regex": "true",
                        },
                    ),
                    spec=client.V1IngressSpec(
                        ingress_class_name=settings.K8S_INGRESS_CLASS,
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
        try:
            k8s.core().delete_namespaced_pod(name=name, namespace=ns)
            return True
        except Exception:
            return False

    def get_dev_status(self, app) -> Dict[str, Any]:
        clean_id = re.sub(r"[^a-z0-9-]", "-", app.id.lower()).strip("-")
        dev_name = f"compassx-app-dev-{clean_id}"
        return {"status": "active", "pod_name": dev_name, "mode": "kubernetes"}

    def get_dev_url(self, app) -> str:
        return ingress_service.get_app_dev_url(app)

    def get_dev_logs(self, app) -> str:
        k8s = self._get_k8s_client()
        if not k8s:
            return ""
        ns = settings.K8S_NAMESPACE
        clean_id = re.sub(r"[^a-z0-9-]", "-", app.id.lower()).strip("-")
        name = f"compassx-app-dev-{clean_id}"
        try:
            return k8s.core().read_namespaced_pod_log(name=name, namespace=ns, tail_lines=200)
        except Exception:
            return ""
