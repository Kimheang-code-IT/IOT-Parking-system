"""One-button entry / exit lane flows with camera OCR and mock payment."""

from __future__ import annotations

import time

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.parking_revision import bump_parking_revision
from app.models.invoice import Invoice
from app.services.parking_service import ParkingService
from app.schemas.gate import (
    GateEntryProcessIn,
    GateExitProcessIn,
    GateExitTriggerIn,
    GateEntryTriggerIn,
    GateTriggerOut,
)
from app.schemas.payment import PaymentWebhookIn
from app.services.gate_camera_service import GateCameraService
from app.services.gate_lane_service import GateLaneService
from app.services.gate_receipt_printer import GateReceiptPrinter
from app.services.invoice_service import InvoiceService
from app.services.payment_service import PaymentService
from app.utils.exit_verify_utils import (
    ExitBarcodePayload,
    parse_exit_barcode,
    validate_exit_barcode_against_invoice,
)


class GateTriggerService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.camera = GateCameraService()
        self.lane = GateLaneService(db)
        self.settings = get_settings()

    def entry_trigger(self, body: GateEntryTriggerIn) -> GateTriggerOut:
        use_cam = body.use_camera and body.source in ("camera", "simulator")
        mock_plate = body.mock_plate
        if body.source == "simulator" and not body.use_camera:
            mock_plate = body.mock_plate or self.settings.gate_camera_fallback_plate
        try:
            plate = self.camera.scan_entry_plate(use_camera=use_cam, mock_plate=mock_plate)
        except ValueError as exc:
            return GateTriggerOut(success=False, message=str(exc))

        target = "GATE_SIM_01" if body.source == "simulator" else body.target_device
        result = self.lane.process_entry(
            GateEntryProcessIn.model_validate(
                {
                    "licensePlate": plate,
                    "vehicleType": body.vehicle_type,
                    "source": body.source,
                    "targetDevice": target,
                }
            )
        )
        if not result.success or not result.gate_command:
            if body.source == "simulator" and "active session" in result.message.lower():
                resumed = self._sim_resume_active_entry(plate, body.auto_close_seconds)
                if resumed:
                    return resumed
            return GateTriggerOut(success=False, message=result.message)

        receipt_path = None
        if result.gate_command.print_data:
            receipt_path = GateReceiptPrinter.print_ticket(result.gate_command.print_data)

        seconds = body.auto_close_seconds
        vhash = result.gate_command.print_data.verify_hash if result.gate_command.print_data else None
        bump_parking_revision()
        return GateTriggerOut(
            success=True,
            message=f"Entry approved for {plate}. Gate open — closes in {seconds}s.",
            verify_hash=vhash,
            plate_number=plate,
            session_id=result.gate_command.session_id,
            invoice_id=result.gate_command.invoice_id,
            gate_command=result.gate_command.command,
            print_saved_path=receipt_path,
            auto_close_seconds=seconds,
            execute_on_device=result.execute_on_device,
        )

    def exit_trigger(self, body: GateExitTriggerIn) -> GateTriggerOut:
        use_cam = body.use_camera and body.source in ("camera", "simulator")

        try:
            scan = self._resolve_exit_barcode(body, use_cam=use_cam)
        except ValueError as exc:
            return GateTriggerOut(success=False, message=str(exc))

        verify_hash = scan.verify_hash
        plate = scan.license_plate
        invoice_id = scan.invoice_id or None

        invoice = InvoiceService(self.db).get_by_id(invoice_id) if invoice_id else None
        if not invoice:
            invoice = InvoiceService(self.db).get_by_verify_hash(verify_hash)
        if not invoice:
            return GateTriggerOut(success=False, message="Invalid exit barcode — invoice not found.")

        if scan.license_plate and scan.invoice_id:
            session = ParkingService(self.db).get_by_id(invoice.session_id)
            if not session:
                return GateTriggerOut(success=False, message="Parking session not found.")
            err = validate_exit_barcode_against_invoice(
                scan,
                invoice_id=invoice.id,
                license_plate=invoice.license_plate,
                verify_hash=invoice.exit_verify_hash or "",
                session_id=session.id,
                secret=self.settings.exit_verify_secret,
            )
            if err:
                return GateTriggerOut(success=False, message=err)
            plate = scan.license_plate
            invoice_id = invoice.id
            verify_hash = (invoice.exit_verify_hash or scan.verify_hash).strip().upper()
        else:
            plate = plate or invoice.license_plate
            invoice_id = invoice.id
            verify_hash = (invoice.exit_verify_hash or verify_hash).strip().upper()

        target = "GATE_SIM_01" if body.source == "simulator" else body.target_device
        result = self.lane.process_exit(
            GateExitProcessIn.model_validate(
                {
                    "verifyHash": verify_hash,
                    "licensePlate": plate,
                    "invoiceId": invoice_id,
                    "source": body.source,
                    "targetDevice": target,
                    "requirePaid": False,
                }
            )
        )
        if not result.gate_command:
            return GateTriggerOut(success=False, message=result.message)

        invoice_id = result.gate_command.invoice_id
        session_id = result.gate_command.session_id
        amount = float(result.gate_command.amount or 0)
        bump_parking_revision()

        if body.mock_payment and invoice_id:
            self._mock_pay(invoice_id, amount)

        if body.wait_for_payment:
            paid = self._wait_until_paid(invoice_id, body.wait_payment_seconds)
            if not paid:
                return GateTriggerOut(
                    success=False,
                    message="Payment timeout — complete payment on the Payment page (ABA KHQR).",
                    plate_number=plate,
                    invoice_id=invoice_id,
                    session_id=session_id,
                    amount=amount,
                    payment_status="Pending",
                    payment_pending=True,
                    gate_command="EXIT_DENIED",
                )

        final = self.lane.process_exit(
            GateExitProcessIn.model_validate(
                {
                    "verifyHash": verify_hash,
                    "licensePlate": plate,
                    "source": body.source,
                    "targetDevice": target,
                    "requirePaid": True,
                }
            )
        )
        if not final.success:
            return GateTriggerOut(
                success=False,
                message=final.message,
                plate_number=plate,
                invoice_id=invoice_id,
                payment_status=final.gate_command.payment_status if final.gate_command else "Pending",
                gate_command="EXIT_DENIED",
                execute_on_device=final.execute_on_device,
            )

        bump_parking_revision()
        return GateTriggerOut(
            success=True,
            message=f"Exit approved for {plate}.",
            plate_number=plate,
            invoice_id=invoice_id,
            session_id=session_id,
            amount=amount,
            payment_status="Paid",
            payment_pending=False,
            gate_command="EXIT_APPROVED",
            auto_close_seconds=body.auto_close_seconds,
            execute_on_device=final.execute_on_device,
        )

    def _resolve_exit_barcode(self, body: GateExitTriggerIn, *, use_cam: bool) -> ExitBarcodePayload:
        if body.exit_barcode and body.exit_barcode.strip():
            scan = parse_exit_barcode(body.exit_barcode)
            if not scan:
                raise ValueError("Invalid exit barcode format.")
            return scan

        if use_cam and self.settings.gate_use_camera:
            raw = self.camera.scan_exit_barcode(use_camera=True)
            if not raw:
                raise ValueError("Could not read exit ticket barcode. Show receipt barcode to webcam.")
            scan = parse_exit_barcode(raw)
            if not scan:
                raise ValueError("Exit barcode unreadable — use IOT-PARKING:plate|invoice|hash ticket.")
            return scan

        if body.source == "simulator":
            plate = (body.mock_plate or self.settings.gate_camera_fallback_plate).strip().upper()
            verify_hash = (body.verify_hash or body.mock_verify_hash or "").strip().upper()
            invoice_id = ""
            inv = self._invoice_for_active_plate(plate) if plate else None
            if inv:
                invoice_id = inv.id
                verify_hash = (inv.exit_verify_hash or verify_hash).strip().upper()
            if verify_hash and invoice_id and plate:
                return ExitBarcodePayload(
                    license_plate=plate,
                    invoice_id=invoice_id,
                    verify_hash=verify_hash,
                )
            if verify_hash:
                return ExitBarcodePayload(license_plate="", invoice_id="", verify_hash=verify_hash)

        raise ValueError("Exit barcode required — scan ticket or send exitBarcode payload.")

    def mock_payment(self, invoice_id: str, amount: float | None = None) -> GateTriggerOut:
        invoice = self.db.get(Invoice, invoice_id)
        if not invoice:
            return GateTriggerOut(success=False, message="Invoice not found.")
        amt = amount if amount is not None else float(invoice.amount or 2.0)
        self._mock_pay(invoice_id, amt)
        self.db.commit()
        return GateTriggerOut(
            success=True,
            message=f"Mock payment applied to {invoice_id}.",
            invoice_id=invoice_id,
            amount=amt,
            payment_status="Paid",
        )

    def _invoice_for_active_plate(self, plate: str) -> Invoice | None:
        session = ParkingService(self.db).get_active_by_plate(plate.strip().upper())
        if not session:
            return None
        return (
            self.db.query(Invoice)
            .filter(Invoice.session_id == session.id)
            .order_by(Invoice.created_at.desc())
            .first()
        )

    def _sim_resume_active_entry(self, plate: str, auto_close_seconds: int) -> GateTriggerOut | None:
        """Wokwi: second entry press re-opens gate for the same active session."""
        invoice = self._invoice_for_active_plate(plate)
        if not invoice:
            return None
        session = ParkingService(self.db).get_active_by_plate(plate.strip().upper())
        if not session:
            return None
        vhash = (invoice.exit_verify_hash or "").strip().upper()
        bump_parking_revision()
        return GateTriggerOut(
            success=True,
            message=f"Active session for {plate} — gate open again.",
            verify_hash=vhash or None,
            plate_number=plate.strip().upper(),
            session_id=session.id,
            invoice_id=invoice.id,
            gate_command="ENTRY_APPROVED",
            auto_close_seconds=auto_close_seconds,
            execute_on_device=True,
        )

    def _mock_pay(self, invoice_id: str, amount: float) -> None:
        PaymentService(self.db).process_webhook(
            PaymentWebhookIn.model_validate(
                {
                    "invoiceId": invoice_id,
                    "amount": amount,
                    "paymentMethod": "KHQR",
                    "success": True,
                    "transactionRef": f"MOCK-{int(time.time())}",
                }
            )
        )
        self.db.commit()

    def _wait_until_paid(self, invoice_id: str | None, max_seconds: int) -> bool:
        if not invoice_id:
            return False
        deadline = time.time() + max_seconds
        while time.time() < deadline:
            inv = self.db.get(Invoice, invoice_id)
            if inv and inv.status == "Paid":
                return True
            time.sleep(2)
            self.db.expire_all()
        return False
