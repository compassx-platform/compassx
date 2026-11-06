import os

import httpx
from fastapi import HTTPException
from compassx.lookup import try_resolve_url


class RegisterModelVersion:
    async def execute(self, payload, guard):
        mlflow_url = try_resolve_url("mlflow", "http://localhost:5555").rstrip("/")
        public_ui_url = os.environ.get("COMPASSX_MLFLOW_PUBLIC_URL", "http://localhost:5555").rstrip("/")

        clean_path = payload.artifact_path.strip("/")
        source = f"runs:/{payload.run_id}/{clean_path}" if clean_path else f"runs:/{payload.run_id}"

        async with httpx.AsyncClient(timeout=6.0) as client:
            # Step 1: Ensure registered model exists
            try:
                await client.post(
                    f"{mlflow_url}/api/2.0/mlflow/registered-models/create",
                    json={"name": payload.model_name, "description": payload.description},
                )
            except Exception:
                pass

            # Step 2: Create model version
            try:
                resp = await client.post(
                    f"{mlflow_url}/api/2.0/mlflow/model-versions/create",
                    json={
                        "name": payload.model_name,
                        "source": source,
                        "run_id": payload.run_id,
                        "description": payload.description,
                    },
                )
                if resp.status_code in (200, 201):
                    version_info = resp.json().get("model_version", {})
                    version_num = version_info.get("version")
                    return {
                        "success": True,
                        "model_name": payload.model_name,
                        "version": version_num,
                        "source": source,
                        "ui_url": f"{public_ui_url}/#/models/{payload.model_name}/versions/{version_num}",
                        "model_version": version_info,
                    }
                else:
                    raise HTTPException(
                        status_code=resp.status_code,
                        detail=f"MLflow error creating model version: {resp.text}",
                    )
            except HTTPException:
                raise
            except Exception as exc:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to communicate with MLflow Model Registry: {exc}",
                )


def register_model_version(payload, guard):
    return RegisterModelVersion().execute(payload, guard)
