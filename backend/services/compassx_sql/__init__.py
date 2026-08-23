from .client import sql, write, write_table, CompassXQueryError, CompassXSchemaError
from .magic import load_ipython_extension

# Provide unified access to compassx_tools via the default `cx` namespace in notebooks
try:
    import services.compassx_tools as _cxt
    tool = _cxt.tool
    tools = _cxt.tools
    connections = _cxt.connections
    promote = _cxt.promote
except Exception:
    pass

__all__ = [
    "sql",
    "write",
    "write_table",
    "CompassXQueryError",
    "CompassXSchemaError",
    "load_ipython_extension",
    "tool",
    "tools",
    "connections",
    "promote",
]

