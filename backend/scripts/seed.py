"""Reload demo parking sessions (skips if sessions already exist)."""

import sys
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.orm import Session

from app.core.bootstrap import bootstrap_database
from app.core.database import SessionLocal
from app.models.invoice import Invoice
from app.models.parking_session import ParkingSession
from app.utils.datetime_utils import utc_now
from app.utils.id_generator import next_invoice_id, next_parking_session_id


def seed_demo_sessions(db: Session) -> None:
    if db.query(ParkingSession).count() > 0:
        return
    now = utc_now()
    completed = ParkingSession(
        id=next_parking_session_id(db),
        license_plate="2A-1234",
        vehicle_type="Car",
        vehicle_description="Black SUV",
        entry_time=now - timedelta(hours=3),
        exit_time=now - timedelta(hours=1),
        duration_display="2h 00m",
        status="Completed",
        fee_amount=Decimal("4.00"),
        rate_per_hour=Decimal("2.00"),
        created_at=now,
        updated_at=now,
    )
    db.add(completed)
    db.flush()
    active = ParkingSession(
        id=next_parking_session_id(db),
        license_plate="1B-5678",
        vehicle_type="Motorcycle",
        vehicle_description="Red Scooter",
        entry_time=now - timedelta(minutes=45),
        exit_time=None,
        duration_display="-",
        status="Active",
        fee_amount=None,
        rate_per_hour=Decimal("2.00"),
        created_at=now,
        updated_at=now,
    )
    db.add(active)
    db.flush()
    db.add(
        Invoice(
            id=next_invoice_id(db),
            session_id=completed.id,
            invoice_date=now.date(),
            license_plate=completed.license_plate,
            amount=Decimal("4.00"),
            method="ABA",
            status="Paid",
            transaction_ref="TRX-100001-POS",
            created_at=now,
        )
    )

    # Add completed Car/Motorcycle/Truck sessions for the last 12 hours (every 2 hours)
    for i in range(1, 7):
        entry_time = now - timedelta(hours=i * 2)
        exit_time = entry_time + timedelta(hours=1, minutes=30)
        v_types = ["Car", "Motorcycle", "Truck"]
        vt = v_types[i % 3]
        desc = f"Seeded {vt}"
        
        fee = Decimal("2.00") if vt == "Motorcycle" else Decimal("4.00")
        
        s = ParkingSession(
            id=next_parking_session_id(db),
            license_plate=f"SD-{vt[0]}-{1000 + i}",
            vehicle_type=vt,
            vehicle_description=desc,
            entry_time=entry_time,
            exit_time=exit_time,
            duration_display="1h 30m",
            status="Completed",
            fee_amount=fee,
            rate_per_hour=Decimal("2.00"),
            created_at=now,
            updated_at=now,
        )
        db.add(s)
        db.flush()
        db.add(
            Invoice(
                id=next_invoice_id(db),
                session_id=s.id,
                invoice_date=exit_time.date(),
                license_plate=s.license_plate,
                amount=fee,
                method="ABA",
                status="Paid",
                transaction_ref=f"TRX-SEED-{1000 + i}",
                created_at=now,
            )
        )


def seed() -> None:
    bootstrap_database(seed_demo=True)
    db = SessionLocal()
    try:
        seed_demo_sessions(db)
        db.commit()
    finally:
        db.close()
    print("Seed completed (devices, bank, demo sessions if DB was empty).")


if __name__ == "__main__":
    seed()
