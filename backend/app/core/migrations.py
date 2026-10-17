"""Lightweight SQLite column migrations (no Alembic)."""

import logging

from sqlalchemy import inspect, text

from app.core.config import get_settings
from app.core.database import SessionLocal, engine
from app.models.invoice import Invoice
from app.utils.exit_verify_utils import VERIFY_HASH_LENGTH, generate_exit_verify_hash

logger = logging.getLogger(__name__)


def run_schema_migrations() -> None:
    settings = get_settings()
    if not settings.is_sqlite:
        return

    inspector = inspect(engine)
    tables = inspector.get_table_names()

    if "invoices" in tables:
        columns = {col["name"] for col in inspector.get_columns("invoices")}
        if "exit_verify_hash" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE invoices ADD COLUMN exit_verify_hash VARCHAR(32)"))
                conn.execute(
                    text(
                        "CREATE UNIQUE INDEX IF NOT EXISTS ix_invoices_exit_verify_hash "
                        "ON invoices (exit_verify_hash)"
                    )
                )
            logger.info("Added invoices.exit_verify_hash column")

        _backfill_exit_verify_hashes(settings.exit_verify_secret)

    if "device_commands" in tables:
        command_columns = {col["name"] for col in inspector.get_columns("device_commands")}
        if "expires_at" not in command_columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE device_commands ADD COLUMN expires_at DATETIME"))
            logger.info("Added device_commands.expires_at column")


def _backfill_exit_verify_hashes(secret: str) -> None:
    db = SessionLocal()
    try:
        rows = db.query(Invoice).all()
        updated: list[Invoice] = []
        for invoice in rows:
            current = (invoice.exit_verify_hash or "").strip()
            if current and len(current) == VERIFY_HASH_LENGTH:
                continue
            invoice.exit_verify_hash = generate_exit_verify_hash(
                invoice_id=invoice.id,
                session_id=invoice.session_id,
                license_plate=invoice.license_plate,
                secret=secret,
            )
            updated.append(invoice)
        if updated:
            db.commit()
            logger.info("Backfilled exit_verify_hash for %s invoice(s)", len(updated))
    finally:
        db.close()
