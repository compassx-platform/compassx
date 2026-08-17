"""Kubernetes API client wrapper for the platform layer.

Ported from backend/app/compute/services/k8s_client.py. The
`_fix_bearer_case` and `_disable_dead_local_proxies` workarounds are
preserved verbatim — do not "simplify" them:

- _fix_bearer_case: kubernetes-client v36 changed auth_settings() to read
  api_key['BearerToken'] while the in-cluster loader still sets
  api_key['authorization'] -> 401 anonymous requests.
- _disable_dead_local_proxies: dev machines that point HTTP(S)_PROXY at
  127.0.0.1:9 break local minikube API access.
"""

from __future__ import annotations

import logging
import os
from urllib.parse import urlparse

from compassx.models import DriverUnavailableError

logger = logging.getLogger(__name__)


class K8sApiClient:
    """Wrapper around kubernetes-python-client. Instantiated via DI."""

    def __init__(self, *, skip_ssl_verify: bool = False, clear_local_proxies: bool = True) -> None:
        try:
            import urllib3
            from kubernetes import client, config as k8s_config
            from kubernetes.config.config_exception import ConfigException
        except ImportError as exc:  # pragma: no cover
            raise DriverUnavailableError(
                "kubernetes package not installed. `pip install kubernetes`."
            ) from exc

        self._client = client
        self._skip_ssl_verify = skip_ssl_verify

        try:
            k8s_config.load_incluster_config()
            logger.info("K8s: loaded in-cluster config")
            self._fix_bearer_case()
        except ConfigException:
            try:
                k8s_config.load_kube_config()
                logger.info("K8s: loaded local kubeconfig (~/.kube/config)")
            except ConfigException as exc:
                raise DriverUnavailableError(
                    "Kubernetes not reachable. Run `minikube start` for local development."
                ) from exc

        if clear_local_proxies:
            self._disable_dead_local_proxies()

        if skip_ssl_verify:
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

        client = self._client
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
        client = self._client
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

    def _apply_ssl(self, api):
        if self._skip_ssl_verify:
            api.api_client.configuration.verify_ssl = False
            api.api_client.configuration.ssl_ca_cert = None
        return api

    def core(self):
        return self._apply_ssl(self._client.CoreV1Api())

    def batch(self):
        return self._apply_ssl(self._client.BatchV1Api())

    def apps(self):
        return self._apply_ssl(self._client.AppsV1Api())

    def rbac(self):
        return self._apply_ssl(self._client.RbacAuthorizationV1Api())
