"""Manual / simulator lane API — plate entry, barcode verify, mock payment helper.

The camera/OpenCV OCR entry path was removed: RFID cards drive both gates via
/api/rfid/*. These endpoints remain for manual lanes, tests and dashboards:

- POST /api/gate/entry/process   manual plate entry (no camera)
- POST /api/gate/exit/process    invoice verify-hash + plate check
- POST /api/gate/exit/mock-payment  dev helper — marks an invoice paid (same
  path as the ABA webhook), which auto-queues EXIT_APPROVED for the exit gate
"""

import time

from fastapi import APIRouter, Depends, Query, status
from fastapi.exceptions import HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.gate import (
    GateEntryProcessIn,
    GateExitProcessIn,
    GateProcessOut,
    GateTriggerOut,
)
from app.schemas.payment import PaymentWebhookIn
from app.services.gate_lane_service import GateLaneService
from app.services.invoice_service import InvoiceService
from app.services.payment_service import PaymentService

router = APIRouter(prefix="/api/gate", tags=["gate"])


@router.post("/entry/process", response_model=GateProcessOut)
def gate_entry_process(body: GateEntryProcessIn, db: Session = Depends(get_db)) -> GateProcessOut:
    """
    Manual entry lane:
    1. Plate is provided by the operator (RFID handles camera-free entry for
       registered cards via /api/rfid/entry-scan).
    2. FastAPI creates session + invoice and queues ENTRY_APPROVED.
    """
    result = GateLaneService(db).process_entry(body)
    if not result.success:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=result.model_dump(by_alias=True))
    db.commit()
    return result


@router.post("/exit/process", response_model=GateProcessOut)
def gate_exit_process(body: GateExitProcessIn, db: Session = Depends(get_db)) -> GateProcessOut:
    """
    Manual exit lane:
    1. Verify hash (ticket code) + plate are provided.
    2. FastAPI verifies the invoice and ABA payment status.
    3. Queues EXIT_APPROVED or EXIT_DENIED for the target ESP32.
    """
    result = GateLaneService(db).process_exit(body)
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
    """Test helper — mark invoice paid via the same path as the ABA webhook."""
    invoice = InvoiceService(db).get_by_id(invoice_id)
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"success": False, "message": f"Invoice {invoice_id} not found."},
        )

    amt = amount if amount is not None else float(invoice.amount or 2.0)
    result = PaymentService(db).process_webhook(
        PaymentWebhookIn.model_validate(
            {
                "invoiceId": invoice_id,
                "amount": amt,
                "paymentMethod": "KHQR",
                "success": True,
                "transactionRef": f"MOCK-{int(time.time())}",
            }
        )
    )
    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"success": False, "message": result.message},
        )
    return GateTriggerOut(
        success=True,
        message=f"Mock payment applied to {invoice_id}.",
        invoice_id=invoice_id,
        amount=amt,
        payment_status="Paid",
    )
