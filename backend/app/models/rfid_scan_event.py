from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RfidScanEvent(Base):
    """Audit trail of every card presentation at a gate (accepted or not)."""

    __tablename__ = "rfid_scan_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    card_uid: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    gate: Mapped[str] = mapped_column(String(8), nullable=False, index=True)  # entry | exit
    license_plate: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    session_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    invoice_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    accepted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    __table_args__ = (
        Index("ix_rfid_scan_events_card_gate_created", "card_uid", "gate", "created_at"),
    )
