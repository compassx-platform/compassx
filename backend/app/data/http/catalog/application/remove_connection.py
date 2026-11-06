from __future__ import annotations

def _bind():
    import app.data.http.catalog.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value

_bind()

def remove_connection(conn_id: int, db: Session = Depends(get_db)):
    if not delete_connection(db, conn_id):
        raise HTTPException(status_code=404, detail="Connection not found")
