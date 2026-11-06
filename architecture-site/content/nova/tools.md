# Tools

Nova registers `fetch_attachment` on the agent tool registry. The class is `FetchAttachmentTool` in `app.nova.services.tools.fetch_attachment_tool`. The registry loads it when the import succeeds. A chat turn calls it by the key `fetch_attachment` with the attachment id. The tool reads the extracted text through `fetch_attachment_content`.

`notebook_manager` and `dashboard_manager` are registered by the Agents module. Their notebook and dashboard work runs through `app.nova.services.notebook_tools` and `app.nova.services.dashboard_tools`.

There is no separate Nova HTTP tool route. Catalog tool execution stays on `POST /api/v1/agent-tools/execute`, documented with [Agents tools](../agents/tools.md).
