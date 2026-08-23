from __future__ import annotations

import json
import uuid
import asyncio
import logging
from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from app.nova.services.tooling import BaseNovaTool, NovaToolResult
from app.database import AccountSessionLocal
from app.catalog.models import UnifiedCatalogNotebook, UnifiedCatalogSchema
from app.catalog.service import _read_notebook_content, _write_notebook_content
from services.storage.config import storage_settings
from services.storage.fs import get_fs
from services.enterprise_gateway.config import eg_settings

logger = logging.getLogger(__name__)


_NOTEBOOKS_BUCKET = storage_settings.STORAGE_NOTEBOOKS_BUCKET
_NOTEBOOKS_PREFIX = storage_settings.STORAGE_NOTEBOOKS_PREFIX.strip("/")


def _notebook_storage_key(path: str) -> str:
    clean = path.replace("\\", "/").lstrip("/")
    if not clean.endswith(".ipynb"):
        raise ValueError("Only .ipynb files are supported")
    if ".." in clean.split("/"):
        raise ValueError("Invalid notebook path")
    return f"{_NOTEBOOKS_PREFIX}/{clean}" if _NOTEBOOKS_PREFIX else clean


def _join_source(source: Any) -> str:
    if isinstance(source, list):
        return "".join(str(part) for part in source)
    return str(source or "")


def _compact_outputs(outputs: Any) -> list[dict[str, Any]]:
    if not isinstance(outputs, list):
        return []
    compact: list[dict[str, Any]] = []
    for output in outputs:
        if not isinstance(output, dict):
            continue
        item = {
            "output_type": output.get("output_type"),
            "execution_count": output.get("execution_count"),
        }
        if "name" in output:
            item["name"] = output.get("name")
        if "text" in output:
            text = output.get("text")
            item["text"] = "".join(text) if isinstance(text, list) else text
        if "data" in output:
            item["data"] = output.get("data")
        if "ename" in output or "evalue" in output:
            item["ename"] = output.get("ename")
            item["evalue"] = output.get("evalue")
            item["traceback"] = output.get("traceback", [])
        compact.append(item)
    return compact


def _notebook_context(context: dict[str, Any]) -> dict[str, Any]:
    notebook = context.get("notebook")
    return notebook if isinstance(notebook, dict) else context


def _context_cells(context: dict[str, Any]) -> list[Any]:
    notebook_context = _notebook_context(context)
    cells = notebook_context.get("cells") or notebook_context.get("cell_states") or []
    return cells if isinstance(cells, list) else []


def _context_cell_at(context: dict[str, Any], cell_index: int) -> dict[str, Any] | None:
    if cell_index < 0:
        return None
    cells = _context_cells(context)
    if not cells:
        nb_data = _load_persisted_notebook(context)
        if nb_data and isinstance(nb_data.get("cells"), list):
            cells = [
                {
                    "cell_type": c.get("cell_type", "code"),
                    "source": _join_source(c.get("source", "")),
                    "outputs": c.get("outputs", []),
                    "metadata": c.get("metadata", {}),
                    "index": idx,
                }
                for idx, c in enumerate(nb_data["cells"])
                if isinstance(c, dict)
            ]

    for position, cell in enumerate(cells):
        if not isinstance(cell, dict):
            continue
        raw_index = cell.get("index", cell.get("cell_index", position))
        try:
            if int(raw_index) == cell_index:
                return cell
        except (TypeError, ValueError):
            continue
    return None


def _resolve_notebook_path(context: dict[str, Any]) -> str | None:
    notebook_context = _notebook_context(context)
    path = (
        notebook_context.get("notebook_id")
        or notebook_context.get("notebook_path")
        or notebook_context.get("path")
        or context.get("notebook_id")
        or context.get("notebook_path")
        or context.get("path")
    )
    return str(path) if path else None


