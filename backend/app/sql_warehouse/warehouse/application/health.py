from sqlalchemy import text
from sqlalchemy.orm import Session


class WarehouseHealth:
    def execute(self, db: Session):
        postgres = True
        try:
            db.execute(text("SELECT 1"))
        except Exception:
            postgres = False
        return {"status": "ok" if postgres else "degraded", "postgres": postgres, "cache": True}


def health(db):
    return WarehouseHealth().execute(db)
