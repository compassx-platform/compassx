from __future__ import annotations


def _bind():
    import app.agent_runtime.http.edge_prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()

def start_session(session_id: str, body: SendMessageRequest):
    """Start the selected agent in tmux and deliver the first prompt."""
    return _run_prompt(session_id, body.content, llm_model=body.llm_model)
