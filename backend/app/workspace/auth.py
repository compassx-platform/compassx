"""Auth helpers. A caller is the principal named by a valid access token."""
from __future__ import annotations

import hashlib
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_account_db
from app.user_manager.auth_utils import hash_password as hash_password
from app.user_manager.auth_utils import verify_password as verify_password
from app.workspace.models import Principal


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


def _principal_for_token(token: str, db: Session) -> Principal:
    from app.user_manager.auth_utils import decode_access_token
    from app.user_manager.dependencies import get_effective_account_role
    from app.user_manager.models.account_models import UmUser

    try:
        payload = decode_access_token(token)
    except Exception as exc:
        raise ValueError(f"Invalid or expired token: {exc}") from exc

    user_id = payload.get("sub")
    if not user_id:
        raise ValueError("Invalid token payload")

    principal = (
        db.query(Principal)
        .filter(Principal.id == user_id, Principal.is_active == True)  # noqa: E712
        .first()
    )
    if principal is not None:
        return principal

    user = db.query(UmUser).filter(UmUser.id == user_id, UmUser.status == "active").first()
    if user is None:
        raise ValueError("User not found")
    role = get_effective_account_role(user.id, user.account_id, db)
    return Principal(
        id=user.id,
        account_id=user.account_id,
        type="user",
        email=user.email,
        name=user.display_name,
        is_account_admin=(role == "account_admin"),
        is_active=True,
    )


def get_current_principal(
    request: Request,
    db: Session = Depends(get_account_db),
) -> Principal:
    token = _extract_token(request)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        return _principal_for_token(token, db)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


def require_account_admin(principal: Principal = Depends(get_current_principal)) -> Principal:
    if not principal.is_account_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account admin required")
    return principal


def validate_bearer_token(token: str) -> Principal:
    """Validate a bearer token and return the Principal."""
    from app.database import AccountSessionLocal
    if AccountSessionLocal is None:
        raise RuntimeError("Account database not available")
    db = AccountSessionLocal()
    try:
        return _principal_for_token(token, db)
    finally:
        db.close()
