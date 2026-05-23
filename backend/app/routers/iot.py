from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import verify_iot_device
from app.models.iot_device import IotDevice
from app.schemas.iot import (
    DeviceHeartbeatIn,
    DeviceHeartbeatOut,
    EntryScanIn,
    EntryScanOut,
    ExitVerifyIn,
    ExitVerifyOut,
    OpenGateIn,
    OpenGateOut,
    SessionStatusOut,
)
from app.services.iot_entry_service import IotEntryService
from app.services.iot_exit_service import IotExitService

router = APIRouter(prefix="/api/iot", tags=["iot"])


@router.post("/heartbeat", response_model=DeviceHeartbeatOut)
def device_heartbeat(
    body: DeviceHeartbeatIn,
    db: Session = Depends(get_db),
    device: IotDevice = Depends(verify_iot_device),
) -> DeviceHeartbeatOut:
    if body.device_code != device.device_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"success": False, "message": "Device code mismatch."},
        )
    return IotExitService(db).heartbeat(device)


@router.get("/session-status", response_model=SessionStatusOut)
def session_status(
    session_id: str = Query(..., alias="sessionId"),
    db: Session = Depends(get_db),
    device: IotDevice = Depends(verify_iot_device),
) -> SessionStatusOut:
    result = IotExitService(db).session_status(session_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
    return result


@router.post("/entry-scan", response_model=EntryScanOut)
def entry_scan(
    body: EntryScanIn,
    db: Session = Depends(get_db),
    device: IotDevice = Depends(verify_iot_device),
) -> EntryScanOut:
    if body.device_code != device.device_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"success": False, "message": "Device code mismatch."},
        )
    result = IotEntryService(db).process_entry(body, device)
    if not result.success:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=result.model_dump(by_alias=True))
    return result


@router.post("/exit-verify", response_model=ExitVerifyOut)
def exit_verify(
    body: ExitVerifyIn,
    db: Session = Depends(get_db),
    device: IotDevice = Depends(verify_iot_device),
) -> ExitVerifyOut:
    if body.device_code != device.device_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"success": False, "message": "Device code mismatch."},
        )
    result = IotExitService(db).verify_exit(body, device)
    if not result.success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result.model_dump(by_alias=True))
    return result


@router.post("/open-gate", response_model=OpenGateOut)
def open_gate(
    body: OpenGateIn,
    db: Session = Depends(get_db),
    device: IotDevice = Depends(verify_iot_device),
) -> OpenGateOut:
    if body.device_code != device.device_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"success": False, "message": "Device code mismatch."},
        )
    result = IotExitService(db).open_gate(body, device)
    if not result.success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result.model_dump(by_alias=True))
    return result
