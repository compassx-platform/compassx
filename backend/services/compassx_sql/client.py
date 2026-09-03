import json
import os
from typing import Any
import httpx
import pandas as pd


class CompassXQueryError(Exception):
    pass


class CompassXSchemaError(CompassXQueryError):
    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.details = details or {}


def _get_auth_and_url() -> tuple[str, str, dict[str, str]]:
    token = (
        os.environ.get("NOTEBOOK_SESSION_TOKEN")
        or os.environ.get("KERNEL_NOTEBOOK_SESSION_TOKEN")
        or os.environ.get("JUPYTER_TOKEN")
        or "dev-session-token"
    )
    api_url = os.environ.get("KERNEL_CATALOG_API_URL") or os.environ.get("CATALOG_API_URL") or "http://127.0.0.1:8000/api/v1/catalog"
    if (os.path.exists("/.dockerenv") or os.environ.get("CONTAINER") == "true") and api_url.startswith(("http://localhost", "https://localhost", "http://127.0.0.1", "https://127.0.0.1")):
        try:
            from compassx.lookup import try_resolve_url_container
            api_url = try_resolve_url_container("backend", "http://localhost:8000") + "/api/v1/catalog"
        except Exception:
            pass
        if api_url.startswith(("http://localhost", "https://localhost", "http://127.0.0.1", "https://127.0.0.1")):
            host_gateway = os.environ.get("COMPASSX_HOST_GATEWAY", "host.docker.internal")
            api_url = api_url.replace("localhost", host_gateway).replace("127.0.0.1", host_gateway)

    ws_id = os.environ.get("WORKSPACE_ID") or os.environ.get("KERNEL_WORKSPACE_ID") or os.environ.get("COMPASSX_WORKSPACE_ID")
    ws_slug = os.environ.get("WORKSPACE_SLUG") or os.environ.get("KERNEL_WORKSPACE_SLUG") or os.environ.get("COMPASSX_WORKSPACE_SLUG")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    if ws_id:
        headers["x-workspace-id"] = ws_id
    if ws_slug:
        headers["x-workspace-slug"] = ws_slug

    return token, api_url.rstrip("/"), headers


def sql(query: str, *, warehouse: str | None = None, timeout: int = 120) -> pd.DataFrame:
    token, api_url, headers = _get_auth_and_url()
    url = f"{api_url}/query"

    payload = {
        "query": query,
        "warehouse": warehouse,
        "timeout_seconds": timeout,
    }

    try:
        resp = httpx.post(url, headers=headers, json=payload, timeout=timeout + 5)
        resp.raise_for_status()
        data = resp.json()
    except (httpx.ConnectError, httpx.ConnectTimeout):
        # In-process fallback when HTTP server is not actively running
        try:
            import duckdb
            return duckdb.query(query).to_df()
        except Exception as exc:
            raise CompassXQueryError(f"Query execution failed: {exc}") from None
    except httpx.HTTPStatusError as exc:
        try:
            err_data = exc.response.json()
            msg = err_data.get("detail", err_data.get("message", str(exc)))
        except Exception:
            msg = exc.response.text or str(exc)
        raise CompassXQueryError(msg) from None
    except Exception as exc:
        raise CompassXQueryError(str(exc)) from None


    if data.get("status") == "error":
        raise CompassXQueryError(data.get("message", "Unknown query error"))

    if data.get("truncated"):
        print(f"Warning: Result truncated to {data.get('row_count')} rows.")

    rows = data.get("rows", [])
    raw_columns = data.get("columns", [])
    columns = [c["name"] if isinstance(c, dict) else c for c in raw_columns]
    return pd.DataFrame(rows, columns=columns)


