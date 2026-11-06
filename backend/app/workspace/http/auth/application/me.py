from __future__ import annotations

def _bind():
    import app.workspace.http.auth.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value


_bind()


def me(principal: Principal = Depends(get_current_principal)):
    return principal
