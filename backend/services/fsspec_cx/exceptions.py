"""Error mapping for volume access."""


def map_resolve_error(error_code: str, message: str) -> Exception:
    """Map /volumes/resolve error codes to Python exceptions."""
    mapping = {
        "VOLUME_NOT_FOUND": FileNotFoundError,
        "PERMISSION_DENIED": PermissionError,
        "TOKEN_INVALID_OR_EXPIRED": PermissionError,
        "CREDENTIAL_MINT_FAILED": OSError,
    }
    exc_class = mapping.get(error_code, OSError)
    return exc_class(f"[{error_code}] {message}")


class VolumeAccessError(Exception):
    """Base exception for volume access errors."""
    pass
