import logging
import os

import httpx
from app.governance.dependencies import Guard
from compassx.lookup import try_resolve_url

logger = logging.getLogger("app.notebooks.routes.notebook_routes")


class GetNotebookExperimentRuns:
    async def execute(self, path: str, max_results: int, guard: Guard):
        clean_path = path.replace("\\", "/").strip("/")
        exp_candidates = [
            f"/{clean_path}",
            clean_path,
            f"/notebooks/{clean_path}",
        ]

        mlflow_url = try_resolve_url("mlflow", "http://localhost:5555").rstrip("/")
        public_ui_url = os.environ.get("COMPASSX_MLFLOW_PUBLIC_URL", "http://localhost:5555").rstrip("/")

        async with httpx.AsyncClient(timeout=4.0) as client:
            # Check health/reachability
            try:
                health_resp = await client.get(f"{mlflow_url}/health")
                if health_resp.status_code != 200:
                    return {
                        "connected": False,
                        "message": f"MLflow server returned status {health_resp.status_code}",
                        "runs": [],
                    }
            except Exception as exc:
                return {
                    "connected": False,
                    "message": f"MLflow tracking server is not reachable at {mlflow_url}",
                    "runs": [],
                }

            # Try to find experiment by candidate names
            experiment = None
            for name in exp_candidates:
                try:
                    resp = await client.get(
                        f"{mlflow_url}/api/2.0/mlflow/experiments/get-by-name",
                        params={"experiment_name": name},
                    )
                    if resp.status_code == 200:
                        experiment = resp.json().get("experiment")
                        break
                except Exception:
                    pass

            if not experiment:
                return {
                    "connected": True,
                    "experiment": None,
                    "ui_url": public_ui_url,
                    "message": f"No MLflow experiment found for notebook '{clean_path}' yet.",
                    "runs": [],
                }

            exp_id = experiment["experiment_id"]
            exp_ui_url = f"{public_ui_url}/#/experiments/{exp_id}"

            # Fetch runs
            runs_data = []
            try:
                search_resp = await client.post(
                    f"{mlflow_url}/api/2.0/mlflow/runs/search",
                    json={
                        "experiment_ids": [exp_id],
                        "max_results": max_results,
                        "order_by": ["attributes.start_time DESC"],
                    },
                )
                if search_resp.status_code == 200:
                    raw_runs = search_resp.json().get("runs", [])
                    for r in raw_runs:
                        info = r.get("info", {})
                        data = r.get("data", {})
                        start_ms = info.get("start_time")
                        end_ms = info.get("end_time")
                        duration_ms = (end_ms - start_ms) if (start_ms and end_ms and end_ms >= start_ms) else None

                        metrics_map = {m["key"]: m["value"] for m in data.get("metrics", []) if "key" in m}
                        params_map = {p["key"]: p["value"] for p in data.get("params", []) if "key" in p}
                        tags_map = {t["key"]: t["value"] for t in data.get("tags", []) if "key" in t}

                        run_id = info.get("run_id")
                        runs_data.append({
                            "run_id": run_id,
                            "run_name": info.get("run_name") or run_id,
                            "status": info.get("status", "UNKNOWN"),
                            "start_time": start_ms,
                            "end_time": end_ms,
                            "duration_ms": duration_ms,
                            "artifact_uri": info.get("artifact_uri"),
                            "metrics": metrics_map,
                            "params": params_map,
                            "tags": tags_map,
                            "ui_url": f"{public_ui_url}/#/experiments/{exp_id}/runs/{run_id}",
                        })
            except Exception as exc:
                logger.warning("Failed to search MLflow runs for experiment %s: %s", exp_id, exc)

            return {
                "connected": True,
                "experiment": {
                    "experiment_id": exp_id,
                    "name": experiment.get("name"),
                    "artifact_location": experiment.get("artifact_location"),
                    "lifecycle_stage": experiment.get("lifecycle_stage"),
                },
                "ui_url": exp_ui_url,
                "total_runs": len(runs_data),
                "runs": runs_data,
            }


def get_notebook_experiment_runs(path, max_results, guard):
    return GetNotebookExperimentRuns().execute(path, max_results, guard)
