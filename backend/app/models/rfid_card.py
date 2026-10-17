from datetime import datetime

from sqlalchemy import DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RfidCard(Base):
    """Registered parking card — maps an RFID UID to a license plate.

    SECURITY NOTE: a card UID is an identifier, not a secret — MIFARE Classic
    UIDs can be cloned. Production systems should additionally require a staff
    gate, PIN, or secure-element cards. See README security notes.
    """

    __tablename__ = "rfid_cards"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    card_uid: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    license_plate: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    vehicle_type: Mapped[str] = mapped_column(String(32), nullable=False, default="Car")
    label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="Active", index=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_rfid_cards_status_plate", "status", "license_plate"),
    )
