"""User Manager — JWT + password hashing utilities."""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone, timedelta

import jwt
from passlib.context import CryptContext

from app.config import settings

# ---------------------------------------------------------------------------
# Password hashing (argon2 via passlib)
# ---------------------------------------------------------------------------
_pwd_ctx = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(plain: str) -> str:
    return _pwd_ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _pwd_ctx.verify(plain, hashed)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Access tokens (short-lived JWT, 15 min default)
# ---------------------------------------------------------------------------

def create_access_token(
    user_id: str,
    account_id: str,
    account_roles: list[str],
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "account_id": account_id,
        "account_roles": account_roles,
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_TTL_MINUTES),
        "type": "access",
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decode and validate an access token.  Raises jwt.PyJWTError on failure."""
    return jwt.decode(
        token,
        settings.JWT_SECRET,
        algorithms=[settings.JWT_ALGORITHM],
    )


# ---------------------------------------------------------------------------
# Refresh tokens (opaque — stored hashed in DB)
# ---------------------------------------------------------------------------

def generate_refresh_token() -> str:
    """Generate a cryptographically secure opaque token string."""
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    """SHA-256 hash of an opaque refresh token (fast — not a password)."""
    return hashlib.sha256(token.encode()).hexdigest()
