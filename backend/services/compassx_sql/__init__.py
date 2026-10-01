from .client import sql, write, write_table, optimize, optimize_table, CompassXQueryError, CompassXSchemaError
from .zorder import z_order_dataframe, normalize_to_uint32, interleave_bits_2d, interleave_bits_nd
try:
    from .magic import load_ipython_extension
except ImportError:
    load_ipython_extension = None

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
    "optimize",
    "optimize_table",
    "z_order_dataframe",
    "normalize_to_uint32",
    "interleave_bits_2d",
    "interleave_bits_nd",
    "CompassXQueryError",
    "CompassXSchemaError",
    "load_ipython_extension",
    "tool",
    "tools",
    "connections",
    "promote",
]


