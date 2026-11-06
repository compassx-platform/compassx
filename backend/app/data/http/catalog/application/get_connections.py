from __future__ import annotations

def _bind():
    import app.data.http.catalog.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value

_bind()

def get_connections(db: Session = Depends(get_db)):
    return list_connections(db)
