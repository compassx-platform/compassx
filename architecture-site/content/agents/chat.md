# Chat

`/api/v1/agents/{agent_id}` is the chat API. Listing and reading sessions requires `BROWSE` on the agent. Creating a session, deleting one, and streaming a turn require `EXECUTE`. That privilege is the one that lets a turn run tools as the agent.

## Sessions

`GET /sessions` returns the agent's sessions. `POST /sessions` returns HTTP 201. `DELETE /sessions/{session_id}` archives the session and returns HTTP 204.

`GET /sessions/{session_id}/messages` returns the transcript. `GET /sessions/{session_id}/context` returns context usage. `GET /sessions/{session_id}/plans` lists plans. `GET /sessions/{session_id}/plans/latest` returns the newest plan.

A session id that does not belong to this agent is HTTP 404 `Session not found`.

## Stream

`POST /sessions/{session_id}/stream` runs one chat turn. The handler resolves the agent with `EXECUTE`, loads the session, and streams the orchestrator events. The route module keeps the handler name `stream_chat`.

Active streams are also listed at `/api/v1/streams`. `GET /streams/active` returns streams the caller may see. `GET /streams/{stream_id}/events` attaches to a stream. `POST /streams/{stream_id}/cancel` cancels it. A missing stream is HTTP 404 `Stream not found`.

## LLM call logs

`GET /api/v1/llm-calls` lists call logs for agents in the workspace. `GET /api/v1/llm-calls/{call_id}` returns one log. A missing log is HTTP 404 `LLM call log not found`.
