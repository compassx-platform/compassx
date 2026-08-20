"""Catalog Connection Service (CRUD, encryption, live test verification, client resolution)."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, List, Optional
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.catalog.models import (
    UnifiedCatalog,
    UnifiedCatalogConnection,
    UnifiedCatalogSchema,
)
from app.catalog.connections.base_provider import ConnectionTestResult
from app.catalog.connections.registry import registry
from app.catalog.connections.schemas import (
    CatalogConnectionCreate,
    CatalogConnectionUpdate,
    ConnectionTestRequest,
)
from app.agents.services.encryption import decrypt_field, encrypt_field

logger = logging.getLogger(__name__)


def _normalize_auth_config_to_cipher(auth_config: Any) -> Optional[str]:
    """Serialize and encrypt credentials dict/string using Fernet."""
    if not auth_config:
        return None
    try:
        if isinstance(auth_config, (dict, list)):
            plaintext = json.dumps(auth_config)
        else:
            plaintext = str(auth_config)
        return encrypt_field(plaintext)
    except Exception as exc:
        logger.error("Failed to encrypt connection auth_config: %s", exc)
        return None


_schema_ensured = False


def _ensure_table_schema(db: Session) -> None:
    global _schema_ensured
    if _schema_ensured:
        return
    try:
        bind = db.get_bind()
        if bind and "sqlite" not in str(bind.engine.url):
            for col in ["schema_id", "catalog_name", "schema_name"]:
                try:
                    db.execute(text(f"ALTER TABLE catalog_v2_connections ALTER COLUMN {col} DROP NOT NULL;"))
                except Exception:
                    pass
            is_gen = db.execute(text("""
                SELECT is_generated FROM information_schema.columns 
                WHERE table_name = 'catalog_v2_connections' AND column_name = 'full_name'
            """)).scalar()
            if is_gen and str(is_gen).upper() in ("ALWAYS", "YES", "TRUE"):
                db.execute(text("ALTER TABLE catalog_v2_connections DROP COLUMN full_name;"))
                db.execute(text("ALTER TABLE catalog_v2_connections ADD COLUMN full_name VARCHAR(765);"))
                db.execute(text("UPDATE catalog_v2_connections SET full_name = COALESCE(catalog_name || '.' || schema_name || '.' || name, name);"))
            db.commit()
        _schema_ensured = True
    except Exception as exc:
        logger.debug("catalog_v2_connections schema ensure non-fatal: %s", exc)
        _schema_ensured = True


class CatalogConnectionService:
    """Service layer managing Unified Catalog Connections."""

    def get_decrypted_auth_config(self, conn: UnifiedCatalogConnection) -> Optional[Any]:
        """Decrypt connection credentials in-memory for secure backend dispatch."""
        if not conn or not conn.auth_config:
            return None
        try:
            plaintext = decrypt_field(conn.auth_config)
            if not plaintext:
                return None
            try:
                return json.loads(plaintext)
            except Exception:
                return plaintext
        except Exception as exc:
            logger.warning("Failed to decrypt connection auth_config for '%s': %s", conn.name, exc)
            return None

    def create_connection(
        self,
        db: Session,
        data: CatalogConnectionCreate,
        user_id: str = "default_user",
    ) -> UnifiedCatalogConnection:
        """Create a new first-class catalog connection under catalog.schema.name or account-level."""
        _ensure_table_schema(db)
        catalog_name = data.catalog.strip().lower() if data.catalog and data.catalog.strip() else None
        schema_name = data.schema_name.strip().lower() if data.schema_name and data.schema_name.strip() else None
        conn_name = data.name.strip()

        schema_id = None
        full_name = conn_name

        if catalog_name and schema_name:
            # 1. Resolve or create catalog
            catalog = db.query(UnifiedCatalog).filter(UnifiedCatalog.name == catalog_name).first()
            if not catalog:
                catalog = UnifiedCatalog(
                    name=catalog_name,
                    description=f"{catalog_name.capitalize()} catalog",
                    created_by=user_id,
                )
                db.add(catalog)
                db.commit()
                db.refresh(catalog)

            # 2. Resolve or create schema
            schema = (
                db.query(UnifiedCatalogSchema)
                .filter(
                    UnifiedCatalogSchema.catalog_id == catalog.id,
                    UnifiedCatalogSchema.name == schema_name,
                )
                .first()
            )
            if not schema:
                schema = UnifiedCatalogSchema(
                    catalog_id=catalog.id,
                    name=schema_name,
                    description=f"{schema_name} schema",
                    created_by=user_id,
                )
                db.add(schema)
                db.commit()
                db.refresh(schema)

            schema_id = schema.id
            full_name = f"{catalog_name}.{schema_name}.{conn_name}"

            # 3. Check for duplicates in same catalog.schema
            existing = (
                db.query(UnifiedCatalogConnection)
                .filter(
                    UnifiedCatalogConnection.catalog_name == catalog_name,
                    UnifiedCatalogConnection.schema_name == schema_name,
                    UnifiedCatalogConnection.name == conn_name,
                )
                .first()
            )
            if existing:
                raise ValueError(f"A connection named '{conn_name}' already exists in '{catalog_name}.{schema_name}'.")
        else:
            # Account-level: Check for duplicates among account-level connections
            existing = (
                db.query(UnifiedCatalogConnection)
                .filter(
                    UnifiedCatalogConnection.schema_id.is_(None),
                    UnifiedCatalogConnection.name == conn_name,
                )
                .first()
            )
            if existing:
                raise ValueError(f"An account-level connection named '{conn_name}' already exists.")

        # 4. Resolve provider & category
        provider = registry.get(data.connector_type)
        category = data.category or (provider.category if provider else "database")

        # 5. Encrypt credentials
        encrypted_auth = _normalize_auth_config_to_cipher(data.auth_config)

        conn = UnifiedCatalogConnection(
            id=str(uuid.uuid4()),
            schema_id=schema_id,
            catalog_name=catalog_name,
            schema_name=schema_name,
            name=conn_name,
            full_name=full_name,
            category=category,
            connector_type=data.connector_type,
            description=data.description,
            config=data.config or {},
            auth_config=encrypted_auth,
            status=data.status or "active",
            owner=user_id,
            created_by=user_id,
            updated_by=user_id,
        )
        db.add(conn)
        db.commit()
        db.refresh(conn)
        return conn

    def get_connection(
        self,
        db: Session,
        connection_id_or_fqn: str,
    ) -> Optional[UnifiedCatalogConnection]:
        """Fetch connection by UUID or 3-part FQN (catalog.schema.name)."""
        query = db.query(UnifiedCatalogConnection)
        if "." in connection_id_or_fqn:
            parts = connection_id_or_fqn.split(".")
            if len(parts) == 3:
                cat, sch, name = parts
                return query.filter(
                    UnifiedCatalogConnection.catalog_name == cat,
                    UnifiedCatalogConnection.schema_name == sch,
                    UnifiedCatalogConnection.name == name,
                ).first()
        # By ID or name fallback
        return query.filter(
            or_(
                UnifiedCatalogConnection.id == connection_id_or_fqn,
                UnifiedCatalogConnection.name == connection_id_or_fqn,
            )
        ).first()

    def list_connections(
        self,
        db: Session,
        catalog_name: Optional[str] = None,
        schema_name: Optional[str] = None,
        category: Optional[str] = None,
        connector_type: Optional[str] = None,
        status: Optional[str] = None,
        search_query: Optional[str] = None,
    ) -> List[UnifiedCatalogConnection]:
        """List connections with optional search and category filters."""
        query = db.query(UnifiedCatalogConnection)
        if catalog_name:
            query = query.filter(UnifiedCatalogConnection.catalog_name == catalog_name.strip().lower())
        if schema_name:
            query = query.filter(UnifiedCatalogConnection.schema_name == schema_name.strip().lower())
        if category:
            query = query.filter(UnifiedCatalogConnection.category == category.strip().lower())
        if connector_type:
            query = query.filter(UnifiedCatalogConnection.connector_type == connector_type.strip().lower())
        if status:
            query = query.filter(UnifiedCatalogConnection.status == status.strip().lower())
        if search_query:
            term = f"%{search_query.strip()}%"
            query = query.filter(
                or_(
                    UnifiedCatalogConnection.name.ilike(term),
                    UnifiedCatalogConnection.full_name.ilike(term),
                    UnifiedCatalogConnection.connector_type.ilike(term),
                    UnifiedCatalogConnection.description.ilike(term),
                )
            )

        return query.order_by(UnifiedCatalogConnection.created_at.desc()).all()

    def update_connection(
        self,
        db: Session,
        connection_id: str,
        data: CatalogConnectionUpdate,
        user_id: str = "default_user",
    ) -> Optional[UnifiedCatalogConnection]:
        """Update connection configuration or credentials."""
        conn = self.get_connection(db, connection_id)
        if not conn:
            return None

        if data.description is not None:
            conn.description = data.description
        if data.config is not None:
            conn.config = data.config
        if data.status is not None:
            conn.status = data.status
        if data.auth_config is not None:
            conn.auth_config = _normalize_auth_config_to_cipher(data.auth_config)

        conn.updated_by = user_id
        db.commit()
        db.refresh(conn)
        return conn

    def toggle_status(
        self,
        db: Session,
        connection_id: str,
    ) -> Optional[UnifiedCatalogConnection]:
        """Toggle active / disabled status."""
        conn = self.get_connection(db, connection_id)
        if not conn:
            return None
        conn.status = "disabled" if conn.status == "active" else "active"
        db.commit()
        db.refresh(conn)
        return conn

    def delete_connection(
        self,
        db: Session,
        connection_id: str,
    ) -> bool:
        """Delete a catalog connection."""
        conn = self.get_connection(db, connection_id)
        if not conn:
            return False
        db.delete(conn)
        db.commit()
        return True

    def test_connection(
        self,
        db: Session,
        req: ConnectionTestRequest,
    ) -> ConnectionTestResult:
        """Test a connection either from existing ID or an in-flight test payload."""
        if req.connection_id:
            conn = self.get_connection(db, req.connection_id)
            if not conn:
                return ConnectionTestResult(success=False, message="Connection not found")
            provider = registry.get(conn.connector_type)
            if not provider:
                return ConnectionTestResult(success=False, message=f"No provider found for '{conn.connector_type}'")
            auth = self.get_decrypted_auth_config(conn)
            return provider.test_connection(conn.config, auth)

        if not req.connector_type:
            return ConnectionTestResult(success=False, message="Connector type is required for testing")

        provider = registry.get(req.connector_type)
        if not provider:
            return ConnectionTestResult(success=False, message=f"Unsupported connector type: '{req.connector_type}'")

        config = req.config or {}
        auth = req.auth_config
        return provider.test_connection(config, auth)


connection_service = CatalogConnectionService()
