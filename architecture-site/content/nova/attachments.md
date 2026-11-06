# Attachments

The router tag is `Nova Attachments`. Paths are absolute on the router because it has no prefix.

`POST /api/v1/nova/sessions/{session_id}/attachments` accepts one or more files and returns HTTP 201 `{"attachments": [...]}`. A missing session is HTTP 404 `Session not found`. The user id is `current_user["id"]`, then `sub`, then `default_user`. Each file is stored through `upload_attachment`. The response includes `file_id`, `filename`, `mime_type`, `size_bytes`, `status`, `delivery_mode`, `extracted_token_count`, `preview_text`, `extraction_error`, `promoted_object_id`, and `created_at`.

`GET /api/v1/nova/sessions/{session_id}/attachments` lists attachments for that session whose status is not `purged`, oldest first, in the same shape.

`GET /api/v1/nova/sessions/{session_id}/attachments/{file_id}` returns one attachment plus `context_payload` from `get_context_payload`. A missing file is HTTP 404 `Attachment not found`.

`POST /api/v1/nova/attachments/{file_id}/promote` body is `target_catalog_path`. It calls `promote_attachment` and returns that result.

`DELETE /api/v1/nova/sessions/{session_id}/attachments/{file_id}` sets `status` to `purged` and returns HTTP 204. It does not remove the row. A missing file is HTTP 404 `Attachment not found`.

These handlers are not mounted by `main.py`.
