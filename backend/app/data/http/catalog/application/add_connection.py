from __future__ import annotations

def _bind():
    import app.data.http.catalog.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value

_bind()

def add_connection(body: ConnectionCreate, db: Session = Depends(get_db)):
    return create_connection(db, body)
