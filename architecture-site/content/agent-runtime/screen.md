# Screen

The screen is `AgentRuntimePage`. Routes are `agent-runtime`, `agent-runtime/:sessionId`, `agents/runtime`, and `agents/runtime/:sessionId`.

The panel title is **Agent Runtime**. **Create Session** opens the create dialog. Success toasts `Agent session created ({agent_type})`. Failure toasts the response `detail` or `Failed to create agent session`. A list failure toasts `Failed to load agent sessions`.

Delete toasts `Agent session deleted` or `Failed to delete session`. Resume toasts `Requested sandbox provision / resume` or the response `detail` or `Failed to resume sandbox`.

The open session reuses the Omnigent chat panel bound to `sandbox_id`. A send failure toasts the response `detail`, the error message, or `Failed to send prompt to agent`.
