"""First-run setup: SQLite tables, IoT devices, bank settings, optional demo sessions."""

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import Base, SessionLocal, engine
from app.core.migrations import run_schema_migrations
from app.models.bank_settings import BankSettings
from app.models.iot_device import IotDevice
from app.utils.datetime_utils import utc_now


def bootstrap_database(*, seed_demo: bool | None = None) -> None:
    settings = get_settings()
    if seed_demo is None:
        seed_demo = settings.seed_demo_data

    Base.metadata.create_all(bind=engine)
    run_schema_migrations()

    db = SessionLocal()
    try:
        _ensure_iot_devices(db, settings)
        _ensure_bank_settings(db)
        if seed_demo:
            from scripts.seed import seed_demo_sessions

            seed_demo_sessions(db)
        db.commit()
    finally:
        db.close()


def _ensure_iot_devices(db: Session, settings) -> None:
    if db.query(IotDevice).count() > 0:
        return
    now = utc_now()
    devices = [
        IotDevice(
            device_code="ENTRY_GATE_01",
            device_name="Entry Gate 1",
            device_type="ENTRY_GATE",
            location="North Entrance",
            status="Active",
            device_token=settings.iot_entry_device_token,
            last_seen_at=now,
            created_at=now,
        ),
        IotDevice(
            device_code="EXIT_GATE_01",
            device_name="Exit Gate 1",
            device_type="EXIT_GATE",
            location="South Exit",
            status="Active",
            device_token=settings.iot_exit_device_token,
            last_seen_at=now,
            created_at=now,
        ),
        IotDevice(
            device_code="CAMERA_ENTRY_01",
            device_name="Entry Camera",
            device_type="CAMERA",
            location="North Entrance",
            status="Active",
            device_token=settings.iot_entry_device_token,
            last_seen_at=now,
            created_at=now,
        ),
        IotDevice(
            device_code="PRINTER_01",
            device_name="Ticket Printer",
            device_type="PRINTER",
            location="Booth",
            status="Active",
            device_token=settings.iot_entry_device_token,
            last_seen_at=now,
            created_at=now,
        ),
    ]
    db.add_all(devices)


def _ensure_bank_settings(db: Session) -> None:
    if db.query(BankSettings).count() > 0:
        return
    db.add(
        BankSettings(
            name="ABA Bank",
            account_name="IOT Parking System",
            account_number="001234567",
        )
    )
