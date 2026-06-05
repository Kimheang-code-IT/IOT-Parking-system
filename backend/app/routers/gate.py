"""Lane workstation API — PC camera OCR triggers gate commands for ESP32."""

from fastapi import APIRouter, Depends, Query, status
from fastapi.exceptions import HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import get_settings
from app.schemas.gate import (
    GateEntryProcessIn,
    GateEntryTriggerIn,
    GateExitProcessIn,
    GateExitTriggerIn,
    GateProcessOut,
    GateTriggerOut,
)
from app.services.gate_lane_service import GateLaneService
from app.services.gate_trigger_service import GateTriggerService

router = APIRouter(prefix="/api/gate", tags=["gate"])


@router.post("/entry/process", response_model=GateProcessOut)
def gate_entry_process(body: GateEntryProcessIn, db: Session = Depends(get_db)) -> GateProcessOut:
    """
    Entry lane PC flow:
    1. Camera captures plate (or simulator sends plate).
    2. FastAPI OCR / validation creates session + invoice.
    3. Queues ENTRY_APPROVED for target ESP32 (or returns executeOnDevice for Wokwi).
    """
    result = GateLaneService(db).process_entry(body)
    if not result.success:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=result.model_dump(by_alias=True))
    db.commit()
    return result


@router.post("/entry/trigger", response_model=GateTriggerOut)
def gate_entry_trigger(body: GateEntryTriggerIn, db: Session = Depends(get_db)) -> GateTriggerOut:
    """
    **One button entry:** OpenCV reads plate → session + invoice → print receipt → ENTRY_APPROVED.
    ESP / Wokwi should open gate then auto-close after `autoCloseSeconds` (default 60).
    """
    settings = get_settings()
    if body.source == "simulator" and not body.use_camera:
        body = body.model_copy(
            update={
                "use_camera": False,
                "mock_plate": body.mock_plate or settings.gate_camera_fallback_plate,
            }
        )
    result = GateTriggerService(db).entry_trigger(body)
    db.commit()
    if not result.success:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=result.model_dump(by_alias=True))
    return result


@router.post("/exit/trigger", response_model=GateTriggerOut)
def gate_exit_trigger(body: GateExitTriggerIn, db: Session = Depends(get_db)) -> GateTriggerOut:
    """
    **One button exit:** scan ticket barcode (plate|invoice|hash) only → verify → payment page / ABA → gate open.
    Set `mockPayment: true` to skip ABA in automated tests.
    """
    settings = get_settings()
    payload = body
    if body.source == "simulator" and not body.use_camera:
        payload = body.model_copy(
            update={
                "use_camera": False,
                "mock_plate": body.mock_plate or settings.gate_camera_fallback_plate,
                "mock_payment": body.mock_payment or settings.gate_auto_mock_payment,
            }
        )
    result = GateTriggerService(db).exit_trigger(payload)
    db.commit()
    if not result.success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result.model_dump(by_alias=True))
    return result


@router.post("/exit/mock-payment", response_model=GateTriggerOut)
def gate_exit_mock_payment(
    invoice_id: str = Query(..., alias="invoiceId"),
    amount: float | None = Query(None, alias="amount"),
    db: Session = Depends(get_db),
) -> GateTriggerOut:
    """Test helper — mark invoice paid (same as ABA webhook)."""
    result = GateTriggerService(db).mock_payment(invoice_id, amount)
    if not result.success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result.model_dump(by_alias=True))
    return result


@router.post("/exit/process", response_model=GateProcessOut)
def gate_exit_process(body: GateExitProcessIn, db: Session = Depends(get_db)) -> GateProcessOut:
    """
    Exit lane PC flow:
    1. Camera scans ticket barcode (plate|invoice|hash).
    2. FastAPI verifies barcode fields and ABA payment status.
    3. Queues EXIT_APPROVED or EXIT_DENIED for target ESP32.
    """
    result = GateLaneService(db).process_exit(body)
    db.commit()
    if not result.success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result.model_dump(by_alias=True))
    return result
