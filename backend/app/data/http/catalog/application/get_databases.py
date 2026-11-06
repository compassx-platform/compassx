from __future__ import annotations

def _bind():
    import app.data.http.catalog.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value

_bind()

def get_databases(conn_id: int, db: Session = Depends(get_db)):
    try:
        dbs = list_databases(db, conn_id)
        return DatabaseListResponse(databases=[DatabaseItem(**d) for d in dbs])
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
