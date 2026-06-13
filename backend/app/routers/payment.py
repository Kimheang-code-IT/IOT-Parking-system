from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.webhook_security import verify_payment_webhook
from app.schemas.payment import (
    AbaQrOut,
    ActiveSessionOut,
    BankInfoOut,
    PaymentConfigOut,
    PaymentStatusOut,
    PaymentVerifyIn,
    PaymentVerifyOut,
    PaymentWebhookIn,
)
from app.services.aba_pay_service import AbaPayError, AbaPayService
from app.services.payment_service import PaymentService

router = APIRouter(prefix="/api/payment", tags=["payment"])


@router.get("/active-session", response_model=ActiveSessionOut)
def active_session(
    plate: str | None = Query(None),
    verify_hash: str | None = Query(None, alias="verifyHash"),
    db: Session = Depends(get_db),
) -> ActiveSessionOut:
    try:
        result = PaymentService(db).get_active_session(plate, verify_hash)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active session found.")
    return result


@router.post("/verify", response_model=PaymentVerifyOut)
def verify_payment(body: PaymentVerifyIn, db: Session = Depends(get_db)) -> PaymentVerifyOut:
    try:
        return PaymentService(db).verify_payment(
            body.plate_number,
            body.amount,
            body.payment_method,
            body.invoice_id,
            body.verify_hash,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/status", response_model=PaymentStatusOut)
def payment_status(
    invoice_id: str = Query(..., alias="invoiceId"),
    verify_hash: str = Query(..., alias="verifyHash"),
    db: Session = Depends(get_db),
) -> PaymentStatusOut:
    try:
        result = PaymentService(db).get_payment_status(invoice_id, verify_hash)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found.")
    return result


@router.get("/config", response_model=PaymentConfigOut)
def payment_config() -> PaymentConfigOut:
    settings = get_settings()
    return PaymentConfigOut(
        mock_only=settings.use_aba_mock,
        use_aba_mock=settings.use_aba_mock,
    )


@router.get("/bank-info", response_model=BankInfoOut)
def bank_info(db: Session = Depends(get_db)) -> BankInfoOut:
    return PaymentService(db).get_bank_info()


@router.get("/aba-qr", response_model=AbaQrOut)
def aba_qr(
    amount: float = Query(..., gt=0),
    plate_number: str = Query(..., alias="plateNumber"),
    invoice_id: str | None = Query(None, alias="invoiceId"),
) -> AbaQrOut:
    try:
        return AbaPayService().generate_qr(amount, plate_number, invoice_id)
    except AbaPayError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "message": exc.message,
                "code": exc.code,
                "traceId": exc.trace_id,
            },
        ) from exc


@router.post("/webhook", response_model=PaymentVerifyOut)
def payment_webhook(
    body: PaymentWebhookIn,
    db: Session = Depends(get_db),
    _: None = Depends(verify_payment_webhook),
) -> PaymentVerifyOut:
    """ABA/KHQR gateway or exit payment terminal calls this when customer pays."""
    return PaymentService(db).process_webhook(body)
