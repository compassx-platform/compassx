# Workspace files

A session's sandbox working directory is `/workspace`. These routes read and write that directory through the sandbox exec channel. `routes.py` forwards each handler to one file under `http/workspace/application/`. The service methods forward to `lifecycle/application/`.

A missing session is HTTP 404. A path error or an empty path is HTTP 400. A sandbox that is not running is HTTP 409. Any other failure is HTTP 500 `Failed to read workspace: {error}`.

`GET /sessions/{session_id}/files` returns `root` and `entries` of `path`, `type`, and `size`.

`GET /sessions/{session_id}/files/content?path=` returns `path`, `content`, `truncated`, and `missing`.

`PUT /sessions/{session_id}/files/content` body is `path` and `content`. The response is `path` and `bytes`.

`GET /sessions/{session_id}/changes` returns git `entries`, `branch`, and recent `commits`.

`GET /sessions/{session_id}/changes/patch` returns one diff of the uncommitted changes. `GET /sessions/{session_id}/changes/diff?path=` returns the diff for that path.

`GET /sandboxes/{sandbox_id}/git` returns `repo`, `branch`, and `branches` for a running sandbox. A value error is HTTP 400. A sandbox that is not running is HTTP 409. Any other failure is HTTP 500 `Failed to read git branches: {error}`.

Creating a session with `sandbox_mode` `existing`, a sandbox id, and a `branch` checks that branch out before the session is stored. A checkout failure is the git error, cut at 400 characters, returned as HTTP 400.
