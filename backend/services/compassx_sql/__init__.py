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

# Ambient MLflow tracking: automatically bind active notebook experiment and autologging
try:
    import os
    from services.mlflow_notebook import bind_notebook_experiment

    _nb_path = os.environ.get("COMPASSX_NOTEBOOK_PATH") or os.environ.get("NOTEBOOK_PATH") or ""
    _nb_exp = bind_notebook_experiment(_nb_path) if _nb_path else ""
    if _nb_exp:
        # Cell execution hook: link cell runs and display inline run banner
        try:
            import IPython
            ip = IPython.get_ipython()
            if ip is not None:
                def _compassx_mlflow_post_run_cell(result):
                    try:
                        import mlflow
                        from IPython.display import display, HTML
                        active = mlflow.active_run()
                        if active:
                            info = active.info
                            run_id = info.run_id
                            run_name = info.run_name or run_id
                            ui_base = os.environ.get("COMPASSX_MLFLOW_PUBLIC_URL", "http://localhost:5555").rstrip("/")
                            exp_id = info.experiment_id
                            link = f"{ui_base}/#/experiments/{exp_id}/runs/{run_id}"
                            try:
                                mlflow.set_tag("compassx.source", "notebook")
                                mlflow.set_tag("compassx.notebook_path", _nb_exp)
                            except Exception:
                                pass
                            display(HTML(
                                f'<div style="font-family: system-ui, -apple-system, sans-serif; font-size: 12px; '
                                f'padding: 6px 12px; margin: 6px 0; background: #f0fdf4; border: 1px solid #bbf7d0; '
                                f'border-radius: 6px; color: #166534; display: flex; align-items: center; gap: 8px;">'
                                f'<span>⚡ <b>MLflow Run:</b> {run_name}</span>'
                                f'<span style="color: #65a30d; font-size: 11px;">({run_id[:8]})</span>'
                                f'<a href="{link}" target="_blank" rel="noopener noreferrer" '
                                f'style="margin-left: auto; color: #15803d; text-decoration: underline; font-weight: 500;">'
                                f'View in MLflow →</a></div>'
                            ))
                    except Exception:
                        pass

                ip.events.register("post_run_cell", _compassx_mlflow_post_run_cell)
        except Exception:
            pass
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


