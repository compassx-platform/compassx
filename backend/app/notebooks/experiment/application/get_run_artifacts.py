import httpx
from compassx.lookup import try_resolve_url


class GetRunArtifacts:
    async def execute(self, run_id: str, path: str, guard):
        mlflow_url = try_resolve_url("mlflow", "http://localhost:5555").rstrip("/")

        async with httpx.AsyncClient(timeout=4.0) as client:
            try:
                resp = await client.get(
                    f"{mlflow_url}/api/2.0/mlflow/artifacts/list",
                    params={"run_id": run_id, "path": path},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return {
                        "connected": True,
                        "root_uri": data.get("root_uri"),
                        "files": data.get("files", []),
                    }
                return {
                    "connected": False,
                    "message": f"MLflow returned status {resp.status_code}",
                    "files": [],
                }
            except Exception as exc:
                return {
                    "connected": False,
                    "message": f"Failed to fetch artifacts: {exc}",
                    "files": [],
                }


def get_run_artifacts(run_id, path, guard):
    return GetRunArtifacts().execute(run_id, path, guard)
