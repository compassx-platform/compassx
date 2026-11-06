# Dev studio

These routes hang off `/api/v1/apps/{app_id}/dev`. A missing app is HTTP 404 `App '{id}' not found.` A workspace mismatch is HTTP 403 `Cannot access app in another workspace.`

## Workspaces

`GET /workspaces` lists dev workspaces for the app. `POST /workspaces` requires a name. An empty name is HTTP 400 `Workspace name cannot be empty.` A create failure is HTTP 500 `Failed to create dev workspace: {error}`.

`DELETE /workspaces/{workspace_id}` returns HTTP 404 `Workspace '{id}' not found.` when the workspace is missing. `POST /workspaces/{workspace_id}/activate` returns HTTP 404 with the service message when activation rejects the id, and HTTP 500 `Failed to activate dev workspace: {error}` on any other failure. `POST /workspaces/{workspace_id}/sync-main` returns HTTP 500 `Failed to sync with remote main: {error}` when the sync fails.

## Sandbox

`_build_app_sandbox_spec` builds the spec the dev sandbox uses. The repo directory comes from `omnigent_dev_service.get_repo_dir`. The Kubernetes id is the app id lowercased with `_` replaced by `-`. A stored git token is decrypted. GitHub URLs are rewritten with `x-access-token`. Other hosts use `oauth2`. The clone targets `/workspace` on branch `git_ref`, then `git_branch`, then `main`. Git identity is `CompassX Dev` and `dev@compassx.io`.

`POST /start` starts or resumes a dev session. The body can name a workspace and a host type, `compassx` or `omnigent`. `POST /restart` restarts that sandbox. `POST /sandbox/ensure` ensures the sandbox. `GET /sandbox/status` and `GET /status` report it. `POST /stop`, `POST /suspend`, and `POST /resume` change the running copy.

`_sync_agent_login` captures or restores the workspace agent login and never fails the request. A failure logs debug `Agent login sync failed for {id}`.

## Files and git

`GET /files` lists workspace files. `GET /file` reads one. `GET /file/diff` returns the diff. `PUT /file` writes content. `POST /publish` commits. The default commit message is `Update application via Omnigent Dev Studio`. `GET /commits` and `GET /workspaces/{workspace_id}/commits` return git history. `POST /verify-git` checks the checkout.

## Run

`POST /install-deps` installs dependencies. `force` defaults to false. `POST /run-app` starts the app process. `POST /exec` runs one command. `GET /logs` returns sandbox logs. `POST /heartbeat` records dev activity so the idle reaper leaves the sandbox up. `WS /terminal/ws` attaches the dev terminal.

## Sessions and build

`GET /sessions` lists app sessions. `POST /sessions` creates one. The agent default is `opencode`. `PATCH /sessions/{session_id}` updates title or status. A missing session is HTTP 404 with the service message. `DELETE /sessions/{session_id}` removes it. `GET /models` lists models the studio can use.

`GET /omnigent/agents` lists Omnigent agents. `POST /omnigent/session` creates a session. The agent name default is `polly`. `GET /build/session` and `GET /build/messages` read the build chat. `POST /build/prompt` sends a prompt. `POST /build/clear` clears it.

## Manifest

`GET /manifest` reads `app.yaml` from the repo. When no file is parsed, the run config is gateway port 8080, frontend port 4000, backend port 8000, frontend command `npm run dev`, and backend command `uvicorn main:app --port 8000`.

`PUT /manifest` writes `app.yaml`. A raw YAML body is stored as given. Otherwise the file is version `1`, named from the slug, name, or id, with optional backend, frontend, install, and env sections. Backend defaults are port 8000, dir `.`, and path `/api`. Frontend defaults are port 4000, dir `frontend`, and path `/`. The response status is `saved`. A write error is ignored. The route also tries to copy the file into a running dev pod and ignores that failure too.
