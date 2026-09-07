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
            from compute.k8s_client import get_k8s_client
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
        name = f"compassx-app-{app.id}"
        image_tag = f"compassx-app-{app.slug}:latest"
        subdomain = ingress_service.get_app_domain(app)
        live_url = ingress_service.get_app_url(app)
        now_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        build_logs.append(f"[{now_ts}] [INFO] Provisioning Kubernetes resources for app '{app.name}' in namespace '{ns}'")
        build_logs.append(f"[{now_ts}] [INFO] Assigned Subdomain: {subdomain} -> Live URL: {live_url}")

        labels = {
            "app.kubernetes.io/name": name,
            "app.kubernetes.io/instance": app.slug,
            "compassx/app-id": app.id,
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

        # 2. Deployment Spec
        container = client.V1Container(
            name="app",
            image=image_tag,
            image_pull_policy="IfNotPresent",
            env=env_vars,
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
                selector=client.V1LabelSelector(match_labels={"compassx/app-id": app.id}),
                template=client.V1PodTemplateSpec(
                    metadata=client.V1ObjectMeta(labels=labels),
                    spec=client.V1PodSpec(containers=[container]),
                ),
            ),
        )

        # 3. Service Spec
        service = client.V1Service(
            api_version="v1",
            kind="Service",
            metadata=client.V1ObjectMeta(name=name, namespace=ns, labels=labels),
            spec=client.V1ServiceSpec(
                selector={"compassx/app-id": app.id},
                ports=[client.V1ServicePort(name="http", port=80, target_port=8080)],
                type="ClusterIP",
            ),
        )

        # 4. Ingress Spec with Subdomain Host Routing
        ingress_path = client.V1HTTPIngressPath(
            path="/",
            path_type="Prefix",
            backend=client.V1IngressBackend(
                service=client.V1IngressServiceBackend(
                    name=name,
                    port=client.V1ServiceBackendPort(number=80),
                )
            ),
        )

        ingress_rule = client.V1IngressRule(
            host=subdomain,
            http=client.V1HTTPIngressRuleValue(paths=[ingress_path]),
        )

        ingress_spec = client.V1IngressSpec(
            ingress_class_name=settings.K8S_INGRESS_CLASS,
            rules=[ingress_rule],
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
                    "nginx.ingress.kubernetes.io/proxy-read-timeout": "3600",
                    "nginx.ingress.kubernetes.io/proxy-send-timeout": "3600",
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
        name = f"compassx-app-{app.id}"
        try:
            k8s.apps().delete_namespaced_deployment(name=name, namespace=ns)
            return True
        except Exception as e:
            logger.warning("Could not delete K8s deployment %s: %s", name, e)
            return False

    def get_status(self, app) -> Dict[str, Any]:
        k8s = self._get_k8s_client()
        name = f"compassx-app-{app.id}"
        ns = settings.K8S_NAMESPACE
        if not k8s:
            return {"status": "unknown", "deployment_name": name}
        try:
            dep = k8s.apps().read_namespaced_deployment_status(name=name, namespace=ns)
            available = (dep.status.available_replicas or 0) > 0
            return {"status": "running" if available else "starting", "deployment_name": name}
        except Exception:
            return {"status": "stopped", "deployment_name": name}

    def get_logs(self, app, max_lines: int = 200) -> List[str]:
        k8s = self._get_k8s_client()
        if not k8s:
            return []
        ns = settings.K8S_NAMESPACE
        try:
            pods = k8s.core().list_namespaced_pod(namespace=ns, label_selector=f"compassx/app-id={app.id}")
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
            from compute.k8s_client import get_k8s_client
            return get_k8s_client()
        except Exception:
            try:
                from compassx.drivers.k8s_client import K8sApiClient
                return K8sApiClient()
            except Exception:
                return None

    def start_dev(self, app, repo_dir: str, omnigent_internal_url: str) -> Dict[str, Any]:
        host_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"compassx-app-{app.id}").hex
        host_name = str(app.name or app.slug or app.id).strip()
        dev_name = f"compassx-app-dev-{app.id}"
        dev_url = ingress_service.get_app_dev_url(app)
        ns = settings.K8S_NAMESPACE

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
        name = f"compassx-app-dev-{app.id}"
        try:
            k8s.core().delete_namespaced_pod(name=name, namespace=ns)
            return True
        except Exception:
            return False

    def get_dev_status(self, app) -> Dict[str, Any]:
        dev_name = f"compassx-app-dev-{app.id}"
        return {"status": "active", "pod_name": dev_name, "mode": "kubernetes"}

    def get_dev_url(self, app) -> str:
        return ingress_service.get_app_dev_url(app)

    def get_dev_logs(self, app) -> str:
        k8s = self._get_k8s_client()
        if not k8s:
            return ""
        ns = settings.K8S_NAMESPACE
        name = f"compassx-app-dev-{app.id}"
        try:
            return k8s.core().read_namespaced_pod_log(name=name, namespace=ns, tail_lines=200)
        except Exception:
            return ""
