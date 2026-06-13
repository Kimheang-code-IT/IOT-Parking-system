"""FIFO exit queue — oldest active parking session exits first."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.invoice import Invoice
from app.models.parking_session import ParkingSession
from app.services.plate_service import normalize_plate


class ExitQueueService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def peek_fifo(self) -> ParkingSession | None:
        """Oldest active session (first in, first out)."""
        return (
            self.db.query(ParkingSession)
            .filter(ParkingSession.status == "Active")
            .order_by(ParkingSession.entry_time.asc())
            .first()
        )

    def invoice_for_session(self, session: ParkingSession) -> Invoice | None:
        return (
            self.db.query(Invoice)
            .filter(Invoice.session_id == session.id)
            .order_by(Invoice.created_at.desc())
            .first()
        )

    def fifo_plate(self) -> str | None:
        session = self.peek_fifo()
        return normalize_plate(session.license_plate) if session else None
