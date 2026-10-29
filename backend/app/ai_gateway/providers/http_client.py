"""HTTP client for upstream model providers.

httpx defaults to the certifi bundle and ignores the OS trust store. The
platform image adds corporate intercept CAs to the system bundle at startup,
so provider calls use that file when it is present.
"""

from __future__ import annotations

import os

import httpx


def gateway_http_client(timeout: httpx.Timeout) -> httpx.AsyncClient:
    system_bundle = "/etc/ssl/certs/ca-certificates.crt"
    bundle = system_bundle if os.path.isfile(system_bundle) else os.environ.get("SSL_CERT_FILE", "")
    verify: bool | str = bundle if bundle and os.path.isfile(bundle) else True
    return httpx.AsyncClient(timeout=timeout, trust_env=False, verify=verify)