async def _load_notebook_record(account_db, path: str):
    try:
        clean = path.replace("\\", "/").strip()
        stripped = clean[10:] if clean.startswith("notebooks/") else clean

        dot_parts = clean.split(".")
        if len(dot_parts) == 3 and not clean.endswith(".ipynb"):
            notebook = account_db.query(UnifiedCatalogNotebook).filter(
                UnifiedCatalogNotebook.catalog_name == dot_parts[0],
                UnifiedCatalogNotebook.schema_name == dot_parts[1],
                UnifiedCatalogNotebook.name == dot_parts[2],
            ).first()
            if notebook:
                return notebook

        slash_parts = clean.rstrip("/").split("/")
        if len(slash_parts) == 3:
            nb_name = slash_parts[2]
            if nb_name.endswith(".ipynb"):
                nb_name = nb_name[:-6]
            notebook = account_db.query(UnifiedCatalogNotebook).filter(
                UnifiedCatalogNotebook.catalog_name == slash_parts[0],
                UnifiedCatalogNotebook.schema_name == slash_parts[1],
                UnifiedCatalogNotebook.name == nb_name,
            ).first()
            if notebook:
                return notebook

        return account_db.query(UnifiedCatalogNotebook).filter(
            (UnifiedCatalogNotebook.id == clean) |
            (UnifiedCatalogNotebook.id == stripped) |
            (UnifiedCatalogNotebook.blob_path == clean) |
            (UnifiedCatalogNotebook.blob_path == stripped) |
            (UnifiedCatalogNotebook.name == clean) |
            (UnifiedCatalogNotebook.name == stripped)
        ).first()
    except SQLAlchemyError as exc:
        logger.warning("Notebook catalog lookup failed for %s, falling back to storage: %s", path, exc)
        return None


def _persist_notebook_edit(context: dict[str, Any], notebook_data: dict[str, Any]) -> None:
    path = _resolve_notebook_path(context)
    if not path:
        return

    account_db = AccountSessionLocal()
    try:
        notebook = run_async(_load_notebook_record(account_db, path))
        if notebook:
            schema = account_db.query(UnifiedCatalogSchema).filter(
                UnifiedCatalogSchema.id == notebook.schema_id
            ).first()
            if schema:
                run_async(_write_notebook_content(account_db, schema, notebook.blob_path, notebook_data))
                return
    finally:
        account_db.close()

    try:
        key = _notebook_storage_key(path)
    except ValueError:
        return
    fs = get_fs()
    fs.write_text(_NOTEBOOKS_BUCKET, key, json.dumps(notebook_data, indent=2))


def _load_persisted_notebook(context: dict[str, Any]) -> dict[str, Any] | None:
    path = _resolve_notebook_path(context)
    if not path:
        return None

    account_db = AccountSessionLocal()
    try:
        notebook = run_async(_load_notebook_record(account_db, path))
        if notebook:
            schema = account_db.query(UnifiedCatalogSchema).filter(
                UnifiedCatalogSchema.id == notebook.schema_id
            ).first()
            if schema:
                return run_async(_read_notebook_content(account_db, schema, notebook.blob_path))
    finally:
        account_db.close()

    try:
        key = _notebook_storage_key(path)
    except ValueError:
        return None
    fs = get_fs()
    if not fs.exists(_NOTEBOOKS_BUCKET, key):
        return None
    return json.loads(fs.read_text(_NOTEBOOKS_BUCKET, key))


class GetCellOutputTool(BaseNovaTool):
    key = "get_cell_output"
    description = "Fetch the current captured output for a notebook cell."
    input_schema = {
        "type": "object",
        "properties": {"cell_index": {"type": "integer", "minimum": 0}},
        "required": ["cell_index"],
    }

    def execute(self, arguments: dict[str, Any], context: dict[str, Any]) -> NovaToolResult:
        index = int(arguments["cell_index"])
        cell = _context_cell_at(context, index)
        if cell is not None:
            return NovaToolResult(ok=True, result={"cell_index": index, "output": cell.get("output")})
        return NovaToolResult(ok=False, error=f"Cell {index} not found")


class GetVariableStateTool(BaseNovaTool):
    key = "get_variable_state"
    description = "Fetch variable state captured for a notebook cell."
    input_schema = {
        "type": "object",
        "properties": {
            "cell_index": {"type": "integer", "minimum": 0},
            "variable_name": {"type": "string"},
        },
        "required": ["cell_index", "variable_name"],
    }

    def execute(self, arguments: dict[str, Any], context: dict[str, Any]) -> NovaToolResult:
        notebook_context = _notebook_context(context)
        variables = notebook_context.get("variable_state", {}).get(str(int(arguments["cell_index"])), {})
        name = arguments["variable_name"]
        return NovaToolResult(ok=True, result={"variable_name": name, "value": variables.get(name)})


