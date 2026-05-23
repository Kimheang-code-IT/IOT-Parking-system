from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("parking_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    license_plate: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    method: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    transaction_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    exit_verify_hash: Mapped[str | None] = mapped_column(String(32), nullable=True, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    session = relationship("ParkingSession", back_populates="invoices")

    __table_args__ = (
        Index("ix_invoices_status_method", "status", "method"),
    )
