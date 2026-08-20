"""Service layer for Catalog Tools and Tool Promotion."""

from __future__ import annotations

import ast
import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from app.catalog.models import UnifiedCatalog, UnifiedCatalogSchema, UnifiedCatalogTool, UnifiedCatalogToolVersion
from app.catalog.tool_schemas import ToolPromoteRequest

logger = logging.getLogger(__name__)


def parse_tool_code_metadata(source_code: str) -> Tuple[str, Optional[str], List[str], Dict[str, Any]]:
    """Parse python code using AST to extract tool name, description, connections, and param schema."""
    parsed_name = ""
    parsed_desc = None
    parsed_conns: List[str] = []
    parsed_params: Dict[str, Any] = {"type": "object", "properties": {}, "required": []}

    try:
        tree = ast.parse(source_code)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                parsed_name = node.name
                docstring = ast.get_docstring(node)
                if docstring:
                    parsed_desc = docstring.strip()

                # Inspect decorators
                for dec in node.decorator_list:
                    call_node = dec if isinstance(dec, ast.Call) else None
                    if call_node:
                        # Extract keyword args
                        for kw in call_node.keywords:
                            if kw.arg == "name" and isinstance(kw.value, ast.Constant):
                                parsed_name = str(kw.value.value)
                            elif kw.arg == "description" and isinstance(kw.value, ast.Constant):
                                parsed_desc = str(kw.value.value)
                            elif kw.arg == "connections" and isinstance(kw.value, ast.List):
                                parsed_conns = [
                                    elt.value for elt in kw.value.elts if isinstance(elt, ast.Constant)
                                ]

                # Infer parameters schema from function arguments
                props = {}
                reqs = []
                for arg in node.args.args:
                    if arg.arg in ("self", "cls"):
                        continue
                    prop_type = "string"
                    if arg.annotation:
                        if isinstance(arg.annotation, ast.Name):
                            ann_id = arg.annotation.id.lower()
                            if ann_id in ("int", "integer"):
                                prop_type = "integer"
                            elif ann_id in ("float", "number"):
                                prop_type = "number"
                            elif ann_id in ("bool", "boolean"):
                                prop_type = "boolean"
                            elif ann_id in ("dict", "mapping"):
                                prop_type = "object"
                            elif ann_id in ("list", "sequence"):
                                prop_type = "array"
                    props[arg.arg] = {"type": prop_type}
                    reqs.append(arg.arg)

                parsed_params = {"type": "object", "properties": props, "required": reqs}
                break
    except Exception as exc:
        logger.warning("Could not parse AST from tool source code: %s", exc)

    return parsed_name, parsed_desc, parsed_conns, parsed_params


def _ensure_catalog_and_schema(db: Session, catalog_name: str, schema_name: str, user_id: str) -> UnifiedCatalogSchema:
    """Ensure catalog and schema rows exist."""
    cat = db.query(UnifiedCatalog).filter(UnifiedCatalog.name == catalog_name).first()
    if not cat:
        cat = UnifiedCatalog(
            id=str(uuid.uuid4()),
            name=catalog_name,
            description=f"Auto-created catalog for {catalog_name}",
            created_by=user_id,
        )
        db.add(cat)
        db.flush()

    sch = (
        db.query(UnifiedCatalogSchema)
        .filter(
            UnifiedCatalogSchema.catalog_id == cat.id,
            UnifiedCatalogSchema.name == schema_name,
        )
        .first()
    )
    if not sch:
        sch = UnifiedCatalogSchema(
            id=str(uuid.uuid4()),
            catalog_id=cat.id,
            name=schema_name,
            description=f"Auto-created schema for {schema_name}",
            created_by=user_id,
        )
        db.add(sch)
        db.flush()

    return sch


