#!/usr/bin/env python3
"""
Apply the database schema + baseline data for the current DATABASE_URL.

Used by the infrastructure `migrate` one-off service and safe to run manually:

    python -m scripts.run_migrations

Behaviour (never destructive):
  - fresh database                -> alembic upgrade head (creates the schema)
  - database bootstrapped by the  -> alembic stamp head (create_all already
    application (create_all)          produced an identical schema)
  - already alembic-managed       -> alembic upgrade head
  - no alembic revisions present  -> falls back to create_all bootstrap

Afterwards `bootstrap_database()` seeds baseline rows (IoT devices, bank
settings) when they are missing. It never deletes data.
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import inspect  # noqa: E402

from app.core.bootstrap import bootstrap_database  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.database import engine  # noqa: E402

APP_TABLES = {"parking_sessions", "invoices", "iot_devices", "rfid_cards"}


def _alembic_config() -> Config:
    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    return cfg


def _has_revisions() -> bool:
    versions = BACKEND_ROOT / "alembic" / "versions"
    return versions.is_dir() and any(versions.glob("*.py"))


def main() -> int:
    settings = get_settings()
    print(f"[migrate] target       : {settings.safe_database_url}")
    print(f"[migrate] environment  : {settings.app_env}")

    tables = set(inspect(engine).get_table_names())

    if not _has_revisions():
        print("[migrate] no alembic revisions found — using SQLAlchemy create_all bootstrap")
        bootstrap_database()
        print("[migrate] schema ensured (create_all + seed).")
        return 0

    cfg = _alembic_config()

    if "alembic_version" in tables:
        print("[migrate] alembic-managed database -> upgrade head")
        command.upgrade(cfg, "head")
    elif tables & APP_TABLES:
        print("[migrate] existing create_all schema detected -> stamping head (no schema changes)")
        command.stamp(cfg, "head")
    else:
        print("[migrate] empty database -> alembic upgrade head (creating schema)")
        command.upgrade(cfg, "head")

    print("[migrate] ensuring baseline rows (IoT devices, bank settings) ...")
    bootstrap_database()

    print("[migrate] current revision:")
    command.current(cfg)
    print("[migrate] done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
