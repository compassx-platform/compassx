"""Ingress and URL resolution service for multi-mode environments (local-dev, docker, kubernetes)."""
import os
import re
import subprocess
import logging
from typing import Optional, Dict, Any

from app.config import settings

logger = logging.getLogger(__name__)


class IngressService:
    """Centralized URL, domain, and ingress resolution for applications and Omnigent Dev Studio."""

    def __init__(self):
        self._mode_override: Optional[str] = None
        self._cached_mode: Optional[str] = None

    def set_mode_override(self, mode: Optional[str]) -> None:
        """Testing hook to explicitly override mode."""
        self._mode_override = mode
        self._cached_mode = None

    def get_active_mode(self) -> str:
        """Determine active deployment/runtime mode: 'kubernetes' | 'docker' | 'local'."""
        if self._mode_override:
            return self._mode_override.lower()
        if self._cached_mode:
            return self._cached_mode

        mode = self._resolve_active_mode()
        self._cached_mode = mode
        return mode

    def _resolve_active_mode(self) -> str:
        explicit = (settings.APP_RUNNER_MODE or os.getenv("APP_RUNNER_MODE", "")).strip().lower()
        if explicit in ("kubernetes", "k8s"):
            return "kubernetes"
        if explicit == "docker":
            return "docker"
        if explicit in ("local", "local-dev"):
            return "local"

        # Check CompassX compute environment
        try:
            from app.compute.services.config import compute_settings
            if compute_settings.is_k8s() or os.getenv("KUBERNETES_SERVICE_HOST"):
                return "kubernetes"
        except Exception:
            if os.getenv("KUBERNETES_SERVICE_HOST"):
                return "kubernetes"

        # Check Docker availability
        try:
            res = subprocess.run(["docker", "version"], capture_output=True, text=True, timeout=5, check=False)
            if res.returncode == 0:
                return "docker"
        except Exception:
            pass

        return "local"

    def is_kubernetes(self) -> bool:
        return self.get_active_mode() == "kubernetes"

    def is_docker(self) -> bool:
        return self.get_active_mode() == "docker"

    def is_local(self) -> bool:
        return self.get_active_mode() == "local"

    # ── Live Application URL Resolution ─────────────────────────────────────

    def get_app_domain(self, app) -> str:
        """Get the subdomain / FQDN for a production app in Kubernetes."""
        slug = getattr(app, "slug", str(app))
        base_domain = settings.APP_BASE_DOMAIN.strip().lstrip(".")
        template = settings.APP_DOMAIN_TEMPLATE
        if "{slug}" in template and "{base_domain}" in template:
            return template.format(slug=slug, base_domain=base_domain)
        elif "{slug}" in template:
            return template.format(slug=slug)
        return f"{slug}.{base_domain}"

    def get_app_url(self, app, host_port: Optional[int] = None) -> str:
        """Resolve public live URL for an application."""
        mode = self.get_active_mode()
        slug = getattr(app, "slug", str(app))
        if mode == "kubernetes":
            domain = self.get_app_domain(app)
            # 1. Custom Public Domain (e.g. app1.domain.com)
            if domain and not any(domain.endswith(ext) for ext in (".internal", ".local", ".lan")):
                scheme = "https" if getattr(settings, "K8S_USE_HTTPS", True) else "http"
                return f"{scheme}://{domain}"

            # 2. Path-based ingress routing on specific ingress host / IP
            ingress_host = getattr(settings, "K8S_INGRESS_HOST", "") or os.getenv("K8S_INGRESS_HOST", "")
            if ingress_host:
                scheme = "https" if getattr(settings, "K8S_USE_HTTPS", True) else "http"
                return f"{scheme}://{ingress_host}/apps/{slug}/"

            # 3. Universal path-based relative URL
            return f"/apps/{slug}/"

        port = host_port or 8080
        return f"http://localhost:{port}"

    # ── Dev Sandbox URL Resolution ──────────────────────────────────────────

    def get_app_dev_domain(self, app) -> str:
        """Get the subdomain for a dev sandbox container/pod in Kubernetes."""
        slug = getattr(app, "slug", str(app))
        base_domain = settings.APP_BASE_DOMAIN.strip().lstrip(".")
        return f"{slug}-dev.{base_domain}"

    def get_app_dev_url(self, app, dev_port: Optional[int] = None) -> str:
        """Resolve public preview URL for a development sandbox."""
        mode = self.get_active_mode()
        slug = getattr(app, "slug", str(app))
        if mode == "kubernetes":
            domain = self.get_app_dev_domain(app)
            # 1. Custom Public Domain
            if domain and not any(domain.endswith(ext) for ext in (".internal", ".local", ".lan")):
                scheme = "https" if getattr(settings, "K8S_USE_HTTPS", True) else "http"
                return f"{scheme}://{domain}"

            # 2. Path-based ingress routing on specific ingress host / IP
            ingress_host = getattr(settings, "K8S_INGRESS_HOST", "") or os.getenv("K8S_INGRESS_HOST", "")
            if ingress_host:
                scheme = "https" if getattr(settings, "K8S_USE_HTTPS", True) else "http"
                return f"{scheme}://{ingress_host}/apps/{slug}-dev/"

            # 3. Universal path-based relative URL
            return f"/apps/{slug}-dev/"

        port = dev_port or 9201
        return f"http://localhost:{port}"

    # ── Omnigent Server URL Resolution ──────────────────────────────────────

    def get_omnigent_domain(self) -> str:
        """Get the FQDN for the shared Omnigent Server in Kubernetes (e.g. devstudio.domain.com)."""
        base_domain = settings.APP_BASE_DOMAIN.strip().lstrip(".")
        template = settings.OMNIGENT_DOMAIN_TEMPLATE
        if "{base_domain}" in template:
            return template.format(base_domain=base_domain)
        return f"devstudio.{base_domain}"

    def get_omnigent_public_url(self) -> str:
        """Resolve the browser-facing Omnigent Server URL (Dev Studio)."""
        if settings.OMNIGENT_PUBLIC_URL:
            return settings.OMNIGENT_PUBLIC_URL.rstrip("/")

        mode = self.get_active_mode()
        if mode == "kubernetes":
            domain = self.get_omnigent_domain()
            if domain and not any(domain.endswith(ext) for ext in (".internal", ".local", ".lan")):
                scheme = "https" if getattr(settings, "K8S_USE_HTTPS", True) else "http"
                return f"{scheme}://{domain}"

            ingress_host = getattr(settings, "K8S_INGRESS_HOST", "") or os.getenv("K8S_INGRESS_HOST", "")
            if ingress_host:
                scheme = "https" if getattr(settings, "K8S_USE_HTTPS", True) else "http"
                return f"{scheme}://{ingress_host}/devstudio"

            return "/devstudio"

        return (getattr(settings, "OMNIGENT_SERVER_URL", "") or "http://localhost:6767").rstrip("/")

    def get_omnigent_internal_url(self) -> str:
        """Resolve cluster/container internal URL for daemon agents to connect."""
        if settings.OMNIGENT_INTERNAL_URL:
            return settings.OMNIGENT_INTERNAL_URL.rstrip("/")

        mode = self.get_active_mode()
        if mode == "kubernetes":
            ns = settings.K8S_NAMESPACE
            return f"http://compassx-omnigent-server.{ns}.svc.cluster.local:6767"
        elif mode == "docker":
            return "http://compassx-omnigent-server:6767"
        else:
            return "http://localhost:6767"

    def get_omnigent_session_url(self, session_id: str) -> str:
        """Construct full URL to an Omnigent session."""
        base = self.get_omnigent_public_url()
        return base

    def ensure_app_ingress(
        self,
        app,
        service_name: Optional[str] = None,
        service_port: int = 8080,
        is_dev: bool = True,
    ) -> bool:
        """Ensure Kubernetes Ingress resource with Let's Encrypt TLS exists for an app.
        
        Configures both main app ({slug}.{base_domain}) and dev app ({slug}-dev.{base_domain})
        with automatic TLS certificates managed by cert-manager.
        """
        if not self.is_kubernetes():
            return False

        try:
            from app.compute.services.k8s_client import get_k8s_client
            from kubernetes import client
            from kubernetes.client.exceptions import ApiException

            k8s = get_k8s_client()
            if not k8s:
                return False

            ns = settings.K8S_NAMESPACE
            app_id = getattr(app, "id", str(app))
            clean_id = re.sub(r"[^a-z0-9-]", "-", str(app_id).lower()).strip("-")
            slug = getattr(app, "slug", clean_id)
            if not slug:
                slug = clean_id

            app_domain = self.get_app_domain(app)
            dev_domain = self.get_app_dev_domain(app)

            # Determine target service name
            target_svc = service_name or (f"compassx-sb-dev-app-{clean_id}" if is_dev else f"compassx-app-{clean_id}")
            ingress_name = f"compassx-app-dev-{clean_id}-ingress" if is_dev else f"compassx-app-{clean_id}-ingress"

            tls_secret_main = f"{slug}-tls"
            tls_secret_dev = f"{slug}-dev-tls"

            tls_list = [
                client.V1IngressTLS(hosts=[app_domain], secret_name=tls_secret_main),
                client.V1IngressTLS(hosts=[dev_domain], secret_name=tls_secret_dev),
            ]

            rules = [
                client.V1IngressRule(
                    host=app_domain,
                    http=client.V1HTTPIngressRuleValue(
                        paths=[
                            client.V1HTTPIngressPath(
                                path="/()(.*)",
                                path_type="ImplementationSpecific",
                                backend=client.V1IngressBackend(
                                    service=client.V1IngressServiceBackend(
                                        name=target_svc,
                                        port=client.V1ServiceBackendPort(number=service_port),
                                    )
                                ),
                            ),
                            client.V1HTTPIngressPath(
                                path=f"/apps/{slug}(/|$)(.*)",
                                path_type="ImplementationSpecific",
                                backend=client.V1IngressBackend(
                                    service=client.V1IngressServiceBackend(
                                        name=target_svc,
                                        port=client.V1ServiceBackendPort(number=service_port),
                                    )
                                ),
                            ),
                        ]
                    ),
                ),
                client.V1IngressRule(
                    host=dev_domain,
                    http=client.V1HTTPIngressRuleValue(
                        paths=[
                            client.V1HTTPIngressPath(
                                path="/()(.*)",
                                path_type="ImplementationSpecific",
                                backend=client.V1IngressBackend(
                                    service=client.V1IngressServiceBackend(
                                        name=target_svc,
                                        port=client.V1ServiceBackendPort(number=service_port),
                                    )
                                ),
                            ),
                            client.V1HTTPIngressPath(
                                path=f"/apps/{slug}-dev(/|$)(.*)",
                                path_type="ImplementationSpecific",
                                backend=client.V1IngressBackend(
                                    service=client.V1IngressServiceBackend(
                                        name=target_svc,
                                        port=client.V1ServiceBackendPort(number=service_port),
                                    )
                                ),
                            ),
                        ]
                    ),
                ),
            ]

            annotations = {
                "nginx.ingress.kubernetes.io/ssl-redirect": "false",
                "nginx.ingress.kubernetes.io/force-ssl-redirect": "false",
                "nginx.ingress.kubernetes.io/proxy-read-timeout": "3600",
                "nginx.ingress.kubernetes.io/proxy-send-timeout": "3600",
                "nginx.ingress.kubernetes.io/rewrite-target": "/$2",
                "nginx.ingress.kubernetes.io/use-regex": "true",
            }
            if getattr(settings, "K8S_INGRESS_CLUSTER_ISSUER", None):
                annotations["cert-manager.io/cluster-issuer"] = settings.K8S_INGRESS_CLUSTER_ISSUER

            ingress_body = client.V1Ingress(
                api_version="networking.k8s.io/v1",
                kind="Ingress",
                metadata=client.V1ObjectMeta(
                    name=ingress_name,
                    namespace=ns,
                    labels={
                        "app.kubernetes.io/instance": slug,
                        "compassx/app-id": clean_id,
                        "compassx/managed": "true",
                    },
                    annotations=annotations,
                ),
                spec=client.V1IngressSpec(
                    ingress_class_name=settings.K8S_INGRESS_CLASS,
                    tls=tls_list,
                    rules=rules,
                ),
            )

            try:
                k8s.networking().replace_namespaced_ingress(name=ingress_name, namespace=ns, body=ingress_body)
                logger.info("Updated Ingress %s with TLS for app %s (%s)", ingress_name, slug, app_domain)
            except ApiException as exc:
                if exc.status == 404:
                    k8s.networking().create_namespaced_ingress(namespace=ns, body=ingress_body)
                    logger.info("Created Ingress %s with TLS for app %s (%s)", ingress_name, slug, app_domain)
                else:
                    raise
            return True
        except Exception as e:
            logger.warning("Could not ensure app ingress for %s: %s", getattr(app, "slug", getattr(app, "id", "")), e)
            return False


ingress_service = IngressService()