class GetSchemaTool(BaseNovaTool):
    key = "get_schema"
    description = "Fetch schema metadata already attached to the notebook request."
    input_schema = {
        "type": "object",
        "properties": {"table_or_view_name": {"type": "string"}},
        "required": ["table_or_view_name"],
    }

    def execute(self, arguments: dict[str, Any], context: dict[str, Any]) -> NovaToolResult:
        name = arguments["table_or_view_name"]
        schema_hints = _notebook_context(context).get("schema_hints", {})
        return NovaToolResult(ok=True, result={"table_or_view_name": name, "schema": schema_hints.get(name)})


class ListImportsTool(BaseNovaTool):
    key = "list_imports"
    description = "List imports already present in the notebook."
    input_schema = {"type": "object", "properties": {}}

    def execute(self, arguments: dict[str, Any], context: dict[str, Any]) -> NovaToolResult:
        return NovaToolResult(ok=True, result={"imports": _notebook_context(context).get("imports", [])})


class ReadNotebookTool(BaseNovaTool):
    key = "read_notebook"
    description = (
        "Read another notebook by relative .ipynb path so Nova or an agent can inspect reference code. "
        "Returns notebook metadata and indexed cells. Outputs are omitted unless include_outputs is true."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "notebook_path": {
                "type": "string",
                "description": "Relative notebook path, for example notebooks/analysis.ipynb or analysis.ipynb.",
            },
            "include_outputs": {
                "type": "boolean",
                "description": "Whether to include compact cell outputs in the response.",
                "default": False,
            },
            "max_cells": {
                "type": "integer",
                "minimum": 1,
                "maximum": 200,
                "description": "Maximum number of cells to return.",
                "default": 80,
            },
        },
        "required": ["notebook_path"],
    }

    def execute(self, arguments: dict[str, Any], context: dict[str, Any]) -> NovaToolResult:
        path = str(arguments["notebook_path"])
        include_outputs = bool(arguments.get("include_outputs", False))
        max_cells = min(max(int(arguments.get("max_cells", 80)), 1), 200)

        # 1. Try to resolve via UnifiedCatalogNotebook database
        from app.database import AccountSessionLocal
        from app.catalog.models import UnifiedCatalogSchema
        from app.catalog.service import _read_notebook_content

        account_db = AccountSessionLocal()
        db_notebook = None
        try:
            db_notebook = run_async(_load_notebook_record(account_db, path))
            if not db_notebook and context.get("notebook_id"):
                db_notebook = run_async(_load_notebook_record(account_db, str(context["notebook_id"])))

            if db_notebook:
                schema = account_db.query(UnifiedCatalogSchema).filter(
                    UnifiedCatalogSchema.id == db_notebook.schema_id
                ).first()
                if schema:
                    notebook_content = run_async(_read_notebook_content(account_db, schema, db_notebook.blob_path))
                else:
                    notebook_content = None
            else:
                notebook_content = None
        except Exception as e:
            logger.warning("Failed to resolve notebook from catalog metadata db: %s", e)
            notebook_content = None
        finally:
            account_db.close()

        # 2. Fallback to reading directly from storage bucket if not resolved in catalog DB
        if notebook_content is None:
            try:
                key = _notebook_storage_key(path)
            except ValueError as exc:
                return NovaToolResult(ok=False, error=str(exc))

            fs = get_fs()
            if not fs.exists(_NOTEBOOKS_BUCKET, key):
                return NovaToolResult(ok=False, error=f"Notebook not found: {path}")

            try:
                notebook_content = json.loads(fs.read_text(_NOTEBOOKS_BUCKET, key))
            except json.JSONDecodeError as exc:
                return NovaToolResult(ok=False, error=f"Notebook is not valid JSON: {exc}")

        raw_cells = notebook_content.get("cells", [])
        if not isinstance(raw_cells, list):
            return NovaToolResult(ok=False, error="Notebook cells must be a list")

        cells = []
        for index, cell in enumerate(raw_cells[:max_cells]):
            if not isinstance(cell, dict):
                continue
            item = {
                "index": index,
                "cell_type": cell.get("cell_type", "code"),
                "source": _join_source(cell.get("source", [])),
                "metadata": cell.get("metadata", {}),
            }
            if include_outputs:
                item["outputs"] = _compact_outputs(cell.get("outputs", []))
            cells.append(item)

        return NovaToolResult(
            ok=True,
            result={
                "notebook_path": path,
                "cell_count": len(raw_cells),
                "returned_cell_count": len(cells),
                "truncated": len(raw_cells) > max_cells,
                "metadata": notebook_content.get("metadata", {}),
                "cells": cells,
            },
        )


