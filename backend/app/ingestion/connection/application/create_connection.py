from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.ingestion.infrastructure.secret_box import _encrypt
from app.ingestion.models import CredentialSecret, IngestionConnection


class CreateConnection:
    def execute(
        self,
        db: Session,
        workspace_id: UUID,
        name: str,
        base_url: str,
        auth_type: str,
        auth_config: dict,
        secret_value: Optional[str],
        default_headers: dict,
        rate_limit_rps: float,
        max_concurrency: int,
        created_by: UUID,
        description: Optional[str] = None,
    ) -> IngestionConnection:
        """Create a new Connection, storing any secret encrypted in credential_secret."""

        secret_ref = None
        if secret_value:
            secret = CredentialSecret(
                id=uuid4(),
                workspace_id=workspace_id,
                encrypted_value=_encrypt(secret_value),
                encryption_key_version=1,
            )
            db.add(secret)
            db.flush()
            secret_ref = secret.id

        conn = IngestionConnection(
            id=uuid4(),
            workspace_id=workspace_id,
            name=name,
            description=description,
            base_url=base_url,
            auth_type=auth_type,
            auth_config=auth_config,
            secret_ref=secret_ref,
            default_headers=default_headers,
            rate_limit_rps=rate_limit_rps,
            max_concurrency=max_concurrency,
            created_by=created_by,
        )
        db.add(conn)
        db.commit()
        db.refresh(conn)
        return conn


def create_connection(
    db: Session,
    workspace_id: UUID,
    name: str,
    base_url: str,
    auth_type: str,
    auth_config: dict,
    secret_value: Optional[str],
    default_headers: dict,
    rate_limit_rps: float,
    max_concurrency: int,
    created_by: UUID,
    description: Optional[str] = None,
) -> IngestionConnection:
    return CreateConnection().execute(
        db,
        workspace_id,
        name,
        base_url,
        auth_type,
        auth_config,
        secret_value,
        default_headers,
        rate_limit_rps,
        max_concurrency,
        created_by,
        description,
    )
