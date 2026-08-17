"""Kubernetes client singleton for the compute module."""
import logging
import os
from urllib.parse import urlparse

import urllib3
from kubernetes import client, config as k8s_config
from kubernetes.config.config_exception import ConfigException

from compute.config import compute_settings

logger = logging.getLogger(__name__)


class K8sClient:
    """Wrapper around kubernetes-python-client, initialised once at startup."""

    def __init__(self) -> None:
        """Attempt in-cluster config, fall back to local kubeconfig."""
        try:
            k8s_config.load_incluster_config()
            logger.info("K8s: loaded in-cluster config")
            self._fix_bearer_case()
        except ConfigException:
            try:
                k8s_config.load_kube_config()
                logger.info("K8s: loaded local kubeconfig (~/.kube/config)")
            except ConfigException as exc:
                raise RuntimeError(
                    "Kubernetes not reachable. Run `minikube start` for local development."
                ) from exc

        self._disable_dead_local_proxies()

        # Disable SSL verification if requested (must be set after loading config)
        if compute_settings.SKIP_K8S_SSL_VERIFY:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            config = client.Configuration.get_default_copy()
            config.verify_ssl = False
            config.ssl_ca_cert = None
            client.Configuration.set_default(config)
            logger.info("K8s: SSL verification disabled")

    def _fix_bearer_case(self) -> None:
        """Fix kubernetes-client v36 in-cluster auth key mismatch.

        kubernetes==36 changed Configuration.auth_settings() to look for
        api_key['BearerToken'], but InClusterConfigLoader._set_config still
        sets api_key['authorization']. Result: no Authorization header sent,
        API server returns 401 (anonymous request).

        Fix: patch _set_config to also set api_key['BearerToken'], and wrap
        the refresh hook so it stays correct after token rotation.
        """
        from kubernetes.config.incluster_config import InClusterConfigLoader

        original_set_config = InClusterConfigLoader._set_config

        def _set_config_fixed(self_loader, client_configuration) -> None:
            original_set_config(self_loader, client_configuration)
            # Mirror token into the key that auth_settings() checks in v36+.
            token = client_configuration.api_key.get("authorization", "")
            if token:
                # Normalise prefix to 'Bearer' (RFC 6750); loader sets 'bearer'.
                if token.startswith("bearer "):
                    token = "Bearer " + token[len("bearer "):]
                    client_configuration.api_key["authorization"] = token
                client_configuration.api_key["BearerToken"] = token

        InClusterConfigLoader._set_config = _set_config_fixed

        # Re-apply to the already-loaded global config.
        cfg = client.Configuration.get_default_copy()
        auth = cfg.api_key.get("authorization", "")
        if auth:
            if auth.startswith("bearer "):
                auth = "Bearer " + auth[len("bearer "):]
                cfg.api_key["authorization"] = auth
            cfg.api_key["BearerToken"] = auth
            client.Configuration.set_default(cfg)

        logger.info("K8s: patched InClusterConfigLoader for v36 BearerToken key")

    def _disable_dead_local_proxies(self) -> None:
        """Clear broken local proxy env vars for local K8s API access.

        In some dev environments, HTTP(S)_PROXY points to 127.0.0.1:9 as a way
        to block outbound traffic. The kubernetes client inherits that proxy and
        then fails to reach the local Minikube API server on 127.0.0.1.
        """
        if compute_settings.COMPASSX_ENV != "local":
            return

        config = client.Configuration.get_default_copy()
        host = config.host or ""
        parsed = urlparse(host)
        hostname = parsed.hostname
        if hostname not in {"127.0.0.1", "localhost"}:
            return

        proxy_keys = (
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "http_proxy",
            "https_proxy",
        )
        cleared = []
        for key in proxy_keys:
            value = os.environ.get(key)
            if value:
                cleared.append(f"{key}={value}")
                os.environ.pop(key, None)

        # Keep loopback addresses explicitly bypassed even if parent env is noisy.
        no_proxy = os.environ.get("NO_PROXY") or os.environ.get("no_proxy") or ""
        required_hosts = ["127.0.0.1", "localhost", "::1"]
        values = [item.strip() for item in no_proxy.split(",") if item.strip()]
        for item in required_hosts:
            if item not in values:
                values.append(item)
        joined = ",".join(values)
        os.environ["NO_PROXY"] = joined
        os.environ["no_proxy"] = joined

        # The generated kubernetes client snapshots proxy settings into the
        # client Configuration object, so we must clear it there too.
        config.proxy = None
        config.no_proxy = joined
        client.Configuration.set_default(config)

        if cleared:
            logger.warning(
                "K8s: cleared proxy env for local API host %s: %s",
                host,
                "; ".join(cleared),
            )

    def core(self) -> client.CoreV1Api:
        """Return CoreV1Api instance."""
        api = client.CoreV1Api()
        if compute_settings.SKIP_K8S_SSL_VERIFY:
            api.api_client.configuration.verify_ssl = False
            api.api_client.configuration.ssl_ca_cert = None
        return api

    def batch(self) -> client.BatchV1Api:
        """Return BatchV1Api instance."""
        api = client.BatchV1Api()
        if compute_settings.SKIP_K8S_SSL_VERIFY:
            api.api_client.configuration.verify_ssl = False
            api.api_client.configuration.ssl_ca_cert = None
        return api

    def apps(self) -> client.AppsV1Api:
        """Return AppsV1Api instance."""
        api = client.AppsV1Api()
        if compute_settings.SKIP_K8S_SSL_VERIFY:
            api.api_client.configuration.verify_ssl = False
            api.api_client.configuration.ssl_ca_cert = None
        return api

    def rbac(self) -> client.RbacAuthorizationV1Api:
        """Return RbacAuthorizationV1Api instance."""
        api = client.RbacAuthorizationV1Api()
        if compute_settings.SKIP_K8S_SSL_VERIFY:
            api.api_client.configuration.verify_ssl = False
            api.api_client.configuration.ssl_ca_cert = None
        return api

    def is_local(self) -> bool:
        """True when COMPASSX_ENV=local."""
        return compute_settings.COMPASSX_ENV == "local"


_client_instance: K8sClient | None = None


def get_k8s_client() -> K8sClient:
    """Return the singleton K8sClient, initialising on first call."""
    global _client_instance
    if _client_instance is None:
        logger.debug("K8s: initialising singleton client")
        _client_instance = K8sClient()
    return _client_instance
