# Commands and terminal

## Exec

`POST /sandboxes/{sandbox_id}/exec` body is `ExecRequestBody`: `command` (a string or a list of tokens), optional `working_dir`, optional `env`, and `timeout` default 60 seconds.

A missing sandbox does not return 404. The body is an `ExecResult` with `exit_code` 1, `success` false, and `stderr` `Sandbox '{id}' not found`.

A found sandbox runs `driver.exec_command` in the instance working directory when the body omits one. `success` is true when the exit code is 0.

## Logs

`GET /sandboxes/{sandbox_id}/logs` takes `max_lines` from 1 to 2000, default 200. The body is `{"sandbox_id": "...", "logs": "..."}`. A missing sandbox still returns 200, and `logs` is `[Sandbox '{id}' not found]`.

`stream_sandbox_logs` is not an HTTP route. Callers that have the service can stream lines. A missing sandbox yields `[Sandbox '{id}' not found]\n` and stops.

## Terminal

`WS /sandboxes/{sandbox_id}/terminal/ws` accepts query `cols` (default 100), `rows` (default 30), `working_dir`, `command`, `agent`, and `session_id`. The socket is accepted before the sandbox lookup.

A missing sandbox sends `\r\n[ERROR] Sandbox '{id}' not found.\r\n` in red and closes with code 4404 and reason `Sandbox '{id}' not found`.

For an empty agent, or `bash`, `shell`, or `sh`, the socket first sends a banner whose first line is `● Connected to Sandbox Terminal`, then the sandbox name, module, and id. Any other agent skips that banner.

If the driver cannot open a stream, the socket sends `[ERROR] Failed to attach interactive terminal. Is the sandbox container/pod running?` and closes with code 1011 and reason `Sandbox container not reachable`.

A Kubernetes stream is the object that has `write_stdin` and `read_stdout`. Browser text that starts with `{"type":` or `{"cols":` is a control message. `resize`, or a message that has `cols` and `rows`, writes a resize channel with `Width` and `Height`. `ping` replies `{"type":"pong"}`. Other text is written to stdin. The pod-to-browser pipe logs debug `Sandbox pod to browser pipe ended: {error}`. The other direction logs `Browser to sandbox pod pipe ended: {error}`.

Docker and local use a subprocess. Output is sent as bytes. Resize calls `driver.resize_terminal`. A stdout read failure logs `Stdout read exception: {error}`. The pipes log `Sandbox subprocess stdout pipe ended: {error}` and `Browser to sandbox stdin pipe ended: {error}`. On the way out, a still-running process is terminated.
