import logging
import base64

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Primary application database
    # All PG_* values must be supplied via environment variables (or .env file).
    # PG_DATABASE has no built-in default so that a misconfigured deployment
    # fails fast with a clear error instead of silently connecting to the wrong DB.
    PG_HOST: str = "localhost"
    PG_PORT: int = 5432
    PG_USER: str = "postgres"
    PG_PASSWORD: str = ""
    PG_DATABASE: str  # required – set via env var, e.g. PG_DATABASE=compassx

    # Data Catalog – Fernet encryption key for stored connection passwords.
    # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # If not set, a random key is generated at startup (passwords survive only until restart).
    CATALOG_ENCRYPTION_KEY: str = ""

    # Raw / time-series database (landing_zone) – may be same host, different DB
    PG_RAW_DATABASE: str = ""   # if empty, falls back to PG_DATABASE

    # Skip initial database connection tests (useful for fast startup if DB temporarily unavailable)
    SKIP_DB_INIT: bool = False

    # External services
    ASSET_MANAGER_BASE_URL: str = "http://localhost:8001"
    USER_MANAGER_BASE_URL: str = "http://localhost:8002"

    # CORS
    FRONTEND_ORIGIN: str = "http://localhost:5173"

    # Git
    ADO_PAT: str = ""
    INACTIVITY_TIMEOUT_MINUTES: int = 30

    # Workspace control plane (system DB).
    # If left empty, derived automatically from PG_* settings as:
    #   postgresql://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/compassx_account
    SYSTEM_DB_NAME: str = "compassx_account"   # override to use different DB name
    SYSTEM_DB_URL: str = ""                   # set this to override entirely
    SYSTEM_DB_POOL_MIN: int = 2
    SYSTEM_DB_POOL_MAX: int = 10

    # Workspace data plane (data DB).
    # If left empty, derived from PG_* settings as:
    #   postgresql://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/compassx_system
    DATA_DB_NAME: str = "compassx_system"       # override to use different DB name
    DATA_DB_URL: str = ""                     # set this to override entirely
    DATA_DB_POOL_MIN: int = 5
    DATA_DB_POOL_MAX: int = 20

    # Asset Manager database.
    # If left empty, derived from PG_* settings as:
    #   postgresql://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/asset_manager
    ASSET_DB_NAME: str = "asset_manager"       # override to use different DB name
    ASSET_DB_URL: str = ""                     # set this to override entirely
    ASSET_DB_POOL_MIN: int = 2
    ASSET_DB_POOL_MAX: int = 10

    # Redis for workspace slug cache and session cache
    REDIS_URL: str = ""

    # Workspace security
    SECRET_KEY: str = ""   # used to encrypt storage_config credentials
    SESSION_TTL_HOURS: int = 24

    # ── User Manager — JWT Auth ──────────────────────────────────────────────
    JWT_SECRET: str = "change-me-in-production-use-a-long-random-secret"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_TTL_MINUTES: int = 15
    REFRESH_TOKEN_TTL_DAYS: int = 30

    # First boot (if set, skips interactive prompt)
    ADMIN_EMAIL: str = ""
    ADMIN_PASSWORD: str = ""
    ACCOUNT_NAME: str = "CompassX"
    ACCOUNT_SLUG: str = "default"

    @property
    def resolved_system_db_url(self) -> str:
        """Return SYSTEM_DB_URL if set, otherwise derive from PG_* settings."""
        if self.SYSTEM_DB_URL:
            return self.SYSTEM_DB_URL
        return (
            f"postgresql://{self.PG_USER}:{self.PG_PASSWORD}"
            f"@{self.PG_HOST}:{self.PG_PORT}/{self.SYSTEM_DB_NAME}"
        )

    @property
    def resolved_data_db_url(self) -> str:
        """Return DATA_DB_URL if set, otherwise derive from PG_* settings."""
        if self.DATA_DB_URL:
            return self.DATA_DB_URL
        return (
            f"postgresql://{self.PG_USER}:{self.PG_PASSWORD}"
            f"@{self.PG_HOST}:{self.PG_PORT}/{self.DATA_DB_NAME}"
        )

    @property
    def resolved_asset_db_url(self) -> str:
        """Return ASSET_DB_URL if set, otherwise derive from PG_* settings."""
        if self.ASSET_DB_URL:
            return self.ASSET_DB_URL
        return (
            f"postgresql://{self.PG_USER}:{self.PG_PASSWORD}"
            f"@{self.PG_HOST}:{self.PG_PORT}/{self.ASSET_DB_NAME}"
        )

    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.PG_USER}:{self.PG_PASSWORD}"
            f"@{self.PG_HOST}:{self.PG_PORT}/{self.PG_DATABASE}"
        )

    @property
    def raw_database_url(self) -> str:
        """Connection URL for the raw/time-series database."""
        db = self.PG_RAW_DATABASE or self.PG_DATABASE
        return (
            f"postgresql://{self.PG_USER}:{self.PG_PASSWORD}"
            f"@{self.PG_HOST}:{self.PG_PORT}/{db}"
        )

    @property
    def catalog_fernet_key(self) -> bytes:
        """Return a valid 32-byte URL-safe base64 Fernet key."""
        if self.CATALOG_ENCRYPTION_KEY:
            return self.CATALOG_ENCRYPTION_KEY.encode()
        # Dev fallback: generate a deterministic key from PG_PASSWORD + PG_DATABASE
        # so it survives process restarts within the same config.
        seed = f"{self.PG_PASSWORD}:{self.PG_DATABASE}:catalog-key-v1"
        raw = seed.encode("utf-8")
        # Pad/hash to 32 bytes then base64-url-encode for Fernet
        import hashlib
        digest = hashlib.sha256(raw).digest()
        key = base64.urlsafe_b64encode(digest)
        # logger.warning(
        #     "CATALOG_ENCRYPTION_KEY not set – using derived key. "
        #     "Set CATALOG_ENCRYPTION_KEY in .env for production."
        # )
        return key

settings = Settings()
