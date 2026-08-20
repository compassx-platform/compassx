"""Connection registry and resolver for cx.connections."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

from .client import ConnectionClient, ConnectionUnreachableError


class ConnectionRegistry:
    """Manages active external connections available during tool execution."""

    def __init__(self) -> None:
        self._connections: Dict[str, Any] = {}

    def register(
        self,
        name: str,
        base_url: str = "",
        auth_config: Any = None,
        connector_type: str = "custom",
        config: Optional[dict[str, Any]] = None,
    ) -> ConnectionClient:
        """Register a connection instance directly."""
        client = ConnectionClient(
            name=name,
            base_url=base_url or (config.get("base_url", "") if config else ""),
            auth_config=auth_config,
            connector_type=connector_type,
        )
        self._connections[name] = client
        # Also alias without catalog/schema prefix if 3-part FQN
        if "." in name:
            short_name = name.split(".")[-1]
            self._connections[short_name] = client
        return client

    def set_active_connections(self, connections_dict: dict[str, dict[str, Any]]) -> None:
        """Set or update multiple connections from a dict."""
        for name, config in connections_dict.items():
            self.register(
                name=name,
                base_url=config.get("base_url", ""),
                auth_config=config.get("auth_config"),
                connector_type=config.get("connector_type", "custom"),
                config=config.get("config"),
            )

    def _load_from_env(self, name: str) -> Optional[ConnectionClient]:
        """Try loading connection config from environment variables."""
        # 1. Check CX_CONNECTIONS_JSON
        env_json = os.environ.get("CX_CONNECTIONS_JSON")
        if env_json:
            try:
                data = json.loads(env_json)
                if name in data:
                    cfg = data[name]
                    return self.register(
                        name=name,
                        base_url=cfg.get("base_url", ""),
                        auth_config=cfg.get("auth_config"),
                        connector_type=cfg.get("connector_type", "custom"),
                        config=cfg.get("config"),
                    )
                # Check by short name if FQN key
                for k, cfg in data.items():
                    if k.split(".")[-1] == name or name.split(".")[-1] == k:
                        return self.register(
                            name=name,
                            base_url=cfg.get("base_url", ""),
                            auth_config=cfg.get("auth_config"),
                            connector_type=cfg.get("connector_type", "custom"),
                            config=cfg.get("config"),
                        )
            except Exception:
                pass

        # 2. Check individual env vars: CX_CONN_<NAME>_BASE_URL, etc.
        prefix = f"CX_CONN_{name.upper().replace('.', '_')}_"
        base_url = os.environ.get(f"{prefix}BASE_URL") or os.environ.get(f"{prefix}URL")
        if base_url:
            auth_raw = os.environ.get(f"{prefix}AUTH")
            connector_type = os.environ.get(f"{prefix}TYPE", "custom")
            return self.register(
                name=name,
                base_url=base_url,
                auth_config=auth_raw,
                connector_type=connector_type,
            )

        return None

    def _load_from_catalog(self, name: str) -> Optional[ConnectionClient]:
        """Try fetching connection metadata from the catalog API or DB in notebook runtime."""
        catalog_url = os.environ.get("CATALOG_API_URL") or os.environ.get("KERNEL_CATALOG_API_URL")
        token = os.environ.get("NOTEBOOK_SESSION_TOKEN") or os.environ.get("KERNEL_NOTEBOOK_SESSION_TOKEN")

        urls = [
            f"http://host.docker.internal:8000/api/v1/connections/{name}",
            f"http://host.docker.internal:8000/api/v1/connections",
            f"http://localhost:8000/api/v1/connections/{name}",
            f"http://localhost:8000/api/v1/connections",
            f"http://127.0.0.1:8000/api/v1/connections/{name}",
        ]

        if catalog_url:
            base = catalog_url.rstrip("/")
            urls.append(f"{base}/connections/{name}")
            urls.append(f"{base.replace('/catalog', '')}/connections/{name}")
            urls.append(f"{base}/connections")
            urls.append(f"{base.replace('/catalog', '')}/connections")

        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        import urllib.request
        import urllib.error

        for url in urls:
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=2) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8"))
                        if isinstance(data, list):
                            for item in data:
                                if item.get("name") == name or item.get("full_name") == name or item.get("id") == name:
                                    return self.register(
                                        name=name,
                                        base_url=(item.get("config") or {}).get("base_url", ""),
                                        connector_type=item.get("connector_type", "custom"),
                                        config=item.get("config") or {},
                                    )
                        elif isinstance(data, dict) and (data.get("name") or data.get("id")):
                            return self.register(
                                name=name,
                                base_url=(data.get("config") or {}).get("base_url", ""),
                                connector_type=data.get("connector_type", "custom"),
                                config=data.get("config") or {},
                            )
            except Exception:
                continue

        # Direct database fallback if running in same process or local backend
        try:
            from app.database import AccountSessionLocal
            from app.catalog.models import UnifiedCatalogConnection
            db = AccountSessionLocal()
            try:
                conn_row = db.query(UnifiedCatalogConnection).filter(
                    (UnifiedCatalogConnection.name == name) |
                    (UnifiedCatalogConnection.full_name == name) |
                    (UnifiedCatalogConnection.id == name)
                ).first()
                if conn_row:
                    return self.register(
                        name=name,
                        base_url=(conn_row.config or {}).get("base_url", ""),
                        connector_type=conn_row.connector_type or "custom",
                        config=conn_row.config or {},
                    )
            finally:
                db.close()
        except Exception:
            pass

        return None

    def get(self, name: str) -> Any:
        """Retrieve a configured connection by name or FQN."""
        if name in self._connections:
            return self._connections[name]

        # Check by short name
        short_name = name.split(".")[-1] if "." in name else name
        if short_name in self._connections:
            return self._connections[short_name]

        client = self._load_from_env(name)
        if client is not None:
            return client

        client = self._load_from_catalog(name)
        if client is not None:
            return client

        raise ValueError(
            f"External connection '{name}' is not configured or resolved in the current environment. "
            f"Declared connections must be registered in the Unified Catalog or supplied at tool execution time."
        )

    def clear(self) -> None:
        """Clear registered connections."""
        self._connections.clear()


# Global singleton instance
connections = ConnectionRegistry()
