from __future__ import annotations

from sqlalchemy.orm import Session

from app.catalog.registered_models.application.get_model import get_model

def delete_model(db: Session, catalog_name: str, schema_name: str, name: str) -> None:
    model = get_model(db, catalog_name, schema_name, name)
    db.delete(model)
    db.commit()

