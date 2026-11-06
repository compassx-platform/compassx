"""Import shim. The implementation lives under `app.catalog.infrastructure`.
"""
import importlib as _importlib

_mod = _importlib.import_module('app.catalog.infrastructure.zorder')
globals().update({name: value for name, value in vars(_mod).items() if not name.startswith('__')})