def _serialize_dataframe(df: pd.DataFrame) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Convert a DataFrame into JSON-safe records and schema definitions."""
    records = []
    for _, row in df.iterrows():
        r = {}
        for col in df.columns:
            val = row[col]
            if pd.isna(val) or val is None:
                r[str(col)] = None
            elif isinstance(val, (pd.Timestamp, pd.Timedelta)):
                r[str(col)] = str(val)
            elif hasattr(val, "item") and callable(getattr(val, "item")):
                r[str(col)] = val.item()
            else:
                r[str(col)] = val
        records.append(r)


    schema_list = []
    for col, dtype in zip(df.columns, df.dtypes):
        if pd.api.types.is_integer_dtype(dtype):
            t = "int64"
        elif pd.api.types.is_float_dtype(dtype):
            t = "float64"
        elif pd.api.types.is_bool_dtype(dtype):
            t = "boolean"
        elif pd.api.types.is_datetime64_any_dtype(dtype):
            t = "timestamp"
        else:
            t = "string"
        schema_list.append({"name": str(col), "type": t})

    return records, schema_list


def write_table(
    df: pd.DataFrame,
    table_ref: str,
    *,
    mode: str = "overwrite",
    schema: dict[str, str] | list[dict[str, Any]] | None = None,
    description: str | None = None,
    timeout: int = 120,
) -> dict[str, Any]:
    """Write a DataFrame to a Catalog table (Iceberg or Postgres-native).

    Parameters:
        df: The pandas DataFrame to write.
        table_ref: 3-level or 2-level namespace (e.g. 'catalog.schema.table').
        mode: 'overwrite' (creates or replaces table) or 'append' (appends to existing table).
        schema: Optional explicit schema override dict or list of dicts.
        description: Optional table description for catalog registration and semantic search.
        timeout: Request timeout in seconds.

    Returns:
        Result dictionary containing status, table_ref, and rows_written count.

    Raises:
        CompassXSchemaError: If schema mismatch occurs on append.
        CompassXQueryError: If table write or API call fails.
    """
    if not isinstance(df, pd.DataFrame):
        df = pd.DataFrame(df)

    table_ref = table_ref.strip()
    if not table_ref:
        raise ValueError("table_ref cannot be empty")

    mode = mode.lower().strip()
    if mode not in {"overwrite", "replace", "append"}:
        raise ValueError("mode must be 'overwrite' or 'append'")

    token, api_url, headers = _get_auth_and_url()

    records, inferred_schema = _serialize_dataframe(df)

    # Format schema list if provided
    schema_list = None
    if schema:
        if isinstance(schema, dict):
            schema_list = [{"name": str(k), "type": str(v)} for k, v in schema.items()]
        elif isinstance(schema, list):
            schema_list = schema
    else:
        schema_list = inferred_schema

    if mode in ("overwrite", "replace"):
        url = f"{api_url}/table/create"
        payload = {
            "table_ref": table_ref,
            "schema": schema_list,
            "data": records,
            "mode": "overwrite",
            "description": description,
        }
    else:
        url = f"{api_url}/table/write"
        payload = {
            "table_ref": table_ref,
            "data": records,
            "schema": schema_list,
            "mode": "append",
        }

    try:
        resp = httpx.post(url, headers=headers, json=payload, timeout=timeout + 5)
        resp.raise_for_status()
        return resp.json()
    except (httpx.ConnectError, httpx.ConnectTimeout):
        # Fallback to direct in-process route execution if running in local offline runtime
        try:
            import asyncio
            from app.database import AccountSessionLocal
            from app.catalog.schemas import NotebookTableCreateRequest, NotebookTableWriteRequest, NotebookTableColumnDef
            from app.catalog.routes import create_table_from_notebook, write_table_from_notebook
            from unittest.mock import MagicMock

            mock_request = MagicMock()
            user = {"id": "system", "email": "system@compassx.internal"}
            with AccountSessionLocal() as db:
                if mode in ("overwrite", "replace"):
                    schema_defs = [NotebookTableColumnDef(**c) for c in (schema_list or [])] if schema_list else None
                    req = NotebookTableCreateRequest(
                        table_ref=table_ref,
                        schema=schema_defs,
                        data=records,
                        mode="overwrite",
                        description=description,
                    )
                    try:
                        loop = asyncio.get_event_loop()
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                    if loop.is_running():
                        import nest_asyncio
                        nest_asyncio.apply()
                        return loop.run_until_complete(create_table_from_notebook(mock_request, req, db=db, user=user))
                    else:
                        return loop.run_until_complete(create_table_from_notebook(mock_request, req, db=db, user=user))
                else:
                    schema_defs = [NotebookTableColumnDef(**c) for c in (schema_list or [])] if schema_list else None
                    req = NotebookTableWriteRequest(
                        table_ref=table_ref,
                        data=records,
                        schema=schema_defs,
                        mode="append",
                    )
                    try:
                        loop = asyncio.get_event_loop()
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                    if loop.is_running():
                        import nest_asyncio
                        nest_asyncio.apply()
                        return loop.run_until_complete(write_table_from_notebook(mock_request, req, db=db, user=user))
                    else:
                        return loop.run_until_complete(write_table_from_notebook(mock_request, req, db=db, user=user))
        except Exception as inner_exc:
            raise CompassXQueryError(f"Local table write failed: {inner_exc}") from None
    except httpx.HTTPStatusError as exc:
        try:
            err_data = exc.response.json()
            err_type = err_data.get("error_type")
            msg = err_data.get("message") or err_data.get("detail") or str(exc)
            if exc.response.status_code == 422 or err_type == "schema_mismatch":
                raise CompassXSchemaError(msg, details=err_data.get("details"))
        except CompassXSchemaError:
            raise
        except Exception:
            msg = exc.response.text or str(exc)
        raise CompassXQueryError(msg) from None
    except Exception as exc:
        raise CompassXQueryError(str(exc)) from None


write = write_table

# Bind helper method directly onto pandas DataFrame
try:
    pd.DataFrame.write_table = lambda self, table_ref, mode="overwrite", schema=None, description=None, timeout=120: write_table(
        self, table_ref, mode=mode, schema=schema, description=description, timeout=timeout
    )
except Exception:
    pass
