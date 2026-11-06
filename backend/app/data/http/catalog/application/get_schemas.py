from __future__ import annotations

def _bind():
    import app.data.http.catalog.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value

_bind()

def get_schemas(conn_id: int, database: str, db: Session = Depends(get_db)):
    try:
        schemas = list_schemas(db, conn_id, database)
        return SchemaListResponse(schemas=[SchemaItem(**s) for s in schemas])
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
