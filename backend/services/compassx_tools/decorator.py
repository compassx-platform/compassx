"""Decorator and schema utilities for CompassX tools."""

from __future__ import annotations

import inspect
from typing import Any, Callable, Sequence, get_type_hints


def _py_type_to_json_schema(py_type: Any) -> dict[str, Any]:
    """Map python type annotations to JSON Schema types."""
    if py_type is str:
        return {"type": "string"}
    elif py_type is int:
        return {"type": "integer"}
    elif py_type is float:
        return {"type": "number"}
    elif py_type is bool:
        return {"type": "boolean"}
    elif py_type is list or getattr(py_type, "__origin__", None) is list:
        return {"type": "array"}
    elif py_type is dict or getattr(py_type, "__origin__", None) is dict:
        return {"type": "object"}
    return {"type": "string"}


def extract_param_schema(fn: Callable[..., Any]) -> dict[str, Any]:
    """Derive an OpenAI-compatible JSON Schema parameter definition from a function."""
    sig = inspect.signature(fn)
    try:
        type_hints = get_type_hints(fn)
    except Exception:
        type_hints = {}

    properties: dict[str, Any] = {}
    required: list[str] = []

    for name, param in sig.parameters.items():
        if name in ("self", "cls"):
            continue
        py_type = type_hints.get(name, param.annotation if param.annotation != inspect.Parameter.empty else str)
        schema_prop = _py_type_to_json_schema(py_type)

        if param.default == inspect.Parameter.empty:
            required.append(name)
        else:
            schema_prop["default"] = param.default

        properties[name] = schema_prop

    return {
        "type": "object",
        "properties": properties,
        "required": required,
    }


def tool(
    name: str | None = None,
    description: str | None = None,
    connections: Sequence[str] | None = None,
    param_schema: dict[str, Any] | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator to declare a Python function as a CompassX agent tool.

    Example:
        @cx.tool(
            name="get_last_5_min_logs",
            description="Fetch the last 5 minutes of logs for a service from Loki",
            connections=["loki_prod"],
        )
        def get_last_5_min_logs(service: str) -> str:
            client = cx.connections.get("loki_prod")
            return client.query_range(f'{{service="{service}"}}', minutes=5)
    """
    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        tool_name = name or fn.__name__
        tool_desc = description or (inspect.getdoc(fn) or f"Tool {tool_name}").strip()
        tool_conns = list(connections) if connections is not None else []
        tool_params = param_schema if param_schema is not None else extract_param_schema(fn)

        fn._is_cx_tool = True
        fn._tool_name = tool_name
        fn._tool_description = tool_desc
        fn._tool_connections = tool_conns
        fn._tool_param_schema = tool_params

        return fn

    return decorator