class ExecuteCellTool(BaseNovaTool):
    key = "execute_cell"
    description = "Record that Nova wants a notebook cell execution. This backend does not execute the cell directly."
    input_schema = {
        "type": "object",
        "properties": {"cell_index": {"type": "integer", "minimum": 0}},
        "required": ["cell_index"],
    }

    def execute(self, arguments: dict[str, Any], context: dict[str, Any]) -> NovaToolResult:
        return NovaToolResult(
            ok=True,
            result={
                "cell_index": int(arguments["cell_index"]),
                "status": "execution_requested",
                "message": "Frontend or notebook runtime should execute this cell.",
            },
        )


class EditCellTool(BaseNovaTool):
    key = "edit_cell"
    description = "Propose replacing the source of one existing notebook cell by index. The UI must request user approval before committing it."
    input_schema = {
        "type": "object",
        "properties": {
            "cell_index": {
                "type": "integer",
                "minimum": 0,
                "description": "Zero-based index of the existing notebook cell to edit.",
            },
            "cell_type": {
                "type": "string",
                "enum": ["code", "markdown", "raw"],
                "default": "code",
            },
            "code": {"type": "string"},
            "explanation": {"type": "string"},
        },
        "required": ["cell_index", "code"],
    }

    def execute(self, arguments: dict[str, Any], context: dict[str, Any]) -> NovaToolResult:
        cell_index = int(arguments["cell_index"])

        notebook_data = _load_persisted_notebook(context) or {"nbformat": 4, "nbformat_minor": 5, "metadata": {}, "cells": []}
        cells_data = notebook_data.get("cells") if isinstance(notebook_data.get("cells"), list) else []
        if cell_index >= len(cells_data):
            return NovaToolResult(ok=False, error=f"Cell {cell_index} not found")

        persisted_cell = cells_data[cell_index] if isinstance(cells_data[cell_index], dict) else {}
        context_cell = _context_cell_at(context, cell_index)
        cell_type = str(arguments.get("cell_type") or (context_cell or {}).get("cell_type") or persisted_cell.get("cell_type") or "code")
        if cell_type not in {"code", "markdown", "raw"}:
            return NovaToolResult(ok=False, error="cell_type must be code, markdown, or raw")

        result = NovaToolResult(
            ok=True,
            result={
                "action": "replace_cell",
                "cell_index": cell_index,
                "cell_type": cell_type,
                "code": str(arguments["code"]),
                "explanation": str(arguments.get("explanation") or ""),
                "requires_approval": False,
            },
        )
        cells_data[cell_index] = {
            **(cells_data[cell_index] if isinstance(cells_data[cell_index], dict) else {}),
            "cell_type": cell_type,
            "source": [str(arguments["code"])],
            "metadata": (cells_data[cell_index].get("metadata", {}) if isinstance(cells_data[cell_index], dict) else {}),
        }
        notebook_data["cells"] = cells_data
        _persist_notebook_edit(context, notebook_data)
        return result


