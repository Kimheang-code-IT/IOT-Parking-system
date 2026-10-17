#!/usr/bin/env python3
"""
One-way, additive copy of the SQLite dev database into PostgreSQL.

Safety rules
------------
- The SQLite source is opened **read-only** (URI mode=ro) and is never modified.
- Rows are inserted only when their primary key does not exist in PostgreSQL
  (safe to re-run; no overwrites without --replace).
- ``--replace`` deletes rows in the migrated PostgreSQL tables first and
  requires ``--yes`` (explicit confirmation).
- After copying, row counts, primary keys and the paid-invoice total are
  validated and compared between source and target.

Usage (host, with psycopg2 installed):

    python -m scripts.migrate_sqlite_to_postgres --dry-run
    python -m scripts.migrate_sqlite_to_postgres \
        --target-url postgresql+psycopg2://iot_parking:PASS@localhost:5432/iot_parking

Inside Docker (target URL comes from the container environment):

    docker compose run --rm -v D:\\IOT-Parking\\backend\\data:/sqlite:ro \
        backend python -m scripts.migrate_sqlite_to_postgres --sqlite /sqlite/iot_parking.db

Validation mode is automatic; the SQLite file remains the backup.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import create_engine, func, select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.models import (  # noqa: E402
    BankSettings,
    DeviceCommand,
    DeviceLog,
    Invoice,
    IotDevice,
    ParkingSession,
    PaymentTransaction,
    RfidCard,
    RfidScanEvent,
)

# FK-safe copy order
COPY_ORDER = [
    IotDevice,
    BankSettings,
    ParkingSession,
    Invoice,
    PaymentTransaction,
    RfidCard,
    DeviceCommand,
    DeviceLog,
    RfidScanEvent,
]


def _normalize(value):
    """SQLite -> PostgreSQL friendly value conversions."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, datetime):
        if value.tzinfo is None:  # SQLite stores naive UTC
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, str):
        return value
    return value


def _is_numeric_column(column) -> bool:
    return type(column.type).__name__ in ("Numeric", "DECIMAL")


def copy_table(src_conn, dst_conn, model, *, replace: bool, dry_run: bool) -> dict:
    table = model.__table__
    pk = list(table.primary_key.columns)[0]

    rows = src_conn.execute(select(table)).mappings().all()
    existing = {
        row[0]
        for row in dst_conn.execute(select(pk)).all()
        if row[0] is not None
    }

    if replace and not dry_run:
        # delete in this table only; COPY_ORDER is FK-safe for inserts and the
        # caller deletes in reverse order beforehand.
        dst_conn.execute(table.delete())
        dst_conn.commit()
        existing = set()

    inserted = skipped = 0
    payload = []
    for row in rows:
        if row[pk.name] in existing:
            skipped += 1
            continue
        data = {}
        for column in table.columns:
            value = row[column.name]
            if value is not None and _is_numeric_column(column):
                value = Decimal(str(value))
            data[column.name] = _normalize(value)
        payload.append(data)

    if payload and not dry_run:
        dst_conn.execute(table.insert(), payload)
        dst_conn.commit()

    inserted = len(payload)
    return {
        "table": table.name,
        "source": len(rows),
        "inserted": inserted,
        "skipped": skipped,
        "target": dst_conn.execute(select(func.count()).select_from(table)).scalar() or 0,
    }


def _money_sum(conn, invoices) -> Decimal:
    value = conn.execute(
        select(func.coalesce(func.sum(invoices.c.amount), 0)).where(invoices.c.status == "Paid")
    ).scalar()
    return Decimal(str(value or 0))


def _fix_sequences(conn) -> None:
    """Advance PostgreSQL identity sequences past imported explicit IDs."""
    from sqlalchemy import Integer, text

    for model in COPY_ORDER:
        table = model.__table__
        pk = list(table.primary_key.columns)[0]
        if isinstance(pk.type, Integer) and pk.autoincrement:
            conn.execute(
                text(
                    "SELECT setval(pg_get_serial_sequence(:tbl, :col), "
                    "COALESCE((SELECT MAX(" + pk.name + ") FROM " + table.name + "), 0) + 1, false)"
                ),
                {"tbl": table.name, "col": pk.name},
            )
    conn.commit()


