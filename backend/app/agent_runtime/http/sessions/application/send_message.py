from __future__ import annotations


def _bind():
    import app.agent_runtime.http.edge_prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()

def send_message(session_id: str, body: SendMessageRequest):
    """Send a follow-up prompt into the running tmux agent."""
    return _run_prompt(session_id, body.content, llm_model=body.llm_model)