class AddMultipleCellsTool(BaseNovaTool):
    key = "add_multiple_cells"
    description = (
        "Propose adding multiple notebook cells in one operation. The UI must request user approval "
        "for each proposed cell before committing it."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "insert_after_cell_index": {
                "type": ["integer", "null"],
                "minimum": -1,
                "description": (
                    "Zero-based cell index after which to insert the new cells. Null appends to the notebook. "
                    "Use -1 to insert at the beginning of an empty notebook."
                ),
            },
            "cells": {
                "type": "array",
                "minItems": 1,
                "maxItems": 20,
                "items": {
                    "type": "object",
                    "properties": {
                        "cell_type": {
                            "type": "string",
                            "enum": ["code", "markdown", "raw"],
                            "default": "code",
                        },
                        "code": {"type": "string"},
                        "explanation": {"type": "string"},
                    },
                    "required": ["code"],
                    "additionalProperties": False,
                },
            },
            "explanation": {"type": "string"},
        },
        "required": ["cells"],
    }

    def execute(self, arguments: dict[str, Any], context: dict[str, Any]) -> NovaToolResult:
        cells = arguments.get("cells")
        if not isinstance(cells, list) or not cells:
            return NovaToolResult(ok=False, error="cells must be a non-empty list")
        if len(cells) > 20:
            return NovaToolResult(ok=False, error="A maximum of 20 cells can be added at once")

        insert_after_cell_index = arguments.get("insert_after_cell_index")
        if insert_after_cell_index is not None:
            insert_after_cell_index = int(insert_after_cell_index)
            if insert_after_cell_index == -1:
                insert_after_cell_index = None
            else:
                context_cells = _context_cells(context)
                if not context_cells:
                    # Fall back to persisted notebook cell count
                    nb = _load_persisted_notebook(context)
                    nb_cells = nb.get("cells", []) if nb and isinstance(nb.get("cells"), list) else []
                    if insert_after_cell_index >= len(nb_cells):
                        return NovaToolResult(ok=False, error=f"Cell {insert_after_cell_index} not found")
                elif _context_cell_at(context, insert_after_cell_index) is None:
                    return NovaToolResult(ok=False, error=f"Cell {insert_after_cell_index} not found")

        normalized_cells = []
        for index, cell in enumerate(cells):
            if not isinstance(cell, dict):
                return NovaToolResult(ok=False, error=f"cells[{index}] must be an object")
            cell_type = str(cell.get("cell_type") or "code")
            if cell_type not in {"code", "markdown", "raw"}:
                return NovaToolResult(ok=False, error=f"cells[{index}].cell_type must be code, markdown, or raw")
            normalized_cells.append(
                {
                    "cell_type": cell_type,
                    "code": str(cell.get("code") or ""),
                    "explanation": str(cell.get("explanation") or ""),
                }
            )

        result = NovaToolResult(
            ok=True,
            result={
                "action": "add_cells",
                "insert_after_cell_index": insert_after_cell_index,
                "cells": normalized_cells,
                "explanation": str(arguments.get("explanation") or ""),
                "requires_approval": False,
            },
        )
        notebook_data = _load_persisted_notebook(context) or {"nbformat": 4, "nbformat_minor": 5, "metadata": {}, "cells": []}
        existing_cells = notebook_data.get("cells") if isinstance(notebook_data.get("cells"), list) else []
        new_cells = [{"cell_type": c["cell_type"], "source": [c["code"]], "metadata": {}} for c in normalized_cells]
        if insert_after_cell_index is None or not existing_cells:
            notebook_data["cells"] = existing_cells + new_cells
        else:
            insertion_index = min(insert_after_cell_index + 1, len(existing_cells))
            notebook_data["cells"] = existing_cells[:insertion_index] + new_cells + existing_cells[insertion_index:]
        _persist_notebook_edit(context, notebook_data)
        return result


NOTEBOOK_NOVA_TOOLS: list[BaseNovaTool] = [
    GetCellOutputTool(),
    GetVariableStateTool(),
    GetSchemaTool(),
    ListImportsTool(),
    ReadNotebookTool(),
    EditCellTool(),
    AddMultipleCellsTool(),
]


def run_async(coro):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    if loop.is_running():
        import threading
        from concurrent.futures import Future

        future = Future()

        def _run():
            try:
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                result = new_loop.run_until_complete(coro)
                future.set_result(result)
            except Exception as e:
                future.set_exception(e)
            finally:
                new_loop.close()

        t = threading.Thread(target=_run)
        t.start()
        return future.result()
    else:
        return loop.run_until_complete(coro)


