import os

import httpx
from compassx.lookup import try_resolve_url


class ListRegisteredModels:
    async def execute(self, max_results: int, guard):
        mlflow_url = try_resolve_url("mlflow", "http://localhost:5555").rstrip("/")
        public_ui_url = os.environ.get("COMPASSX_MLFLOW_PUBLIC_URL", "http://localhost:5555").rstrip("/")

        async with httpx.AsyncClient(timeout=4.0) as client:
            try:
                health_resp = await client.get(f"{mlflow_url}/health")
                if health_resp.status_code != 200:
                    return {
                        "connected": False,
                        "message": f"MLflow tracking server returned status {health_resp.status_code}",
                        "models": [],
                    }
            except Exception:
                return {
                    "connected": False,
                    "message": f"MLflow tracking server is not reachable at {mlflow_url}",
                    "models": [],
                }

            try:
                resp = await client.get(
                    f"{mlflow_url}/api/2.0/mlflow/registered-models/search",
                    params={"max_results": max_results},
                )
                if resp.status_code != 200:
                    return {
                        "connected": True,
                        "models": [],
                        "message": f"Failed to retrieve models: {resp.text}",
                    }

                raw_models = resp.json().get("registered_models", [])
                models_data = []
                for m in raw_models:
                    name = m.get("name")
                    versions = []
                    for v in m.get("latest_versions", []):
                        versions.append({
                            "version": v.get("version"),
                            "creation_timestamp": v.get("creation_timestamp"),
                            "last_updated_timestamp": v.get("last_updated_timestamp"),
                            "current_stage": v.get("current_stage"),
                            "aliases": v.get("aliases", []),
                            "status": v.get("status"),
                            "source": v.get("source"),
                            "run_id": v.get("run_id"),
                            "ui_url": f"{public_ui_url}/#/models/{name}/versions/{v.get('version')}",
                        })
                    tags_map = {t["key"]: t["value"] for t in m.get("tags", []) if "key" in t}
                    models_data.append({
                        "name": name,
                        "creation_timestamp": m.get("creation_timestamp"),
                        "last_updated_timestamp": m.get("last_updated_timestamp"),
                        "description": m.get("description"),
                        "latest_versions": versions,
                        "tags": tags_map,
                        "ui_url": f"{public_ui_url}/#/models/{name}",
                    })

                return {
                    "connected": True,
                    "models": models_data,
                    "total_models": len(models_data),
                }
            except Exception as exc:
                return {
                    "connected": False,
                    "message": f"Error querying models: {exc}",
                    "models": [],
                }


def list_registered_models(max_results, guard):
    return ListRegisteredModels().execute(max_results, guard)
