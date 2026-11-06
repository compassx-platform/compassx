from __future__ import annotations

def _bind():
    import app.data.http.catalog.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value

_bind()

def get_tables(conn_id: int, database: str, schema: str, db: Session = Depends(get_db)):
    try:
        tables = list_tables(db, conn_id, database, schema)
        return TableListResponse(tables=[TableItem(**t) for t in tables])
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