def promote_tool(
    db: Session,
    payload: ToolPromoteRequest,
    user_id: str = "default_user",
) -> UnifiedCatalogTool:
    """Promote a function to a versioned catalog tool."""
    # 1. Parse code metadata if not supplied
    ast_name, ast_desc, ast_conns, ast_params = parse_tool_code_metadata(payload.source_code)

    tool_name = payload.name or ast_name or "unnamed_tool"
    description = payload.description or ast_desc or f"Promoted tool {tool_name}"
    connections = (
        payload.connection_dependencies
        if payload.connection_dependencies is not None
        else ast_conns
    )
    param_schema = (
        payload.param_schema
        if payload.param_schema is not None
        else ast_params
    )

    nb_id = (
        payload.source_notebook_object_id
        or getattr(payload, "notebook", None)
        or getattr(payload, "notebook_path", None)
        or getattr(payload, "source_notebook_id", None)
    )

    # 2. Ensure schema exists
    schema_obj = _ensure_catalog_and_schema(db, payload.catalog, payload.schema_name, user_id)

    # 3. Check for existing tool
    existing_tool = (
        db.query(UnifiedCatalogTool)
        .filter(
            UnifiedCatalogTool.catalog_name == payload.catalog,
            UnifiedCatalogTool.schema_name == payload.schema_name,
            UnifiedCatalogTool.name == tool_name,
        )
        .first()
    )

    if existing_tool:
        # Re-promotion: increment current_version and append version row
        new_version_num = existing_tool.current_version + 1
        existing_tool.current_version = new_version_num
        existing_tool.source_code = payload.source_code
        existing_tool.param_schema = param_schema
        existing_tool.description = description
        existing_tool.connection_dependencies = connections
        existing_tool.source_notebook_object_id = nb_id or existing_tool.source_notebook_object_id
        existing_tool.updated_by = user_id

        version_row = UnifiedCatalogToolVersion(
            id=str(uuid.uuid4()),
            tool_id=existing_tool.id,
            version=new_version_num,
            source_notebook_object_id=nb_id,
            source_code=payload.source_code,
            param_schema=param_schema,
            connection_dependencies=connections,
            promoted_by=user_id,
        )
        db.add(version_row)
        db.commit()
        db.refresh(existing_tool)
        return existing_tool
    else:
        # Initial promotion
        tool_id = str(uuid.uuid4())
        tool_obj = UnifiedCatalogTool(
            id=tool_id,
            schema_id=schema_obj.id,
            catalog_name=payload.catalog,
            schema_name=payload.schema_name,
            name=tool_name,
            source_notebook_object_id=nb_id,
            source_code=payload.source_code,
            param_schema=param_schema,
            description=description,
            connection_dependencies=connections,
            owner=user_id,
            current_version=1,
            created_by=user_id,
            updated_by=user_id,
        )
        db.add(tool_obj)
        db.flush()

        version_row = UnifiedCatalogToolVersion(
            id=str(uuid.uuid4()),
            tool_id=tool_id,
            version=1,
            source_notebook_object_id=payload.source_notebook_object_id,
            source_code=payload.source_code,
            param_schema=param_schema,
            connection_dependencies=connections,
            promoted_by=user_id,
        )
        db.add(version_row)
        db.commit()
        db.refresh(tool_obj)
        return tool_obj


def get_tool_by_id(db: Session, tool_id: str) -> Optional[UnifiedCatalogTool]:
    """Fetch tool by ID with version history."""
    return db.query(UnifiedCatalogTool).filter(UnifiedCatalogTool.id == tool_id).first()


def get_tool_by_name(
    db: Session,
    name: str,
    catalog: str = "main",
    schema: str = "default",
) -> Optional[UnifiedCatalogTool]:
    """Fetch tool by namespace coordinates."""
    return (
        db.query(UnifiedCatalogTool)
        .filter(
            UnifiedCatalogTool.catalog_name == catalog,
            UnifiedCatalogTool.schema_name == schema,
            UnifiedCatalogTool.name == name,
        )
        .first()
    )


def list_tools(
    db: Session,
    catalog: Optional[str] = None,
    schema: Optional[str] = None,
) -> List[UnifiedCatalogTool]:
    """List tools optionally filtered by catalog / schema."""
    query = db.query(UnifiedCatalogTool)
    if catalog:
        query = query.filter(UnifiedCatalogTool.catalog_name == catalog)
    if schema:
        query = query.filter(UnifiedCatalogTool.schema_name == schema)
    return query.order_by(UnifiedCatalogTool.catalog_name, UnifiedCatalogTool.schema_name, UnifiedCatalogTool.name).all()
