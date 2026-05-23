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
from app.schemas.iot_commands import DeviceCommandAckIn, DeviceCommandPollOut, GateEventIn
from app.services.gate_command_service import GateCommandService
from app.services.iot_device_service import IotDeviceService
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


@router.get("/commands/next", response_model=DeviceCommandPollOut | None)
def poll_command(
    device_code: str = Query(..., alias="deviceCode"),
    db: Session = Depends(get_db),
    device: IotDevice = Depends(verify_iot_device),
) -> DeviceCommandPollOut | None:
    """ESP32 polls for ENTRY_APPROVED / EXIT_APPROVED / EXIT_DENIED."""
    if device_code != device.device_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"success": False, "message": "Device code mismatch."},
        )
    row = GateCommandService(db).poll_next(device_code)
    if not row:
        db.commit()
        return None
    IotDeviceService(db).touch_last_seen(device)
    db.commit()
    payload = GateCommandService.payload(row)
    return DeviceCommandPollOut(
        commandId=row.id,
        command=row.command,  # type: ignore[arg-type]
        payload=payload,
        message=payload.get("message", row.command),
    )


@router.post("/commands/ack")
def ack_command(
    body: DeviceCommandAckIn,
    db: Session = Depends(get_db),
    device: IotDevice = Depends(verify_iot_device),
) -> dict:
    if body.device_code != device.device_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"success": False, "message": "Device code mismatch."},
        )
    row = GateCommandService(db).ack(body.command_id, body.device_code, body.status == "completed")
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Command not found.")
    IotDeviceService(db).log_event(
        device,
        "COMMAND_ACK",
        payload=body.model_dump(by_alias=True),
        success=body.status == "completed",
        message=body.detail or "Command acknowledged.",
    )
    db.commit()
    return {"success": True, "message": "Acknowledged."}


@router.post("/gate/event")
def gate_event(
    body: GateEventIn,
    db: Session = Depends(get_db),
    device: IotDevice = Depends(verify_iot_device),
) -> dict:
    """ESP32 reports car passed / gate closed (IR sensor or simulator button)."""
    if body.device_code != device.device_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"success": False, "message": "Device code mismatch."},
        )
    IotDeviceService(db).log_event(
        device,
        body.event.upper(),
        license_plate=None,
        payload=body.model_dump(by_alias=True),
        success=True,
        message=f"Gate event: {body.event}",
    )
    db.commit()
    return {"success": True, "message": "Event recorded."}


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
