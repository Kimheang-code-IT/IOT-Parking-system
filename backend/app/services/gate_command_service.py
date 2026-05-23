import json
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.device_command import DeviceCommand
from app.utils.datetime_utils import utc_now


class GateCommandService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def queue(
        self,
        device_code: str,
        command: str,
        payload: dict[str, Any],
    ) -> DeviceCommand:
        row = DeviceCommand(
            id=str(uuid.uuid4()),
            device_code=device_code,
            command=command,
            payload_json=json.dumps(payload),
            status="pending",
            created_at=utc_now(),
        )
        self.db.add(row)
        self.db.flush()
        return row

    def poll_next(self, device_code: str) -> DeviceCommand | None:
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

    @staticmethod
    def payload(row: DeviceCommand) -> dict[str, Any]:
        try:
            return json.loads(row.payload_json or "{}")
        except json.JSONDecodeError:
            return {}
