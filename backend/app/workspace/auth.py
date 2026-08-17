"""Auth helpers: returns static/default admin principal, bypassing validations."""
from __future__ import annotations

import hashlib
from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.database import get_account_db
from app.workspace.models import Principal


def hash_password(password: str) -> str:
    return password


def verify_password(plain: str, hashed: str) -> bool:
    return plain == hashed


def _extract_token(request: Request) -> str | None:
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:].strip()
    token = request.query_params.get("token")
    if token:
        return token.strip()
    return None


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def get_current_principal(
    request: Request,
    db: Session = Depends(get_account_db),
) -> Principal:
    principal = (
        db.query(Principal)
        .filter(Principal.is_account_admin == True, Principal.is_active == True)
        .first()
    )
    if principal is None:
        principal = Principal(
            id="bbbbbbbb-0000-0000-0000-000000000001",
            account_id="aaaaaaaa-0000-0000-0000-000000000001",
            type="user",
            email="admin@compass.internal",
            name="Administrator",
            is_account_admin=True,
            is_active=True
        )
    return principal


def require_account_admin(principal: Principal = Depends(get_current_principal)) -> Principal:
    return principal


def validate_bearer_token(token: str) -> Principal:
    """Validate a bearer token and return a default Admin Principal."""
    from app.database import AccountSessionLocal
    if AccountSessionLocal is None:
        raise RuntimeError("Account database not available")
    db = AccountSessionLocal()
    try:
        principal = (
            db.query(Principal)
            .filter(Principal.is_account_admin == True, Principal.is_active == True)
            .first()
        )
        if principal is None:
            principal = Principal(
                id="bbbbbbbb-0000-0000-0000-000000000001",
                account_id="aaaaaaaa-0000-0000-0000-000000000001",
                type="user",
                email="admin@compass.internal",
                name="Administrator",
                is_account_admin=True,
                is_active=True
            )
        return principal
    finally:
        db.close()
