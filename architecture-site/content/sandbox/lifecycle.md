# Lifecycle

A sandbox id is the spec's `sandbox_id`, or `sb-` plus 10 hex characters. `consumer_key` is the idempotency key. Matching ignores case and treats `_` as `-`.

## List

`GET /sandboxes` reads the workspace id from the request when one is present. Optional query `consumer_module` and `status` filter the list. A row with no `workspace_id` is kept even when a workspace filter is set. Rows are newest `created_at` first.

The list merges three sources:

1. Instances already in `sandbox_service._instances`.
2. Instances the active driver discovers. A discovery failure logs debug `Sandbox driver discovery error: {error}` and the in-memory rows are still returned.
3. Active `DevWorkspace` rows. Each one is shown as id `dev-app-{app_id}`, consumer key `app_{app_id}`, name `{app name} (Dev Sandbox)`, module `app`, status `running`, and image `compassx-dev-host:latest`. A lookup failure logs debug `Dev workspace discovery error: {error}`.

## Provision and ensure

`POST /sandboxes` is HTTP 201. `POST /sandboxes/ensure` returns the instance. Both copy the request workspace id onto the spec when the spec has none.

`provision_sandbox` calls `ensure_sandbox` and wraps the instance in a `SandboxHandle`.

`ensure_sandbox` looks up an existing sandbox by id or consumer key. If the live status is `ready` or `running`, it returns that instance with progress stage `ready`, message `Sandbox is active and ready`, percent 100, and logs `ensure_sandbox: Returning existing active sandbox {name} ({id})`.

If the live status is `suspended` or `stopped`, it resumes the sandbox and returns progress message `Sandbox resumed successfully`. If the status is `provisioning` or `initializing`, it returns the instance unchanged.

Otherwise it provisions. The consumer key is copied onto label `compassx.consumer_key` when that label is missing. Progress stages are:

| Stage | Step name | Message |
| --- | --- | --- |
| `allocating` | Allocate Compute | `Allocating compute sandbox for '{name}'...` |
| `starting` | Start Runtime | `Starting sandbox container environment...` |
| `initializing` | the script name | `Running step [{n}/{total}]: {name}...` |
| `ready` | Ready | `Sandbox environment is ready` |

A failed init script that does not set `ignore_failure` sets status `failed`, logs the error line, and returns. The error text is `Init step '{name}' failed with exit code {code}: {stderr or stdout}`. A driver status that is already `failed` logs `Sandbox '{name}' ({id}) FAILED in {seconds}s: {message}`. A status that is still `provisioning` returns progress message `Sandbox compute is provisioning in cluster...`. Success logs `Sandbox '{name}' ({id}) is READY in {seconds}s`.

## Get

`GET /sandboxes/{sandbox_id}` refreshes status and endpoints from the driver. A missing id is HTTP 404 `Sandbox '{id}' not found`.

## Suspend and resume

`POST /sandboxes/{sandbox_id}/suspend` returns `{"suspended": true, "sandbox_id": "..."}` and sets status `suspended`. A missing sandbox or a driver failure is HTTP 404 `Sandbox '{id}' not found or could not be suspended`.

`POST /sandboxes/{sandbox_id}/resume` returns `{"resumed": true, "sandbox_id": "..."}` and sets status `running`. The 404 detail is `Sandbox '{id}' not found or could not be resumed`.

## Terminate

`DELETE /sandboxes/{sandbox_id}` and `POST /sandboxes/{sandbox_id}/terminate` both call `terminate_sandbox`. Success is `{"terminated": true, "sandbox_id": "..."}`.

If no instance can be found, the method removes any in-memory row and returns true, so the HTTP response is still terminated. The 404 `Sandbox '{id}' not found or could not be terminated` is returned only when a driver terminate call returns false. After a real terminate, status is `terminated` and both the requested id and the instance id are dropped from memory.
