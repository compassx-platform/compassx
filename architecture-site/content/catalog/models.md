# Registered models

Registered models live in the account tables `catalog_registered_models`, `catalog_model_versions`, and `catalog_model_aliases`. The router is `app.catalog.registered_models.routes.router`. `main.py` mounts it at `/api/v1/catalog`, the same prefix the router already carries, so the paths are `/api/v1/catalog/...`.

`routes.py` checks governance and maps `RegistryError` to HTTP. `service.py` keeps `get_model`, `list_models`, `list_in_schema`, `create_model`, `update_model`, `delete_model`, `set_alias`, `delete_alias`, `register_version`, `invoke_registered_model`, and `Registration`. Each one forwards to one file under `registered_models/application/`. `_schema`, `_model_query`, and `_index` stay in `repository.py` because more than one action uses them. The index log name is `app.catalog.registered_models`.

## List and read

`GET /models` lists models, optionally filtered by `catalog` and `schema_name`. The guard keeps rows the caller can `BROWSE`. `GET /catalogs/{catalog}/schemas/{schema}/models` checks that the schema exists, then applies the same filter. A missing catalog or schema is HTTP 404.

`GET /catalogs/{catalog}/schemas/{schema}/models/{model}` requires `BROWSE` on that model. A missing model is HTTP 404 `Model '{catalog}.{schema}.{name}' was not found.`

## Create, update, and delete

`POST /catalogs/{catalog}/schemas/{schema}/models` requires `CREATE` on the schema and returns HTTP 201. A duplicate name is HTTP 409 `Model '{catalog}.{schema}.{name}' already exists.` The owner and the created-by actor come from the current user. The storage location is `models/{name}`. After the row is flushed, the search index is asked to embed an object of type `model`. A failure logs `Failed to index registered model %s: %s` at warning and the model row still commits. The caller becomes the owner.

`PATCH` requires `EDIT`. It writes `comment` when the body sends one, and `owner` when the body sends one. `DELETE` requires `MANAGE` and returns HTTP 204.

## Versions and aliases

`POST .../models/{model}/versions` registers a version from an MLflow run. If the model does not exist yet, the caller needs `CREATE` on the schema and becomes the owner. If it exists, the caller needs `EDIT`. The artifact path is checked, the run is loaded, and each artifact file is written through the schema storage backend. A schema with no storage returns HTTP 400 `Schema '{catalog}.{schema}' has no storage backend for model artifacts.` The version number is one higher than the current maximum, or 1. Status is `READY`. An optional alias is created or moved. A failure rolls the transaction back.

`PUT .../aliases/{alias}` requires `EDIT`. The alias in the path and the body must match, or the response is HTTP 400 `The alias in the path and the body must match.` A missing version is HTTP 404. An existing alias moves to the new version.

`DELETE .../aliases/{alias}` requires `EDIT`. A missing alias is HTTP 404 `Alias '{alias}' is not set on '{full name}'.`

## Score

`POST .../models/{model}/invocations` requires `EXECUTE`. The body may name a `version`. Otherwise it uses the alias, default `champion`, and if that alias is missing it uses the highest `READY` version. No ready version is HTTP 404 `The model has no ready version to score.` Scoring reads the artifact through `serving.py`. The response is the model full name, the version, and `predictions`.
