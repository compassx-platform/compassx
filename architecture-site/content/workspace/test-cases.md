# Test cases

These are product checks. Use an account admin.

## Create a workspace

Open Create a Workspace. Submit a name and a new slug, and leave storage managed. You should get HTTP 201 and a url `/w/{slug}`. Open that url. The workspace should be active. Creating the same slug again should say `Workspace slug already exists`. The server log for a successful create should not contain `Failed to create workspace due to catalog creation/binding error`. The new workspace should have a default catalog ending in `_default`, schema `default`, volume `sample_data`, and notebook `getting_started`.

## Custom storage

Create a workspace with storage backend `minio` and a bad endpoint. You should see `Storage config validation failed`. Create one with a backend name that is not `minio`, `s3`, or `azure`. You should see `Unknown storage backend`.

## Account and workspace settings

Open Account Settings. You should see the account name and sections for Airflow, the app node pool, and compute. Change the Airflow tuning profile and save. Reload the page. The saved profile should still be there. Open Workspace Settings inside a workspace. You should see Python `3.11` until you change it. Save a different Python version and reload. The new version should be the one returned by `GET /api/w/{slug}/api/workspace/settings`.

## Members and publish

As a workspace admin, `POST /api/w/{slug}/api/workspace/members` with role `editor`. You should see `Invalid role`. Add a principal with role `member`. You should get HTTP 201. Add the same principal again. You should see `Principal already a member`. Remove the membership. The next list should omit it.

Publish a catalog object that already has visibility `global`. You should see `Object already published`.

## Gate

Open `/w/not-a-workspace` with a signed-in token. The response should be HTTP 404 and JSON `{"error": "workspace not found"}`. Open a workspace whose status is not `active`. You should see `workspace unavailable`. Call a workspace route with no token. You should see `missing auth token`.
