"""Choose a model version and score records. HTTP stays on the route."""
from __future__ import annotations

from app.catalog.registered_models.application.get_model import get_model
from app.catalog.registered_models.artifacts import RegistryError
from app.catalog.registered_models.schemas import ModelInvocation, ModelInvocationResult
from app.catalog.registered_models.serving import invoke_model


def _version_for_invocation(model, body: ModelInvocation):
    if body.version is not None:
        match = next((item for item in model.versions if item.version == body.version), None)
        if match is None:
            raise RegistryError(404, f"Version {body.version} was not found.")
        return match
    alias_name = body.alias or "champion"
    alias = next((item for item in model.aliases if item.alias == alias_name), None)
    if alias is not None:
        match = next((item for item in model.versions if item.version == alias.version), None)
        if match is not None:
            return match
    ready = [item for item in model.versions if item.status == "READY"]
    if not ready:
        raise RegistryError(404, "The model has no ready version to score.")
    return max(ready, key=lambda item: item.version)


async def invoke_registered_model(db, catalog_name, schema_name, model_name, body):
    model = get_model(db, catalog_name, schema_name, model_name)
    version = _version_for_invocation(model, body)
    predictions = await invoke_model(db, model, version, body.dataframe_records)
    return ModelInvocationResult(model=model.full_name, version=version.version, predictions=predictions)
