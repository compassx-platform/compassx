from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.ingestion.connection.repository import get_connection
from app.ingestion.infrastructure.secret_box import _encrypt
from app.ingestion.models import CredentialSecret


class RotateConnectionSecret:
    def execute(
        self,
        db: Session,
        workspace_id: UUID,
        connection_id: UUID,
        new_secret_value: str,
    ) -> None:
        """Replace (or create) the credential_secret for this connection."""
        conn = get_connection(db, workspace_id, connection_id)

        if conn.secret_ref:
            # Update existing secret row
            secret = db.query(CredentialSecret).filter(
                CredentialSecret.id == conn.secret_ref
            ).first()
            if secret:
                secret.encrypted_value = _encrypt(new_secret_value)
                secret.encryption_key_version = 1
            else:
                # orphaned ref — create fresh
                secret = CredentialSecret(
                    id=uuid4(),
                    workspace_id=workspace_id,
                    encrypted_value=_encrypt(new_secret_value),
                    encryption_key_version=1,
                )
                db.add(secret)
                db.flush()
                conn.secret_ref = secret.id
        else:
            secret = CredentialSecret(
                id=uuid4(),
                workspace_id=workspace_id,
                encrypted_value=_encrypt(new_secret_value),
                encryption_key_version=1,
            )
            db.add(secret)
            db.flush()
            conn.secret_ref = secret.id

        db.commit()


def rotate_connection_secret(
    db: Session,
    workspace_id: UUID,
    connection_id: UUID,
    new_secret_value: str,
) -> None:
    return RotateConnectionSecret().execute(db, workspace_id, connection_id, new_secret_value)
