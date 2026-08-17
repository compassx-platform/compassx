"""Workspace startup: run Alembic migrations then first-boot initialiser.

Called once from app lifespan. Idempotent.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def _run_alembic(config_file: str, db_url: str) -> None:
    """Run `alembic upgrade head` for a given config file and DB URL."""
    from alembic.config import Config
    from alembic import command

    # Config file path is relative to the backend/ directory
    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    cfg_path = os.path.join(backend_dir, config_file)

    cfg = Config(cfg_path)
    cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(cfg, "head")
    logger.info("Alembic upgrade head complete: %s", config_file)


def run_workspace_startup() -> None:
    """Run system DB migrations, data DB migrations, then first boot."""
    from app.config import settings
    from app.database import AccountSessionLocal

    # Automatic Alembic migrations on startup are disabled to prevent server boot hanging.
    # Run alembic migrations manually via CLI when necessary.
    logger.info("Automatic startup Alembic migrations skipped.")

    # 3. First boot (create account + admin + system catalog if empty)
    if AccountSessionLocal is None:
        logger.error("AccountSessionLocal not initialised — skipping first boot")
        return

    try:
        from app.workspace.first_boot import FirstBootRunner
        runner = FirstBootRunner(settings.resolved_system_db_url)
        db = AccountSessionLocal()
        try:
            runner.run(db)
        finally:
            db.close()
    except Exception:
        logger.exception("FirstBootRunner failed")
        raise
