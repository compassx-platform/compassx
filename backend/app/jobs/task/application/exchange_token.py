import uuid

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.jobs.models.run_trace import ExecutionToken
from app.jobs.security import generate_execution_token, utcnow, verify_internal_secret


class ExchangeToken:
    def execute(self, token_ref: str, secret: str | None, db: Session):
        verify_internal_secret(secret)
        try:
            token_id = uuid.UUID(token_ref)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail="Execution token not found") from exc
        token = db.query(ExecutionToken).filter(
            ExecutionToken.token_id == token_id
        ).with_for_update().first()
        if not token:
            raise HTTPException(status_code=404, detail="Execution token not found")
        if token.exchanged_at is not None or token.expires_at <= utcnow():
            raise HTTPException(status_code=410, detail="Execution token is expired or already exchanged")
        raw, token_hash = generate_execution_token()
        token.token_hash = token_hash
        token.exchanged_at = utcnow()
        db.commit()
        return {"access_token": raw, "expires_at": token.expires_at}


def exchange_token(token_ref, secret, db):
    return ExchangeToken().execute(token_ref, secret, db)
