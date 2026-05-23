from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.iot_device import IotDevice
from app.services.iot_device_service import IotDeviceService


def verify_iot_device(
    x_device_code: str = Header(..., alias="x-device-code"),
    x_device_token: str = Header(..., alias="x-device-token"),
    db: Session = Depends(get_db),
) -> IotDevice:
    device = IotDeviceService(db).get_by_code(x_device_code)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"success": False, "message": "Unknown device."},
        )
    if device.device_token != x_device_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"success": False, "message": "Invalid device token."},
        )
    if device.status != "Active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"success": False, "message": "Device is not active."},
        )
    return device
