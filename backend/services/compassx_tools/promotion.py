"""Promotion helper for CompassX tools SDK.

Enables in-notebook promotion of @cx.tool functions directly to the Unified Catalog:
    cx.tools.promote(fetch_todo_item, catalog="main", schema="default")
"""

from __future__ import annotations

import inspect
import json
import os
from typing import Any, Callable, Optional, Sequence
import urllib.request
import urllib.error

from .decorator import extract_param_schema


class PromotionResult:
    """Represents the outcome of promoting a tool to the Unified Catalog."""

    def __init__(self, data: dict[str, Any]):
        self.id = data.get("id", "")
        self.catalog = data.get("catalog") or data.get("catalog_name", "")
        self.schema = data.get("schema") or data.get("schema_name", "")
        self.name = data.get("name", "")
        self.full_name = data.get("full_name", f"{self.catalog}.{self.schema}.{self.name}")
        self.version = data.get("current_version", 1)
        self.description = data.get("description", "")
        self.param_schema = data.get("param_schema", {})
        self.connections = data.get("connection_dependencies", [])
        self.data = data

    def __repr__(self) -> str:
        return (
            f"<PromotedTool '{self.full_name}' (v{self.version}) "
            f"connections={self.connections}>"
        )

    def _repr_pretty_(self, p, cycle):
        if cycle:
            p.text(str(self))
            return
        p.text(
            f"Successfully Promoted to Unified Catalog!\n"
            f"  * Tool: {self.full_name} (v{self.version})\n"
            f"  * Connections: {', '.join(self.connections) if self.connections else 'None'}\n"
            f"  * Description: {self.description or 'No description'}\n"
            f"  * ID: {self.id}"
        )


def promote(
    fn: Callable[..., Any],
    catalog: str = "main",
    schema: str = "default",
    name: Optional[str] = None,
    description: Optional[str] = None,
    connections: Optional[Sequence[str]] = None,
    source_notebook_id: Optional[str] = None,
    notebook: Optional[str] = None,
) -> PromotionResult:
    """Promote a Python function to the Unified Catalog as a first-class agent tool.

    Parameters:
        fn: The Python function (decorated with @cx.tool or standard callable).
        catalog: Target catalog name in Unified Catalog (default: 'main').
        schema: Target schema name in Unified Catalog (default: 'default').
        name: Override tool name (defaults to @cx.tool name or fn.__name__).
        description: Override tool description.
        connections: Override declared connection dependencies.
        source_notebook_id: Optional source notebook asset path/UUID for provenance.
        notebook: Alias for source_notebook_id.

    Returns:
        PromotionResult with metadata and version confirmation.
    """
    tool_name = name or getattr(fn, "_tool_name", getattr(fn, "__name__", "tool"))
    tool_desc = description or getattr(fn, "_tool_description", inspect.getdoc(fn) or "")
    tool_conns = list(connections) if connections is not None else getattr(fn, "_tool_connections", [])
    tool_schema = getattr(fn, "_tool_param_schema", extract_param_schema(fn))

    # Extract clean source code of the function
    try:
        source_code = inspect.getsource(fn)
    except Exception:
        source_code = f"def {tool_name}():\n    pass\n"

    nb_id = (
        notebook
        or source_notebook_id
        or os.environ.get("COMPASSX_NOTEBOOK_PATH")
        or os.environ.get("COMPASSX_NOTEBOOK_ID")
        or os.environ.get("NOTEBOOK_PATH")
        or os.environ.get("NOTEBOOK_ID")
        or os.environ.get("JPY_SESSION_NAME")
    )

    payload = {
        "catalog": catalog,
        "schema": schema,
        "schema_name": schema,
        "name": tool_name,
        "description": tool_desc,
        "source_code": source_code,
        "param_schema": tool_schema,
        "connection_dependencies": tool_conns,
        "source_notebook_object_id": nb_id,
    }

    catalog_url = os.environ.get("CATALOG_API_URL") or os.environ.get("KERNEL_CATALOG_API_URL")
    token = os.environ.get("NOTEBOOK_SESSION_TOKEN") or os.environ.get("KERNEL_NOTEBOOK_SESSION_TOKEN")

    urls = [
        f"http://host.docker.internal:8000/api/v1/catalog/tools/promote",
        f"http://host.docker.internal:8000/catalog/tools/promote",
        f"http://localhost:8000/api/v1/catalog/tools/promote",
        f"http://127.0.0.1:8000/api/v1/catalog/tools/promote",
    ]

    if catalog_url:
        base = catalog_url.rstrip("/")
        urls.insert(0, f"{base}/tools/promote")
        urls.insert(1, f"{base.replace('/catalog', '')}/catalog/tools/promote")

    headers = {
        "Content-Type": "application/json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    body_bytes = json.dumps(payload).encode("utf-8")
    last_error = None

    for url in urls:
        try:
            req = urllib.request.Request(url, data=body_bytes, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status in (200, 201):
                    data = json.loads(resp.read().decode("utf-8"))
                    result = PromotionResult(data)
                    print(
                        f"✓ Promoted tool '{result.full_name}' (v{result.version}) to Unified Catalog!"
                    )
                    return result
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="replace")
            last_error = f"HTTP {exc.code}: {err_body}"
        except Exception as exc:
            last_error = str(exc)
            continue

    # Fallback to direct DB promotion if running in backend/local process
    try:
        from app.database import AccountSessionLocal
        from app.catalog.tool_schemas import ToolPromoteRequest
        from app.catalog import tool_service as svc

        db = AccountSessionLocal()
        try:
            req_obj = ToolPromoteRequest(**payload)
            tool_row = svc.promote_tool(db, req_obj, user_id="notebook_user")
            data = {
                "id": tool_row.id,
                "catalog": tool_row.catalog_name,
                "schema_name": tool_row.schema_name,
                "name": tool_row.name,
                "full_name": tool_row.full_name,
                "current_version": tool_row.current_version,
                "description": tool_row.description,
                "param_schema": tool_row.param_schema,
                "connection_dependencies": tool_row.connection_dependencies,
            }
            result = PromotionResult(data)
            print(
                f"✓ Promoted tool '{result.full_name}' (v{result.version}) to Unified Catalog!"
            )
            return result
        finally:
            db.close()
    except Exception:
        pass

    raise RuntimeError(f"Failed to promote tool to catalog API: {last_error}")