async def execute_code_on_kernel(kernel_id: str, code: str) -> list[dict[str, Any]]:
    upstream_ws_url = eg_settings.internal_url().replace("http://", "ws://").replace("https://", "wss://")
    ws_url = f"{upstream_ws_url}/api/kernels/{kernel_id}/channels"
    
    msg_id = uuid.uuid4().hex
    session_id = uuid.uuid4().hex
    
    execute_msg = {
        "header": {
            "msg_id": msg_id,
            "username": "nova",
            "session": session_id,
            "msg_type": "execute_request",
            "version": "5.3",
        },
        "parent_header": {},
        "metadata": {},
        "content": {
            "code": code,
            "silent": False,
            "store_history": True,
            "user_expressions": {},
            "allow_stdin": False,
            "stop_on_error": True,
        },
        "channel": "shell",
    }
    
    outputs = []
    import websockets
    
    async with websockets.connect(ws_url, open_timeout=10) as ws:
        await ws.send(json.dumps(execute_msg))
        
        received_reply = False
        kernel_idle = False
        
        while not (received_reply and kernel_idle):
            try:
                raw_msg = await asyncio.wait_for(ws.recv(), timeout=30.0)
                msg = json.loads(raw_msg)
                
                msg_type = msg.get("header", {}).get("msg_type")
                parent_msg_id = msg.get("parent_header", {}).get("msg_id")
                
                if parent_msg_id != msg_id:
                    continue
                
                content = msg.get("content", {})
                
                if msg_type == "status":
                    if content.get("execution_state") == "idle":
                        kernel_idle = True
                elif msg_type == "execute_reply":
                    received_reply = True
                elif msg_type == "stream":
                    outputs.append({
                        "output_type": "stream",
                        "name": content.get("name", "stdout"),
                        "text": content.get("text", ""),
                    })
                elif msg_type in ("execute_result", "display_data"):
                    outputs.append({
                        "output_type": msg_type,
                        "data": content.get("data", {}),
                        "metadata": content.get("metadata", {}),
                        "execution_count": content.get("execution_count"),
                    })
                elif msg_type == "error":
                    outputs.append({
                        "output_type": "error",
                        "ename": content.get("ename", ""),
                        "evalue": content.get("evalue", ""),
                        "traceback": content.get("traceback", []),
                    })
            except asyncio.TimeoutError:
                break
                
    return outputs


class ProposeCellEditTool(BaseNovaTool):
    key = "propose_cell_edit"
    description = "Propose replacing or updating the source of an existing notebook cell."
    input_schema = {
        "type": "object",
        "properties": {
            "cell_index": {
                "type": "integer",
                "minimum": 0,
                "description": "Zero-based index of the cell to edit.",
            },
            "cell_type": {
                "type": "string",
                "enum": ["code", "markdown", "raw"],
                "default": "code",
            },
            "code": {"type": "string", "description": "The proposed new source code or markdown."},
            "explanation": {"type": "string", "description": "Explanation for the proposed edit."},
        },
        "required": ["cell_index", "code"],
    }

    def execute(self, arguments: dict[str, Any], context: dict[str, Any]) -> NovaToolResult:
        cell_index = int(arguments["cell_index"])
        cell = _context_cell_at(context, cell_index)
        if cell is None:
            return NovaToolResult(ok=False, error=f"Cell {cell_index} not found")

        cell_type = str(arguments.get("cell_type") or cell.get("cell_type") or "code")
        if cell_type not in {"code", "markdown", "raw"}:
            return NovaToolResult(ok=False, error="cell_type must be code, markdown, or raw")

        result = NovaToolResult(
            ok=True,
            result={
                "action": "replace_cell",
                "cell_index": cell_index,
                "cell_type": cell_type,
                "code": str(arguments["code"]),
                "explanation": str(arguments.get("explanation") or ""),
                "requires_approval": False,
            },
        )
        return result


def _start_kernel_for_compute(resource_id: str, job_id: str, runtime: str, session_token: str) -> str:
    """Start an EG kernel for a compute resource and return the new kernel_id.

    Replicates the logic from compute/routes/router.py:start_kernel_for_resource.
    Returns kernel_id string on success, raises on failure.
    """
    import httpx
    from app.compute.routes.router import _kernel_catalog_api_url

    eg_url = eg_settings.internal_url()
    kernelspec_map = {
        "spark": "spark_python",
        "ray": "ray_python",
        "flink": "flink_python",
        "duckdb": "duckdb_python",
    }
    kernel_name = kernelspec_map.get(runtime, "duckdb_python")

    # Clean up stale kernels for this job
    try:
        existing = httpx.get(f"{eg_url}/api/kernels", timeout=10)
        if existing.is_success:
            for k in existing.json():
                env = (k.get("metadata") or {}).get("env") or {}
                if env.get("KERNEL_COMPASSX_JOB_ID") == job_id:
                    httpx.delete(f"{eg_url}/api/kernels/{k['id']}", timeout=10)
    except Exception:
        pass

    try:
        catalog_api_url = _kernel_catalog_api_url()
    except Exception:
        catalog_api_url = ""

    resp = httpx.post(
        f"{eg_url}/api/kernels",
        json={
            "name": kernel_name,
            "env": {
                "KERNEL_COMPASSX_JOB_ID": job_id,
                "KERNEL_RUNTIME": runtime,
                "KERNEL_CATALOG_API_URL": catalog_api_url,
                "KERNEL_NOTEBOOK_SESSION_TOKEN": session_token,
                "CATALOG_API_URL": catalog_api_url,
                "NOTEBOOK_SESSION_TOKEN": session_token,
            },
        },
        timeout=120.0,
    )
    resp.raise_for_status()
    return resp.json()["id"]


