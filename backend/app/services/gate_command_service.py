import json
import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.device_command import DeviceCommand
from app.utils.datetime_utils import ensure_utc, utc_now


class GateCommandService:
    """Queues gate commands for ESP32 devices and tracks their lifecycle.

    Lifecycle: pending -> delivered (device polled) -> acked | failed.
    A command past `expires_at` is marked `expired` and is never delivered —
    a stale "open gate" approval must not execute minutes later.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def queue(
        self,
        device_code: str,
        command: str,
        payload: dict[str, Any],
    ) -> DeviceCommand:
        now = utc_now()
        timeout_seconds = get_settings().gate_command_timeout_seconds
        row = DeviceCommand(
            id=str(uuid.uuid4()),
            device_code=device_code,
            command=command,
            payload_json=json.dumps(payload),
            status="pending",
            created_at=now,
            expires_at=now + timedelta(seconds=timeout_seconds) if timeout_seconds > 0 else None,
        )
        self.db.add(row)
        self.db.flush()
        return row

    def expire_stale(self) -> int:
        """Marks pending/delivered commands past their deadline as expired."""
        now = utc_now()
        rows = self.db.scalars(
            select(DeviceCommand).where(DeviceCommand.status.in_(("pending", "delivered")))
        ).all()
        expired = 0
        for row in rows:
            if row.expires_at and ensure_utc(row.expires_at) < now:
                row.status = "expired"
                self.db.add(row)
                expired += 1
        if expired:
            # sessions run with autoflush disabled — the status change must be
            # flushed before poll_next selects the next pending row.
            self.db.flush()
        return expired

    def poll_next(self, device_code: str) -> DeviceCommand | None:
        self.expire_stale()
        stmt = (
            select(DeviceCommand)
            .where(
                DeviceCommand.device_code == device_code,
                DeviceCommand.status == "pending",
            )
            .order_by(DeviceCommand.created_at.asc())
            .limit(1)
        )
        row = self.db.scalar(stmt)
        if not row:
            return None
        row.status = "delivered"
        row.delivered_at = utc_now()
        self.db.add(row)
        return row

    def ack(self, command_id: str, device_code: str, success: bool) -> DeviceCommand | None:
        row = self.db.get(DeviceCommand, command_id)
        if not row or row.device_code != device_code:
            return None
        row.status = "acked" if success else "failed"
        row.acked_at = utc_now()
        self.db.add(row)
        return row

    def has_open_command(self, device_code: str, command: str, invoice_id: str) -> bool:
        """True when the same approval for this invoice is still pending/delivered."""
        rows = self.db.scalars(
            select(DeviceCommand)
            .where(
                DeviceCommand.device_code == device_code,
                DeviceCommand.command == command,
                DeviceCommand.status.in_(("pending", "delivered")),
            )
            .order_by(DeviceCommand.created_at.desc())
            .limit(10)
        ).all()
        return any(self.payload(row).get("invoiceId") == invoice_id for row in rows)

    def recent(self, device_code: str | None = None, limit: int = 25) -> list[DeviceCommand]:
        self.expire_stale()
        stmt = select(DeviceCommand).order_by(DeviceCommand.created_at.desc()).limit(limit)
        if device_code:
            stmt = stmt.where(DeviceCommand.device_code == device_code)
        return list(self.db.scalars(stmt).all())

    @staticmethod
    def payload(row: DeviceCommand) -> dict[str, Any]:
        try:
            return json.loads(row.payload_json or "{}")
        except json.JSONDecodeError:
            return {}
