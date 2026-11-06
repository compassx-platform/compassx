# Connections

A connection is one API base URL plus how to authenticate. The screen calls it an API connection. The row is `ingestion_connection`. The secret, when there is one, is a separate `credential_secret` row. Responses include `has_secret` and never the secret.

## Create

`POST /connections` takes name, base URL, auth type, non-secret `auth_config`, optional `secret_value`, default headers, rate limit, and max concurrency. Auth types are `none`, `api_key_header`, `api_key_query`, `bearer_token`, and `basic_auth`.

When `secret_value` is present, the action encrypts it with Fernet from `INGESTION_SECRET_KEY` and stores the bytes on a new `credential_secret` row. The connection stores that row's id as `secret_ref`. A missing key uses the built-in development key. If the cryptography package is missing, the value is base64-encoded instead. The response is the connection, with `has_secret` true when `secret_ref` is set.

## Read and update

`GET /connections` returns the workspace's connections ordered by name. `GET /connections/{id}` returns one. A miss is HTTP 404, `Connection {id} not found`.

`PATCH /connections/{id}` writes each field that was sent and that exists on the row. A field sent as null is left unchanged. The secret is not on this body. A miss is the same 404.

## Rotate and delete

`POST /connections/{id}/rotate-secret` with `new_secret_value` replaces the encrypted value, or creates a secret row when the connection had none or the referenced row is gone. The response is HTTP 204. The new secret is not returned.

`DELETE /connections/{id}` counts enabled job configs for that connection in the workspace. When the count is greater than zero the response is HTTP 400: `Cannot delete connection — {count} enabled job config(s) still reference it. Disable them first.` Otherwise the connection row is deleted. Disabled job configs attached to it are removed with it, because the relationship cascade deletes them. The response is HTTP 204.

## Use at run time

`resolve_secret` reads `credential_secret` and decrypts it. Only the executor calls it. It returns null when there is no secret row.
