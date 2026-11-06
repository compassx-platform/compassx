from typing import Optional

from sqlalchemy.orm import Session

from app.ingestion.infrastructure.secret_box import _decrypt
from app.ingestion.models import CredentialSecret, IngestionConnection


class ResolveSecret:
    def execute(self, db: Session, connection: IngestionConnection) -> Optional[str]:
        """Decrypt and return the raw secret for a connection. Server-side only."""
        if not connection.secret_ref:
            return None
        secret = db.query(CredentialSecret).filter(
            CredentialSecret.id == connection.secret_ref
        ).first()
        if not secret:
            return None
        return _decrypt(secret.encrypted_value)


def resolve_secret(db: Session, connection: IngestionConnection) -> Optional[str]:
    return ResolveSecret().execute(db, connection)
