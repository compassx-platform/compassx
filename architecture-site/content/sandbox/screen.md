# Screen

The sandbox list is the **Sandboxes** tab on **Compute**. The route is `compute?tab=sandboxes`. The search placeholder is `Filter sandboxes`. An empty table says `No compute sandboxes running currently`. The button is **Provision Sandbox**. The list refreshes with the rest of the Compute page, every 10 seconds.

## Provision

The dialog title is **Provision Compute Sandbox**. The name placeholder is `e.g., app-build-sandbox-1`. An empty name shows `Sandbox name is required.`

The consumer choices are App Engine, Agent Runtime, Dev Studio, Notebook, Jobs Runner, and Custom Sandbox. The preset images include `compassx-sandbox-host:latest`, `python:3.11-slim`, `node:20-slim`, `compassx/runtime-base:latest`, and `debian:bookworm-slim`. The custom image placeholder is `Or enter custom container image (e.g. ubuntu:22.04)`. The ports placeholder is `8080, 8501, 3000`. The init command placeholder is `e.g., pip install fastapi uvicorn`.

The submit button is **Provision Sandbox**, and **Provisioning...** while the request runs. The working directory sent with the spec is `/workspace`. An init command is stored as a script named `Startup Script` with a 120 second timeout. A failure shows the server message or `Failed to provision sandbox`.

## Terminal

Opening a sandbox goes to `compute/sandboxes/{sandboxId}` or `compute/sandboxes/{sandboxId}/terminal`. The back button is **Sandboxes** and returns to `/compute?tab=sandboxes`. The title is the sandbox name, or the id when the name is missing. Details reload every 8 seconds. A load failure shows the server detail or `Failed to load sandbox details`.

**Suspend** shows `Suspending sandbox compute...`. A failure shows `Suspend failed: {message}`. **Resume** shows `Resuming sandbox compute...` and `Resume failed: {message}`.

**Terminate Sandbox** asks `Are you sure you want to terminate sandbox "{name}"? All running processes and ephemeral state will be permanently removed.` The confirm button is **Terminate**. Success is `Sandbox terminated successfully`. Failure is `Termination failed: {message}`.
