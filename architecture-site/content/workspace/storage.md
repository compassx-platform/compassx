# Storage

`resolve_workspace_storage` is what other modules call. It stays in `app.workspace.storage_resolver`. The logger name is `app.workspace.storage_resolver`.

A missing workspace uses account managed storage with no slug prefix. Backend `managed` or `default`, or an empty `storage_config`, uses managed storage and prefixes keys with `workspaces/{slug}/` after `STORAGE_PREFIX`. The backend comes from `STORAGE_BACKEND`, default `minio`. MinIO uses `STORAGE_ENDPOINT`, `STORAGE_BUCKET`, the access key, the secret, the region, and the prefix. S3 omits the endpoint. Azure maps the access key to `account_name`, the secret to `account_key`, and the bucket to `container`. Any other backend name returns `local` and the prefix.

A custom backend returns that backend name and the decrypted config. Fields `account_key`, `access_key`, `secret_key`, and `password` are decrypted. A value that is not encrypted is left as stored.

`validate_storage_config` writes and deletes `.compassx_probe` before a custom workspace is saved. MinIO, S3, and Azure are accepted. Anything else raises `Unknown storage backend: {name}`. Any failure becomes `Storage config validation failed: {error}`, which the create route returns as HTTP 400.

`encrypt_storage_config` encrypts those four fields with the catalog Fernet key before they are stored.

`ensure_default_storage_bucket` runs at startup and during Identity setup. For MinIO or S3 it calls `head_bucket`. A missing bucket logs `Default storage bucket '%s' does not exist. Creating...` and then `Default storage bucket '%s' created successfully.` A region other than `us-east-1` on S3 sends `LocationConstraint`. Other head errors log `Could not head default bucket '%s': %s`. Any other failure logs `Could not ensure default storage bucket '%s': %s`.
