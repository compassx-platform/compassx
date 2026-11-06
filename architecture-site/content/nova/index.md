# Nova

Nova is the side-panel assistant. Its attachment HTTP router lives in `app.nova.routes.attachment_routes`. Its file handling lives in `app.nova.services.attachment_service`. Notebook and dashboard helpers live in `app.nova.services.notebook_tools` and `dashboard_tools`, and the agent tools `notebook_manager` and `dashboard_manager` call them.

`register_agent_routers` includes the attachment router. `main.py` does not call `register_agent_routers`, and it does not include the Nova router, so `/api/v1/nova/...` is not served by the running app. The route functions still exist on `app.nova.routes.attachment_routes`.

Nova registers one agent tool, `fetch_attachment`. It is documented on the [Tools](tools.md) page.

## What stays public

`upload_session_attachments`, `list_session_attachments`, `get_session_attachment`, `promote_session_attachment`, and `delete_session_attachment` stay on the route module and forward to one application file each. `PromoteAttachmentRequest` and `_get_session_or_404` stay there. The logger name is `app.nova.routes.attachment_routes`.

`upload_attachment`, `extract_attachment`, `get_context_payload`, `fetch_attachment_content`, `promote_attachment`, and `purge_session_attachments` stay in `attachment_service`.

## Files

- `app/nova/routes/attachment_routes.py` — HTTP facade
- `app/nova/http/attachments/application/` — one file per attachment action
- `app/nova/services/attachment_service.py` — storage and extraction
- `app/nova/services/tools/fetch_attachment_tool.py` — agent tool
- `app/nova/services/notebook_tools.py` and `dashboard_tools.py` — helpers for the agent tools

## Pages

- [Attachments](attachments.md)
- [Tools](tools.md)
- [Test cases](test-cases.md)
