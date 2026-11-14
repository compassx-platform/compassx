from __future__ import annotations


def _bind():
    import app.agent_runtime.http.edge_prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()

def list_agents():
    """Agents the runtime can launch. New agents appear here when they are registered."""
    from app.sandbox.agents import agent_registry

    return agent_registry.catalog()
