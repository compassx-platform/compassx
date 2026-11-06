# Experiments

Experiment routes talk to MLflow over HTTP. The tracking URL comes from service lookup name `mlflow`, and falls back to `http://localhost:5555`. The UI link uses `COMPASSX_MLFLOW_PUBLIC_URL`, with the same fallback. A signed-in member is required. The handlers do not check a privilege on a notebook or a model.

## Runs

`GET /api/v1/notebook/experiments/runs?path=&max_results=50` looks for an experiment named `/{path}`, then `{path}`, then `/notebooks/{path}`. Slashes in the path are normalised.

When MLflow does not answer, the body is `{ "connected": false, "message": "MLflow tracking server is not reachable at {url}", "runs": [] }`. A health check that is not 200 uses `MLflow server returned status {code}`.

When MLflow answers and no experiment matches, the body is connected, `experiment` is null, and the message is `No MLflow experiment found for notebook '{path}' yet.`

A match returns the experiment id, name, artifact location, and lifecycle stage, plus `ui_url` and the runs. Each run has `run_id`, `run_name`, `status` (default `UNKNOWN`), start and end times, `duration_ms`, `artifact_uri`, `metrics`, `params`, `tags`, and a UI link. A search failure logs `Failed to search MLflow runs for experiment {id}: {error}` at warning and still returns the experiment with the runs collected so far.

## Artifacts

`GET /api/v1/notebook/experiments/runs/{run_id}/artifacts?path=` lists files. Success is `{ "connected": true, "root_uri", "files" }`. A non-200 response is `{ "connected": false, "message": "MLflow returned status {code}", "files": [] }`. A connection error is `Failed to fetch artifacts: {error}`.

## Models

`GET /api/v1/notebook/experiments/models?max_results=50` lists registered models. An unreachable server is `{ "connected": false, "message": "MLflow tracking server is not reachable at {url}", "models": [] }`. A health status other than 200 says `MLflow tracking server returned status {code}`. A search that is not 200 stays connected and sets `message` to `Failed to retrieve models: {body}`. Each model includes `name`, timestamps, `description`, `latest_versions`, `tags`, and `ui_url`.

`POST /api/v1/notebook/experiments/models/register` takes `run_id`, `model_name`, `artifact_path` (default `model`), and `description`. The source is `runs:/{run_id}/{artifact_path}`. It posts a create-registered-model call and ignores a failure, then posts a create-model-version call. Success is `{ "success": true, "model_name", "version", "source", "ui_url", "model_version" }`. A non-200 version create raises that status with `MLflow error creating model version: {body}`. A connection error is 500 `Failed to communicate with MLflow Model Registry: {error}`.
