import json

from sqlalchemy.orm import Session

from app.models.device_log import DeviceLog
from app.models.iot_device import IotDevice
from app.utils.datetime_utils import utc_now


class IotDeviceService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_code(self, device_code: str) -> IotDevice | None:
        return self.db.query(IotDevice).filter(IotDevice.device_code == device_code).first()

    def touch_last_seen(self, device: IotDevice) -> None:
        device.last_seen_at = utc_now()
        self.db.add(device)

    def log_event(
        self,
        device: IotDevice,
        event_type: str,
        *,
        license_plate: str | None = None,
        payload: dict | None = None,
        success: bool = True,
        message: str | None = None,
    ) -> DeviceLog:
        log = DeviceLog(
            device_id=device.id,
            event_type=event_type,
            license_plate=license_plate,
            payload=json.dumps(payload) if payload else None,
            success=success,
            message=message,
            created_at=utc_now(),
        )
        self.db.add(log)
        return log