def _find_resource_id_by_name(resource_name: str) -> tuple[str, str, str] | None:
    """Look up a compute resource by name. Returns (resource_id, job_id, runtime) or None."""
    from app.database import SystemSessionLocal
    from app.compute.models.compute_resources import ComputeResource

    db = SystemSessionLocal()
    try:
        resource = db.query(ComputeResource).filter(
            ComputeResource.name == resource_name
        ).first()
        if resource:
            return resource.id, resource.id, resource.runtime
        return None
    finally:
        db.close()


def _persist_cell_execution_outputs(context: dict[str, Any], cell_index: int, outputs: list[dict[str, Any]]) -> None:
    notebook_data = _load_persisted_notebook(context)
    if not notebook_data or not isinstance(notebook_data.get("cells"), list):
        return

    cells = notebook_data["cells"]
    if 0 <= cell_index < len(cells) and isinstance(cells[cell_index], dict):
        target_cell = cells[cell_index]
        target_cell["outputs"] = outputs
        # Find max execution_count across cells to increment
        max_count = 0
        for c in cells:
            if isinstance(c, dict) and isinstance(c.get("execution_count"), int):
                max_count = max(max_count, c["execution_count"])
        target_cell["execution_count"] = max_count + 1
        _persist_notebook_edit(context, notebook_data)


class StartKernelAndRunCellTool(BaseNovaTool):
    key = "run_cell"
    description = (
        "Execute a notebook cell and return the outputs. "
        "This tool is BLOCKING — it waits until execution finishes before returning. "
        "If no kernel is currently connected, it will automatically start one using the "
        "notebook's last-connected compute resource (or the 'default' compute if none is stored). "
        "Returns outputs on success. Returns an error if kernel start or execution fails — "
        "do NOT fall back to frontend; report the failure to the user."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "cell_index": {"type": "integer", "minimum": 0},
        },
        "required": ["cell_index"],
    }

    def execute(self, arguments: dict[str, Any], context: dict[str, Any]) -> NovaToolResult:
        cell_index = int(arguments["cell_index"])
        cell = _context_cell_at(context, cell_index)
        if cell is None:
            return NovaToolResult(ok=False, error=f"Cell {cell_index} not found")

        code = cell.get("source", "")
        if cell.get("cell_status") == "pending" and cell.get("pending_source"):
            code = cell.get("pending_source")

        notebook_ctx = _notebook_context(context)
        kernel_id = notebook_ctx.get("kernel_id")

        # If kernel already connected, execute directly
        if kernel_id:
            try:
                outputs = run_async(execute_code_on_kernel(kernel_id, code))
                _persist_cell_execution_outputs(context, cell_index, outputs)
                return NovaToolResult(
                    ok=True,
                    result={"cell_index": cell_index, "status": "success", "outputs": outputs},
                )
            except Exception as exc:
                return NovaToolResult(
                    ok=False,
                    error=f"Cell execution failed on kernel {kernel_id}: {exc}",
                )

        # No kernel connected — find compute and start kernel
        notebook_id = notebook_ctx.get("notebook_id")
        resource_id = None
        job_id = None
        runtime = "duckdb"

        # Try last-connected compute from DB
        if notebook_id:
            try:
                from app.database import SystemSessionLocal
                account_db = AccountSessionLocal()
                try:
                    from app.catalog.models import UnifiedCatalogNotebook
                    nb = account_db.query(UnifiedCatalogNotebook).filter(
                        UnifiedCatalogNotebook.id == notebook_id
                    ).first()
                    last_resource_id = nb.last_compute_resource_id if nb else None
                finally:
                    account_db.close()
                if last_resource_id:
                    system_db = SystemSessionLocal()
                    try:
                        from app.compute.models.compute_resources import ComputeResource
                        cr = system_db.query(ComputeResource).filter(
                            ComputeResource.id == last_resource_id
                        ).first()
                        if cr:
                            resource_id = cr.id
                            job_id = cr.id
                            runtime = cr.runtime
                    finally:
                        system_db.close()
            except Exception as exc:
                logger.warning("Could not look up last compute for notebook %s: %s", notebook_id, exc)

        # Fall back to "default" compute if no resource found
        if not resource_id:
            result = _find_resource_id_by_name("default")
            if result:
                resource_id, job_id, runtime = result

        if not resource_id:
            return NovaToolResult(
                ok=False,
                error=(
                    "Cell execution failed: no kernel is connected and no compute resource is available. "
                    "Please open the notebook, connect a compute resource, and try again."
                ),
            )

        # Start kernel on the compute resource
        session_token = context.get("session_token", "")
        try:
            new_kernel_id = _start_kernel_for_compute(resource_id, job_id, runtime, session_token)
        except Exception as exc:
            return NovaToolResult(
                ok=False,
                error=f"Cell execution failed: could not start kernel on compute resource '{resource_id}': {exc}",
            )

        # Execute on the newly started kernel
        try:
            outputs = run_async(execute_code_on_kernel(new_kernel_id, code))
            _persist_cell_execution_outputs(context, cell_index, outputs)
            return NovaToolResult(
                ok=True,
                result={"cell_index": cell_index, "status": "success", "outputs": outputs},
            )
        except Exception as exc:
            return NovaToolResult(
                ok=False,
                error=f"Cell execution failed after kernel start: {exc}",
            )


