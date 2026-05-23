from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.invoice import Invoice
from app.models.parking_session import ParkingSession
from app.models.payment_transaction import PaymentTransaction


def next_parking_session_id(db: Session) -> str:
    count = db.scalar(select(func.count()).select_from(ParkingSession)) or 0
    pending = sum(1 for obj in db.new if isinstance(obj, ParkingSession))
    return f"PK-{1001 + count + pending}"


def next_invoice_id(db: Session) -> str:
    count = db.scalar(select(func.count()).select_from(Invoice)) or 0
    pending = sum(1 for obj in db.new if isinstance(obj, Invoice))
    return f"IN-{count + pending + 1:06d}"


def next_transaction_ref(db: Session) -> str:
    count = db.scalar(select(func.count()).select_from(PaymentTransaction)) or 0
    suffix = 100000 + count
    return f"TRX-{suffix}-POS"
