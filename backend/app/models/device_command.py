from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DeviceCommand(Base):
    """Commands queued for ESP32 gates (ENTRY_APPROVED, EXIT_APPROVED, EXIT_DENIED)."""

    __tablename__ = "device_commands"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    device_code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    command: Mapped[str] = mapped_column(String(32), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (Index("ix_device_commands_device_status", "device_code", "status"),)