class ApproveCellEditTool(BaseNovaTool):
    key = "approve_cell_edit"
    description = "Approve and commit a pending cell edit."
    input_schema = {
        "type": "object",
        "properties": {
            "cell_index": {"type": "integer", "minimum": 0},
        },
        "required": ["cell_index"],
    }

    def execute(self, arguments: dict[str, Any], context: dict[str, Any]) -> NovaToolResult:
        return NovaToolResult(
            ok=True,
            result={
                "cell_index": int(arguments["cell_index"]),
                "status": "approved",
            },
        )


class RejectCellEditTool(BaseNovaTool):
    key = "reject_cell_edit"
    description = "Reject and discard a pending cell edit, reverting to original code."
    input_schema = {
        "type": "object",
        "properties": {
            "cell_index": {"type": "integer", "minimum": 0},
        },
        "required": ["cell_index"],
    }

    def execute(self, arguments: dict[str, Any], context: dict[str, Any]) -> NovaToolResult:
        return NovaToolResult(
            ok=True,
            result={
                "cell_index": int(arguments["cell_index"]),
                "status": "rejected",
            },
        )


class GetCellStateTool(BaseNovaTool):
    key = "get_cell_state"
    description = "Get the state of a notebook cell, including committed source, pending source, status, and outputs."
    input_schema = {
        "type": "object",
        "properties": {
            "cell_index": {"type": "integer", "minimum": 0},
        },
        "required": ["cell_index"],
    }

    def execute(self, arguments: dict[str, Any], context: dict[str, Any]) -> NovaToolResult:
        index = int(arguments["cell_index"])
        cell = _context_cell_at(context, index)
        if cell is None:
            return NovaToolResult(ok=False, error=f"Cell {index} not found")

        return NovaToolResult(
            ok=True,
            result={
                "cell_index": index,
                "cell_type": cell.get("cell_type", "code"),
                "source": cell.get("source", ""),
                "committed_source": cell.get("committed_source"),
                "pending_source": cell.get("pending_source"),
                "cell_status": cell.get("cell_status", "clean"),
                "output": cell.get("output", []),
            },
        )


NOTEBOOK_NOVA_TOOLS.extend([
    ProposeCellEditTool(),
    StartKernelAndRunCellTool(),
    ApproveCellEditTool(),
    RejectCellEditTool(),
    GetCellStateTool(),
])
