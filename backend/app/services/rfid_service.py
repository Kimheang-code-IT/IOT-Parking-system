"""RFID access control — card registry, scan flows, duplicate protection.

Reuses the existing parking / invoice / payment / gate-command services; this
module only adds the card identity layer plus the scan audit trail.

SECURITY: a MIFARE card UID is an identifier, not a secret (UIDs can be
cloned). It is fine for this local project; production deployments need
additional authentication. See README "Security notes".
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.parking_revision import bump_parking_revision
from app.models.invoice import Invoice
from app.models.iot_device import IotDevice
from app.models.parking_session import ParkingSession
from app.models.rfid_card import RfidCard
from app.models.rfid_scan_event import RfidScanEvent
from app.schemas.iot import EntryScanIn, ExitVerifyIn
from app.schemas.rfid import (
    GateActivityOut,
    GateCommandStateOut,
    RfidCardIn,
    RfidCardListOut,
    RfidCardOut,
    RfidCardUpdateIn,
    RfidScanEventOut,
    RfidScanIn,
    RfidScanListOut,
    RfidScanOut,
)
from app.services.gate_command_service import GateCommandService
from app.services.gate_receipt_printer import GateReceiptPrinter
from app.services.invoice_service import InvoiceService
from app.services.iot_device_service import IotDeviceService
from app.services.iot_entry_service import IotEntryService
from app.services.iot_exit_service import IotExitService
from app.services.parking_service import ParkingService
from app.services.plate_service import normalize_plate
from app.utils.datetime_utils import ensure_utc, format_iso, utc_now
from app.utils.rfid_utils import normalize_card_uid

# Window in which a card scan can re-open the exit gate for an already-paid
# invoice (e.g. the driver paid first, then pulled up to the gate).
REPAID_EXIT_WINDOW_MINUTES = 30


class RfidService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.parking = ParkingService(db)
        self.invoices = InvoiceService(db)
        self.devices = IotDeviceService(db)
        self.commands = GateCommandService(db)
        self.entry = IotEntryService(db)
        self.exit = IotExitService(db)

    # ------------------------------------------------------------- cards

    def register_card(self, payload: RfidCardIn) -> RfidCard:
        uid = normalize_card_uid(payload.card_uid)
        plate = normalize_plate(payload.license_plate)
        if not plate:
            raise ValueError("License plate is required.")
        if self.get_card(uid):
            raise ValueError(f"Card {uid} is already registered.")

        now = utc_now()
        card = RfidCard(
            card_uid=uid,
            license_plate=plate,
            vehicle_type=payload.vehicle_type,
            label=(payload.label or None),
            status="Active",
            last_used_at=None,
            created_at=now,
            updated_at=now,
        )
        self.db.add(card)
        self.db.flush()
        return card

    def get_card(self, uid_raw: str) -> RfidCard | None:
        try:
            uid = normalize_card_uid(uid_raw)
        except ValueError:
            return None
        return self.db.query(RfidCard).filter(RfidCard.card_uid == uid).first()

    def update_card(self, uid_raw: str, payload: RfidCardUpdateIn) -> RfidCard | None:
        card = self.get_card(uid_raw)
        if not card:
            return None
        if payload.license_plate is not None:
            plate = normalize_plate(payload.license_plate)
            if not plate:
                raise ValueError("License plate cannot be empty.")
            card.license_plate = plate
        if payload.vehicle_type is not None:
            card.vehicle_type = payload.vehicle_type
        if payload.label is not None:
            card.label = payload.label or None
        if payload.status is not None:
            card.status = payload.status
        card.updated_at = utc_now()
        self.db.add(card)
        self.db.flush()
        return card

    def list_cards(
        self,
        *,
        search: str | None = None,
        status: list[str] | None = None,
        page: int = 1,
        limit: int = 50,
    ) -> RfidCardListOut:
        query = select(RfidCard)
        count_stmt = select(func.count()).select_from(RfidCard)
        filters = []
        if search:
            term = f"%{search.lower()}%"
            filters.append(
                or_(
                    func.lower(RfidCard.card_uid).like(term),
                    func.lower(RfidCard.license_plate).like(term),
                    func.lower(func.coalesce(RfidCard.label, "")).like(term),
                )
            )
        if status:
            filters.append(RfidCard.status.in_(status))
        if filters:
            query = query.where(*filters)
            count_stmt = count_stmt.where(*filters)

        total = int(self.db.scalar(count_stmt) or 0)
        rows = self.db.scalars(
            query.order_by(RfidCard.created_at.desc()).offset((page - 1) * limit).limit(limit)
        ).all()
        return RfidCardListOut(data=[self._card_out(row) for row in rows], total=total)

    def list_scans(
        self,
        *,
        card_uid: str | None = None,
        gate: str | None = None,
        accepted: bool | None = None,
        page: int = 1,
        limit: int = 50,
    ) -> RfidScanListOut:
        query = select(RfidScanEvent)
        count_stmt = select(func.count()).select_from(RfidScanEvent)
        filters = []
        if card_uid:
            filters.append(RfidScanEvent.card_uid == card_uid.strip().upper())
        if gate:
            filters.append(RfidScanEvent.gate == gate)
        if accepted is not None:
            filters.append(RfidScanEvent.accepted == accepted)
        if filters:
            query = query.where(*filters)
            count_stmt = count_stmt.where(*filters)

        total = int(self.db.scalar(count_stmt) or 0)
        rows = self.db.scalars(
            query.order_by(RfidScanEvent.created_at.desc()).offset((page - 1) * limit).limit(limit)
        ).all()
        return RfidScanListOut(data=[self._scan_out(row) for row in rows], total=total)

    def gate_activity(self, device_code: str | None = None, limit: int = 25) -> GateActivityOut:
        rows = self.commands.recent(device_code=device_code, limit=limit)
        commands = [
            GateCommandStateOut(
                command_id=row.id,
                device_code=row.device_code,
                command=row.command,
                status=row.status,
                created_at=format_iso(row.created_at),
                delivered_at=format_iso(row.delivered_at) if row.delivered_at else None,
                acked_at=format_iso(row.acked_at) if row.acked_at else None,
                expires_at=format_iso(row.expires_at) if row.expires_at else None,
                message=str(self.commands.payload(row).get("message", "")),
            )
            for row in rows
        ]
        return GateActivityOut(commands=commands)

    # ------------------------------------------------------------- scans

    def entry_scan(self, device: IotDevice, payload: RfidScanIn) -> RfidScanOut:
        uid = self._normalize_or_deny(payload.card_uid, "entry")
        if isinstance(uid, RfidScanOut):
            return uid

        card = self.get_card(uid)
        if not card:
            return self._deny("entry", uid, "Card not registered. Ask staff to register this card.")
        if card.status != "Active":
            return self._deny("entry", uid, f"Card is {card.status.lower()}.", card=card)
        if self._is_duplicate(uid, "entry"):
            return self._duplicate_out("entry", uid)

        plate = normalize_plate(card.license_plate)

        # Already inside with an active session: re-open the entry gate for
        # this card instead of creating a duplicate session.
        active = self.parking.get_active_by_plate(plate)
        if active:
            invoice = self._latest_invoice(active.id)
            if invoice:
                payload_dict = {
                    "sessionId": active.id,
                    "invoiceId": invoice.id,
                    "plateNumber": plate,
                    "cardUid": uid,
                    "message": "Active session — entry gate open.",
                }
                if not self.commands.has_open_command(device.device_code, "ENTRY_APPROVED", invoice.id):
                    self.commands.queue(device.device_code, "ENTRY_APPROVED", payload_dict)
                self._touch_card(card)
                self.devices.touch_last_seen(device)
                self._log_scan(
                    uid, "entry", plate=plate, session_id=active.id, invoice_id=invoice.id,
                    accepted=True, reason="active session reopened",
                )
                self.db.commit()
                bump_parking_revision()
                return RfidScanOut(
                    success=True,
                    gate="entry",
                    authorized=True,
                    message="Active session found — gate opening.",
                    card_uid=uid,
                    card_status=card.status,
                    plate_number=plate,
                    session_id=active.id,
                    invoice_id=invoice.id,
                )

        scan = EntryScanIn.model_validate(
            {
                "deviceCode": device.device_code,
                "licensePlate": plate,
                "vehicleType": payload.vehicle_type or card.vehicle_type,
                "vehicleDescription": f"RFID card {uid}",
            }
        )
        result = self.entry.process_entry(scan, device)  # commits
        if not result.success:
            return self._deny("entry", uid, result.message, card=card)

        self.commands.queue(
            device.device_code,
            "ENTRY_APPROVED",
            {
                "sessionId": result.session_id,
                "invoiceId": result.invoice_id,
                "plateNumber": result.license_plate,
                "cardUid": uid,
                "message": "Entry approved — open gate.",
            },
        )
        receipt_path = GateReceiptPrinter.print_ticket(result.print_data) if result.print_data else None

        self._touch_card(card)
        self._log_scan(
            uid, "entry", plate=plate, session_id=result.session_id, invoice_id=result.invoice_id,
            accepted=True, reason="entry approved",
        )
        self.db.commit()
        bump_parking_revision()
        return RfidScanOut(
            success=True,
            gate="entry",
            authorized=True,
            message="Entry approved — gate opening.",
            card_uid=uid,
            card_status=card.status,
            plate_number=result.license_plate,
            session_id=result.session_id,
            invoice_id=result.invoice_id,
            entry_time=result.entry_time,
            print_data=result.print_data,
            print_saved_path=receipt_path,
        )

    def exit_scan(self, device: IotDevice, payload: RfidScanIn) -> RfidScanOut:
        uid = self._normalize_or_deny(payload.card_uid, "exit")
        if isinstance(uid, RfidScanOut):
            return uid

        card = self.get_card(uid)
        if not card:
            return self._deny("exit", uid, "Card not registered. Ask staff to register this card.")
        if card.status != "Active":
            return self._deny("exit", uid, f"Card is {card.status.lower()}.", card=card)
        if self._is_duplicate(uid, "exit"):
            return self._duplicate_out("exit", uid)

        plate = normalize_plate(card.license_plate)
        session = self.parking.get_active_by_plate(plate)

        if session:
            invoice = self._latest_invoice(session.id)
            if not invoice:
                return self._deny("exit", uid, "Invoice missing for this session — contact staff.", card=card)

            verify = ExitVerifyIn.model_validate(
                {
                    "deviceCode": device.device_code,
                    "verifyHash": invoice.exit_verify_hash or "",
                    "licensePlate": plate,
                    "invoiceId": invoice.id,
                }
            )
            # Reuses the invoice/plate verification + fee calculation.
            result = self.exit.verify_exit(verify, device)  # commits
            if not result.success:
                return self._deny("exit", uid, result.message, card=card, session_id=session.id)

            due = float(result.amount or 0)
            paid = (result.payment_status or "").lower() == "paid"
            self._touch_card(card)

            if paid:
                command_payload = {
                    "sessionId": session.id,
                    "invoiceId": invoice.id,
                    "plateNumber": plate,
                    "amount": due,
                    "paymentStatus": result.payment_status,
                    "message": "Exit approved — open gate.",
                }
                if not self.commands.has_open_command(device.device_code, "EXIT_APPROVED", invoice.id):
                    self.commands.queue(device.device_code, "EXIT_APPROVED", command_payload)
                self._log_scan(
                    uid, "exit", plate=plate, session_id=session.id, invoice_id=invoice.id,
                    accepted=True, reason="exit approved (paid)",
                )
                self.db.commit()
                bump_parking_revision()
                return RfidScanOut(
                    success=True,
                    gate="exit",
                    authorized=True,
                    message="Exit approved — gate opening.",
                    card_uid=uid,
                    card_status=card.status,
                    plate_number=plate,
                    session_id=session.id,
                    invoice_id=invoice.id,
                    entry_time=result.entry_time,
                    duration=result.duration,
                    amount=due,
                    payment_status=result.payment_status,
                )

            self._log_scan(
                uid, "exit", plate=plate, session_id=session.id, invoice_id=invoice.id,
                accepted=True, reason="payment pending",
            )
            self.db.commit()
            bump_parking_revision()
            return RfidScanOut(
                success=True,
                gate="exit",
                authorized=False,
                payment_pending=True,
                message=f"Payment due ${due:.2f} — pay at the kiosk/dashboard; the gate opens when paid.",
                card_uid=uid,
                card_status=card.status,
                plate_number=plate,
                session_id=session.id,
                invoice_id=invoice.id,
                entry_time=result.entry_time,
                duration=result.duration,
                amount=due,
                payment_status=result.payment_status,
            )

        # No active session: the driver may have paid already (dashboard /
        # ABA webhook completed the session). Re-open the exit gate if the
        # payment is recent; otherwise deny.
        paid_invoice = self._recently_paid_invoice(plate)
        if paid_invoice:
            if not self.commands.has_open_command(
                device.device_code, "EXIT_APPROVED", paid_invoice.id
            ):
                self.commands.queue(
                    device.device_code,
                    "EXIT_APPROVED",
                    {
                        "sessionId": paid_invoice.session_id,
                        "invoiceId": paid_invoice.id,
                        "plateNumber": plate,
                        "amount": float(paid_invoice.amount or 0),
                        "paymentStatus": paid_invoice.status,
                        "message": "Payment received — exit gate open.",
                    },
                )
            self._touch_card(card)
            self.devices.touch_last_seen(device)
            self._log_scan(
                uid, "exit", plate=plate, session_id=paid_invoice.session_id,
                invoice_id=paid_invoice.id, accepted=True, reason="already paid",
            )
            self.db.commit()
            bump_parking_revision()
            return RfidScanOut(
                success=True,
                gate="exit",
                authorized=True,
                message="Payment already received — gate opening.",
                card_uid=uid,
                card_status=card.status,
                plate_number=plate,
                session_id=paid_invoice.session_id,
                invoice_id=paid_invoice.id,
                amount=float(paid_invoice.amount or 0),
                payment_status=paid_invoice.status,
            )

        return self._deny("exit", uid, "No active parking session for this card.", card=card)

    # ------------------------------------------------------------- helpers

    def _normalize_or_deny(self, uid_raw: str, gate: str) -> str | RfidScanOut:
        try:
            return normalize_card_uid(uid_raw)
        except ValueError as exc:
            return self._deny(gate, (uid_raw or "").strip().upper()[:32], str(exc))

    def _is_duplicate(self, uid: str, gate: str) -> bool:
        cooldown = max(int(self.settings.rfid_scan_cooldown_seconds), 1)
        cutoff = utc_now() - timedelta(seconds=cooldown)
        row = (
            self.db.query(RfidScanEvent)
            .filter(
                RfidScanEvent.card_uid == uid,
                RfidScanEvent.gate == gate,
                RfidScanEvent.accepted.is_(True),
            )
            .order_by(RfidScanEvent.created_at.desc())
            .first()
        )
        return bool(row and row.created_at and ensure_utc(row.created_at) >= cutoff)

    def _duplicate_out(self, gate: str, uid: str) -> RfidScanOut:
        self._log_scan(uid, gate, accepted=False, reason="duplicate scan suppressed")
        self.db.commit()
        return RfidScanOut(
            success=True,
            gate=gate,
            duplicate=True,
            message="Duplicate scan ignored.",
            card_uid=uid,
        )

    def _deny(
        self,
        gate: str,
        uid: str,
        reason: str,
        *,
        card: RfidCard | None = None,
        session_id: str | None = None,
    ) -> RfidScanOut:
        plate = normalize_plate(card.license_plate) if card else None
        self._log_scan(uid, gate, plate=plate, session_id=session_id, accepted=False, reason=reason)
        self.db.commit()
        return RfidScanOut(
            success=False,
            gate=gate,
            message=reason,
            card_uid=uid or None,
            card_status=card.status if card else None,
            plate_number=plate,
        )

    def _log_scan(
        self,
        uid: str,
        gate: str,
        *,
        plate: str | None = None,
        session_id: str | None = None,
        invoice_id: str | None = None,
        accepted: bool,
        reason: str | None = None,
    ) -> RfidScanEvent:
        row = RfidScanEvent(
            card_uid=uid or "UNKNOWN",
            gate=gate,
            license_plate=plate,
            session_id=session_id,
            invoice_id=invoice_id,
            accepted=accepted,
            reason=reason,
            created_at=utc_now(),
        )
        self.db.add(row)
        return row

    def _touch_card(self, card: RfidCard) -> None:
        card.last_used_at = utc_now()
        self.db.add(card)

    def _latest_invoice(self, session_id: str) -> Invoice | None:
        return (
            self.db.query(Invoice)
            .filter(Invoice.session_id == session_id)
            .order_by(desc(Invoice.created_at))
            .first()
        )

    def _recently_paid_invoice(self, plate: str) -> Invoice | None:
        cutoff = utc_now() - timedelta(minutes=REPAID_EXIT_WINDOW_MINUTES)
        rows = (
            self.db.query(Invoice)
            .join(ParkingSession, Invoice.session_id == ParkingSession.id)
            .filter(
                Invoice.license_plate == plate,
                Invoice.status == "Paid",
                ParkingSession.exit_time.isnot(None),
            )
            .order_by(desc(Invoice.created_at))
            .limit(5)
            .all()
        )
        for invoice in rows:
            session = self.parking.get_by_id(invoice.session_id)
            if session and session.exit_time and ensure_utc(session.exit_time) >= cutoff:
                return invoice
        return None

    @staticmethod
    def _card_out(card: RfidCard) -> RfidCardOut:
        return RfidCardOut(
            card_uid=card.card_uid,
            license_plate=card.license_plate,
            vehicle_type=card.vehicle_type,
            label=card.label,
            status=card.status,
            last_used_at=format_iso(card.last_used_at) if card.last_used_at else None,
            created_at=format_iso(card.created_at),
            updated_at=format_iso(card.updated_at),
        )

    @staticmethod
    def _scan_out(row: RfidScanEvent) -> RfidScanEventOut:
        return RfidScanEventOut(
            id=row.id,
            card_uid=row.card_uid,
            gate=row.gate,
            license_plate=row.license_plate,
            session_id=row.session_id,
            invoice_id=row.invoice_id,
            accepted=row.accepted,
            reason=row.reason,
            created_at=format_iso(row.created_at),
        )
