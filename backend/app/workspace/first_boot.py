"""First boot initialiser for CompassX workspace/account layer.

Idempotent — safe to re-run. Steps per spec section 6:
  1. Check if accounts table already has a row (FIRST_BOOT_COMPLETE signal)
  2. If empty, create account + admin principal
  3. Auto-register system catalog
  4. Create default 'public' schema in system catalog
"""
from __future__ import annotations

import logging
import os
from uuid import uuid4

from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import settings
from app.workspace.models import (
    Account,
    Principal,
    WorkspaceCatalog,
    WorkspaceCatalogSchema,
)

logger = logging.getLogger(__name__)

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

FIRST_BOOT_MARKER = ".compassx_first_boot_complete"


class FirstBootRunner:
    """Idempotent first boot setup.

    Call `run(db)` at application startup with a system DB session.
    """

    def __init__(self, system_db_url: str) -> None:
        self._system_db_url = system_db_url

    def run(self, db: Session) -> None:
        # Already booted?
        if db.query(Account).first() is not None:
            logger.info("FirstBoot: account already exists — skipping")
            return

        logger.info("FirstBoot: no account found — running first boot setup")

        account_name = settings.ACCOUNT_NAME or "CompassX"
        account_slug = settings.ACCOUNT_SLUG or "default"
        admin_email = settings.ADMIN_EMAIL
        admin_password = settings.ADMIN_PASSWORD

        if not admin_email or not admin_password:
            # Fallback: use well-known dev credentials so the app can start in dev mode.
            logger.warning(
                "FirstBoot: ADMIN_EMAIL/ADMIN_PASSWORD not set — using dev defaults "
                "(admin@compass.internal / Admin@123456). Set these env vars in production."
            )
            admin_email = admin_email or "admin@compass.internal"
            admin_password = admin_password or "Admin@123456"

        account_id = str(uuid4())
        principal_id = str(uuid4())

        # Step 5: Insert account
        account = Account(
            id=account_id,
            name=account_name,
            slug=account_slug,
        )
        db.add(account)
        db.flush()

        # Step 6: Insert admin principal
        pw_hash = _pwd_ctx.hash(admin_password)
        admin = Principal(
            id=principal_id,
            account_id=account_id,
            type="user",
            email=admin_email,
            name="Administrator",
            password_hash=pw_hash,
            is_account_admin=True,
        )
        db.add(admin)
        db.flush()

        # Step 7: Auto-register system catalog (foreign_postgres pointing at system DB)
        system_catalog_id = str(uuid4())
        system_catalog = WorkspaceCatalog(
            id=system_catalog_id,
            account_id=account_id,
            name="system",
            type="foreign_postgres",
            connection_url=self._system_db_url,
            is_system=True,
        )
        db.add(system_catalog)
        db.flush()

        # Step 8: Create default schema in system catalog
        db.add(WorkspaceCatalogSchema(
            catalog_id=system_catalog_id,
            name="public",
        ))

        db.commit()
        logger.info(
            "FirstBoot: complete — account '%s', admin '%s', system catalog registered",
            account_name,
            admin_email,
        )
