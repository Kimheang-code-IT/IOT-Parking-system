from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ParkingSession(Base):
    __tablename__ = "parking_sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    license_plate: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    vehicle_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    vehicle_description: Mapped[str | None] = mapped_column(String(128), nullable=True)
    entry_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    exit_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_display: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    fee_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    rate_per_hour: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    invoices = relationship("Invoice", back_populates="session", lazy="selectin")
    payment_transactions = relationship("PaymentTransaction", back_populates="session", lazy="selectin")

    __table_args__ = (
        Index("ix_parking_sessions_status_entry", "status", "entry_time"),
    )
