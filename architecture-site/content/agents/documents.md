# Documents and changes

Both groups hang off `/api/v1/agents/{agent_id}/sessions/{session_id}`. The session is resolved through the agent, so another workspace's session id does not resolve.

## Documents

`POST /documents` accepts uploaded files and returns HTTP 201. No files is HTTP 400 `No files uploaded`. When the agent disallows uploads, the response is HTTP 403 `Document upload is disabled for this agent`.

`GET /documents` lists the session documents. `DELETE /documents/{doc_id}` returns HTTP 204. A missing document is HTTP 404 `Document not found`.

## Changes

`GET /changes` lists proposed changes for the session. `GET /changes/{change_id}` returns one. A missing change is HTTP 404 `Change {id} not found`.

`POST /changes/{change_id}/accept` applies the change. A failure is HTTP 400 with the result error, or `Accept failed`. `POST /changes/{change_id}/reject` declines it. A failure is HTTP 400 with the result error, or `Reject failed`.

`POST /changes/bulk-review` accepts `accept_all` or `reject_all`. Any other action is HTTP 400 `action must be 'accept_all' or 'reject_all'`.
