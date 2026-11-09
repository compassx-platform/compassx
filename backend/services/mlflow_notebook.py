"""Bind a notebook to its MLflow experiment.

Databricks gives every notebook an experiment named after the notebook.
Runs from ``mlflow.start_run()`` and autologging land there unless the
caller has already selected a different experiment.
"""

from __future__ import annotations

import os


def notebook_experiment_name(path: str) -> str:
    clean = path.replace("\\", "/").strip().lstrip("/")
    return f"/{clean}" if clean else ""


def _tracking_uri() -> str:
    current = os.environ.get("MLFLOW_TRACKING_URI")
    if current:
        return current.rstrip("/")
    try:
        from compassx.lookup import try_resolve_url

        return try_resolve_url("mlflow", "http://localhost:5555").rstrip("/")
    except Exception:
        return "http://localhost:5555"


def _active_experiment_name(mlflow) -> str | None:
    if mlflow.__class__.__name__ == "MagicMock":
        return None
    try:
        from mlflow.tracking.fluent import _get_experiment_id

        experiment_id = _get_experiment_id()
        if not experiment_id:
            return None
        experiment = mlflow.get_experiment(experiment_id)
        name = getattr(experiment, "name", None)
        return name if isinstance(name, str) else None
    except Exception:
        return None


def bind_notebook_experiment(path: str, notebook_id: str | None = None) -> str:
    """Select this notebook's experiment when the session has not chosen another."""
    experiment_name = notebook_experiment_name(path)
    if not experiment_name:
        return ""

    notebook_path = experiment_name.lstrip("/")
    os.environ["COMPASSX_NOTEBOOK_PATH"] = notebook_path
    os.environ["NOTEBOOK_PATH"] = notebook_path
    os.environ["MLFLOW_EXPERIMENT_NAME"] = experiment_name
    if notebook_id:
        os.environ["NOTEBOOK_ID"] = str(notebook_id)
    os.environ["MLFLOW_TRACKING_URI"] = _tracking_uri()

    try:
        import mlflow

        mlflow.set_tracking_uri(os.environ["MLFLOW_TRACKING_URI"])
        bound = os.environ.get("COMPASSX_BOUND_EXPERIMENT")
        current = _active_experiment_name(mlflow)
        if bound and current not in (None, "Default", bound):
            return experiment_name

        if mlflow.get_experiment_by_name(experiment_name) is None:
            try:
                mlflow.create_experiment(experiment_name)
            except Exception:
                pass
        mlflow.set_experiment(experiment_name)
        os.environ["COMPASSX_BOUND_EXPERIMENT"] = experiment_name

        autolog = os.environ.get("COMPASSX_MLFLOW_AUTOLOG", "true").lower()
        if autolog in ("true", "1", "yes") and os.environ.get("COMPASSX_MLFLOW_AUTOLOG_DONE") != "1":
            try:
                mlflow.autolog(log_models=True, silent=True)
            except Exception:
                pass
            os.environ["COMPASSX_MLFLOW_AUTOLOG_DONE"] = "1"
    except Exception:
        return experiment_name
    return experiment_name
