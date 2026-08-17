import os
import jwt

JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-secret-key-replace-me-in-prod")
JWT_ALGORITHM = "HS256"

def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(
            token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM], audience="core-opus"
        )
    except jwt.PyJWTError:
        return None
