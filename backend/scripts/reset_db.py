"""
Wipe all test data and recreate a fresh SQLite database.

Keeps schema + IoT device registry + bank settings. Does not add demo sessions unless --demo.

Stop the API server first (uvicorn), then run from backend/:

  python scripts/reset_db.py
  python scripts/reset_db.py --demo   # optional sample sessions for UI testing
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.bootstrap import bootstrap_database
from app.core.config import get_settings
from app.core.database import SessionLocal, engine
from app.core.migrations import run_schema_migrations
from app.models.device_log import DeviceLog
from app.models.invoice import Invoice
from app.models.parking_session import ParkingSession
from app.models.payment_transaction import PaymentTransaction


def _unlink_sqlite(path: Path) -> None:
    for candidate in (path, Path(f"{path}-wal"), Path(f"{path}-shm")):
        if candidate.exists():
            candidate.unlink()
            print(f"  Removed {candidate}")


def _clear_all_rows() -> None:
    """Delete transactional data while the DB file stays open (e.g. uvicorn running)."""
    db = SessionLocal()
    try:
        db.query(DeviceLog).delete()
        db.query(PaymentTransaction).delete()
        db.query(Invoice).delete()
        db.query(ParkingSession).delete()
        db.commit()
        print("  Cleared sessions, invoices, payments, and device logs.")
    finally:
        db.close()


def reset_db(*, seed_demo: bool = False) -> None:
    settings = get_settings()
    engine.dispose()

    if not (settings.is_sqlite and settings.sqlite_path):
        print("reset_db.py only supports SQLite. For PostgreSQL, truncate tables manually.")
        sys.exit(1)

    file_reset = False
    if settings.sqlite_path.exists():
        print(f"Resetting database at {settings.sqlite_path}")
        try:
            _unlink_sqlite(settings.sqlite_path)
            file_reset = True
        except PermissionError:
            print("  Database file is in use — clearing all rows instead.")
            print("  (Stop uvicorn and run again to delete the file completely.)")
            _clear_all_rows()
    else:
        print("No database file found — creating a new one.")
        file_reset = True

    if file_reset:
        bootstrap_database(seed_demo=seed_demo)
    else:
        run_schema_migrations()
        if seed_demo:
            from scripts.seed import seed_demo_sessions

            db = SessionLocal()
            try:
                seed_demo_sessions(db)
                db.commit()
            finally:
                db.close()
    print()
    print("Database reset complete.")
    if seed_demo:
        print("  Demo parking sessions and invoices were added.")
    else:
        print("  Empty — no sessions or invoices. IoT devices and bank settings are ready.")
    print("  Restart the API: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")


def main() -> None:
    parser = argparse.ArgumentParser(description="Delete all parking test data and recreate the DB.")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="After reset, load sample sessions (same as scripts/seed.py demo data)",
    )
    args = parser.parse_args()
    reset_db(seed_demo=args.demo)


if __name__ == "__main__":
    main()
