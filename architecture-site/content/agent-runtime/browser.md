# Browser

The host process owns a browser for a session tab. The sandbox does not. `browser_host.py` is that collaborator. `routes.py` forwards each handler to one file under `http/browser/application/`. The service methods forward to `lifecycle/application/`.

The tab key is `{session_id}:{tab}`. The tab must match letters, numbers, `_`, or `-`, up to 80 characters. Anything else is HTTP 400 `Unknown browser tab.` A missing session is HTTP 404. A browser that cannot start is HTTP 503. Any other failure is HTTP 500 `Browser host failed: {error}`.

`POST /sessions/{session_id}/browser/open` body is `tab_id`, `url`, `width`, and `height`.

`GET /sessions/{session_id}/browser/frame?tab_id=` returns JPEG bytes. The headers are `X-Page-Width`, `X-Page-Height`, and `Cache-Control: no-store`.

`POST /sessions/{session_id}/browser/inspect` body is `tab_id`, `x`, and `y`. The response describes the element under that point.

`POST /sessions/{session_id}/browser/input` body is `tab_id`, `kind`, `x`, `y`, `delta_y`, `key`, and `text`. Success is `{"ok": true}`.

`POST /sessions/{session_id}/browser/note` body is `tab_id`, `instruction`, `x`, `y`, `width`, and `height`. An empty instruction is HTTP 400 `Message is empty.` The host captures the region, tries to store the JPEG in the sandbox at `/tmp/cx-notes/`, and delivers a prompt that includes the element detail, the instruction, and the screenshot path when the store succeeded. A store failure logs `[AgentRuntimeService] Could not store the annotation screenshot: %s` and the prompt is still delivered.
