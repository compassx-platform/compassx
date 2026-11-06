from __future__ import annotations

def _bind():
    import app.data.http.catalog.prelude as prelude
    target = globals()
    for key, value in vars(prelude).items():
        if not key.startswith("__"):
            target[key] = value

_bind()

def preview_table(
    conn_id: int,
    database: str,
    schema: str,
    table: str,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    try:
        return get_table_preview(db, conn_id, database, schema, table, limit)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
