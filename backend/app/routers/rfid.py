"""RFID card management + device scan endpoints.

Device endpoints (ESP32 gate firmware, x-device-code/x-device-token):
  POST /api/rfid/entry-scan   card tap at the entry gate
  POST /api/rfid/exit-scan    card tap at the exit gate

Management endpoints (dashboard; optional shared secret rfid_admin_token):
  GET  /api/rfid/cards             registered cards (search + status filter)
  POST /api/rfid/cards             register a card
  POST /api/rfid/cards/{card_uid}  update plate / type / label / status
  GET  /api/rfid/scans             scan history (accepted + rejected)
  GET  /api/rfid/gate-activity     recent gate commands + acknowledgement state

Device scan responses always use HTTP 200 with a decision body
(success/authorized/paymentPending/duplicate) — the gate firmware acts on the
body, not on the status code.
"""

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import verify_iot_device
from app.models.iot_device import IotDevice
from app.schemas.rfid import (
    GateActivityOut,
    RfidCardIn,
    RfidCardListOut,
    RfidCardOut,
    RfidCardUpdateIn,
    RfidScanIn,
    RfidScanListOut,
    RfidScanOut,
)
from app.services.rfid_service import RfidService

router = APIRouter(prefix="/api/rfid", tags=["rfid"])


def verify_rfid_admin(
    x_rfid_admin_token: str | None = Header(default=None, alias="x-rfid-admin-token"),
) -> None:
    """Optional shared secret for card management (empty setting = local dev)."""
    expected = get_settings().rfid_admin_token
    if expected and x_rfid_admin_token != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"success": False, "message": "Invalid RFID admin token."},
        )


# ------------------------------------------------------------------ device


@router.post("/entry-scan", response_model=RfidScanOut)
def rfid_entry_scan(
    body: RfidScanIn,
    db: Session = Depends(get_db),
    device: IotDevice = Depends(verify_iot_device),
) -> RfidScanOut:
    """Entry gate taps a card: resolve card -> session + invoice + gate command."""
    if body.device_code != device.device_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"success": False, "message": "Device code mismatch."},
        )
    return RfidService(db).entry_scan(device, body)


@router.post("/exit-scan", response_model=RfidScanOut)
def rfid_exit_scan(
    body: RfidScanIn,
    db: Session = Depends(get_db),
    device: IotDevice = Depends(verify_iot_device),
) -> RfidScanOut:
    """Exit gate taps a card: active session + fee + paid check -> gate command."""
    if body.device_code != device.device_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"success": False, "message": "Device code mismatch."},
        )
    return RfidService(db).exit_scan(device, body)


# -------------------------------------------------------------- management


@router.get("/cards", response_model=RfidCardListOut, dependencies=[Depends(verify_rfid_admin)])
def list_cards(
    search: str | None = Query(None),
    status_filter: list[str] | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> RfidCardListOut:
    return RfidService(db).list_cards(search=search, status=status_filter, page=page, limit=limit)


@router.post("/cards", response_model=RfidCardOut, dependencies=[Depends(verify_rfid_admin)])
def register_card(body: RfidCardIn, db: Session = Depends(get_db)) -> RfidCardOut:
    try:
        card = RfidService(db).register_card(body)
        db.commit()
    except ValueError as exc:
        code = status.HTTP_409_CONFLICT if "already registered" in str(exc) else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=code, detail={"success": False, "message": str(exc)}) from exc
    return RfidService._card_out(card)


@router.post(
    "/cards/{card_uid}",
    response_model=RfidCardOut,
    dependencies=[Depends(verify_rfid_admin)],
)
def update_card(card_uid: str, body: RfidCardUpdateIn, db: Session = Depends(get_db)) -> RfidCardOut:
    service = RfidService(db)
    try:
        card = service.update_card(card_uid, body)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"success": False, "message": str(exc)},
        ) from exc
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"success": False, "message": "Card not found."},
        )
    db.commit()
    return RfidService._card_out(card)


@router.get("/scans", response_model=RfidScanListOut, dependencies=[Depends(verify_rfid_admin)])
def list_scans(
    card_uid: str | None = Query(None, alias="cardUid"),
    gate: str | None = Query(None, pattern="^(entry|exit)$"),
    accepted: bool | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> RfidScanListOut:
    return RfidService(db).list_scans(
        card_uid=card_uid, gate=gate, accepted=accepted, page=page, limit=limit
    )


@router.get(
    "/gate-activity",
    response_model=GateActivityOut,
    dependencies=[Depends(verify_rfid_admin)],
)
def gate_activity(
    device_code: str | None = Query(None, alias="deviceCode"),
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
) -> GateActivityOut:
    result = RfidService(db).gate_activity(device_code=device_code, limit=limit)
    db.commit()  # persist any commands newly marked expired
    return result