def main() -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Copy SQLite data into PostgreSQL (additive).")
    parser.add_argument(
        "--sqlite",
        type=Path,
        default=BACKEND_ROOT / "data" / "iot_parking.db",
        help="Path to the SQLite database file (default: backend/data/iot_parking.db)",
    )
    parser.add_argument(
        "--target-url",
        default=settings.database_url,
        help="PostgreSQL SQLAlchemy URL (default: current DATABASE_URL)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Report only, write nothing")
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Delete existing target rows for the migrated tables before copying",
    )
    parser.add_argument("--yes", action="store_true", help="Confirm --replace (required)")
    args = parser.parse_args()

    if not args.sqlite.exists():
        print(f"[migrate-data] SQLite file not found: {args.sqlite}")
        return 2

    if args.replace and not args.yes:
        print("[migrate-data] --replace deletes all rows in the target tables; re-run with --yes")
        return 2

    if args.target_url.startswith("sqlite"):
        print("[migrate-data] Target URL is SQLite — set DATABASE_URL to PostgreSQL first.")
        return 2

    src_engine = create_engine(f"sqlite:///file:{args.sqlite.as_posix()}?mode=ro&uri=true")
    dst_engine = create_engine(args.target_url, pool_pre_ping=True)

    print(f"[migrate-data] source : {args.sqlite} (read-only)")
    print(f"[migrate-data] target : {dst_engine.url.render_as_string(hide_password=True)}")
    if args.dry_run:
        print("[migrate-data] DRY RUN — no writes")

    with src_engine.connect() as src, dst_engine.connect() as dst:
        if args.replace and not args.dry_run:
            print("[migrate-data] --replace: deleting target rows (reverse FK order) ...")
            for model in reversed(COPY_ORDER):
                dst.execute(model.__table__.delete())
            dst.commit()

        results = []
        for model in COPY_ORDER:
            result = copy_table(src, dst, model, replace=False, dry_run=args.dry_run)
            results.append(result)
            print(
                f"  {result['table']:<24} source={result['source']:<5} "
                f"inserted={result['inserted']:<5} skipped={result['skipped']:<5} target={result['target']}"
            )

        if not args.dry_run:
            _fix_sequences(dst)

        # ---- validation -------------------------------------------------
        failures = 0
        if args.dry_run:
            print("\n[migrate-data] DRY RUN — validation is skipped (nothing was written).")
            print("[migrate-data] Re-run without --dry-run to copy and validate.")
            return 0

        for model, result in zip(COPY_ORDER, results):
            if result["target"] < result["source"]:
                print(f"  [FAIL] {result['table']}: target has fewer rows than source")
                failures += 1
            missing = 0
            pk = list(model.__table__.primary_key.columns)[0]
            src_keys = {r[0] for r in src.execute(select(pk)).all()}
            tgt_keys = {r[0] for r in dst.execute(select(pk)).all()}
            missing = len(src_keys - tgt_keys)
            if missing:
                print(f"  [FAIL] {result['table']}: {missing} source keys missing in target")
                failures += 1

        src_paid = _money_sum(src, Invoice.__table__)
        dst_paid = _money_sum(dst, Invoice.__table__)
        src_active = src.execute(
            select(func.count()).select_from(ParkingSession.__table__).where(
                ParkingSession.__table__.c.status == "Active"
            )
        ).scalar() or 0
        dst_active = dst.execute(
            select(func.count()).select_from(ParkingSession.__table__).where(
                ParkingSession.__table__.c.status == "Active"
            )
        ).scalar() or 0

        print("\n[migrate-data] validation")
        print(f"  paid invoice totals : SQLite ${src_paid:.2f}  ->  PostgreSQL ${dst_paid:.2f}")
        print(f"  active sessions     : SQLite {src_active}  ->  PostgreSQL {dst_active}")
        if dst_paid < src_paid:
            print("  [FAIL] PostgreSQL paid total is lower than SQLite")
            failures += 1

    print(f"\n[migrate-data] {'completed with failures' if failures else 'completed successfully'}")
    print("[migrate-data] SQLite file was NOT modified and remains the rollback source.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
