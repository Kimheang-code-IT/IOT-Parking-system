"""Lane workstation API — PC camera OCR triggers gate commands for ESP32."""

from fastapi import APIRouter, Depends, status
from fastapi.exceptions import HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.gate import GateEntryProcessIn, GateExitProcessIn, GateProcessOut
from app.services.gate_lane_service import GateLaneService

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


@router.post("/exit/process", response_model=GateProcessOut)
def gate_exit_process(body: GateExitProcessIn, db: Session = Depends(get_db)) -> GateProcessOut:
    """
    Exit lane PC flow:
    1. Camera scans invoice QR (verifyHash) and license plate.
    2. FastAPI verifies invoice, plate, and ABA payment status.
    3. Queues EXIT_APPROVED or EXIT_DENIED for target ESP32.
    """
    result = GateLaneService(db).process_exit(body)
    db.commit()
    if not result.success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result.model_dump(by_alias=True))
    return result
