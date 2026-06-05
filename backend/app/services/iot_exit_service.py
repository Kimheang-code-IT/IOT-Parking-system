from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.invoice import Invoice
from app.models.iot_device import IotDevice
from app.schemas.iot import (
    DeviceHeartbeatOut,
    ExitVerifyIn,
    ExitVerifyOut,
    OpenGateIn,
    OpenGateOut,
    SessionStatusOut,
)
from app.services.invoice_service import InvoiceService
from app.services.iot_device_service import IotDeviceService
from app.services.parking_fee_service import ParkingFeeService
from app.services.parking_service import ParkingService
from app.services.plate_service import normalize_plate
from app.utils.datetime_utils import duration_between, format_display_datetime, format_iso, utc_now
from app.core.config import get_settings
from app.utils.exit_verify_utils import (
    normalize_verify_hash_scan,
    parse_exit_barcode,
    validate_exit_barcode_against_invoice,
)


class IotExitService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.parking = ParkingService(db)
        self.invoices = InvoiceService(db)
        self.devices = IotDeviceService(db)
        self.fee_service = ParkingFeeService()

    def heartbeat(self, device: IotDevice) -> DeviceHeartbeatOut:
        self.devices.touch_last_seen(device)
        self.devices.log_event(device, "HEARTBEAT", success=True, message="Device online.")
        self.db.commit()
        last_seen = device.last_seen_at
        return DeviceHeartbeatOut(
            success=True,
            message="Heartbeat recorded.",
            device_code=device.device_code,
            last_seen_at=format_iso(last_seen) if last_seen else None,
        )

    def session_status(self, session_id: str) -> SessionStatusOut | None:
        session = self.parking.get_by_id(session_id)
        if not session:
            return None
        invoice = (
            self.db.query(Invoice)
            .filter(Invoice.session_id == session_id)
            .order_by(desc(Invoice.created_at))
            .first()
        )
        payment_status = invoice.status if invoice else "Pending"
        amount = float(session.fee_amount or (invoice.amount if invoice else 0))
        can_open = session.status == "Completed" and payment_status == "Paid"
        return SessionStatusOut(
            success=True,
            session_id=session.id,
            invoice_id=invoice.id if invoice else None,
            plate_number=session.license_plate,
            session_status=session.status,
            payment_status=payment_status,
            amount=amount,
            can_open_gate=can_open,
        )

    def verify_exit(self, payload: ExitVerifyIn, device: IotDevice) -> ExitVerifyOut:
        scan = parse_exit_barcode(payload.verify_hash)
        if scan and scan.license_plate and scan.invoice_id:
            plate = normalize_plate(scan.license_plate)
            verify_hash = scan.verify_hash
            invoice = self.invoices.get_by_id(scan.invoice_id)
            if not invoice:
                return self._fail(device, payload, plate, "Invalid exit barcode — invoice not found.")
            session = self.parking.get_by_id(invoice.session_id)
            if not session:
                return self._fail(device, payload, plate, "Parking session not found.")
            settings = get_settings()
            err = validate_exit_barcode_against_invoice(
                scan,
                invoice_id=invoice.id,
                license_plate=invoice.license_plate,
                verify_hash=invoice.exit_verify_hash or "",
                session_id=session.id,
                secret=settings.exit_verify_secret,
            )
            if err:
                return self._fail(device, payload, plate, err)
        else:
            plate = normalize_plate(payload.license_plate)
            verify_hash = normalize_verify_hash_scan(payload.verify_hash) or payload.verify_hash.strip().upper()
            invoice = self.invoices.get_by_verify_hash(verify_hash)
            if not invoice and payload.invoice_id:
                invoice = self.invoices.get_by_id(payload.invoice_id.strip())
            if not invoice:
                return self._fail(device, payload, plate, "Invalid exit barcode or verification code.")
            if normalize_plate(invoice.license_plate) != plate:
                return self._fail(device, payload, plate, "License plate does not match invoice.")

        session = self.parking.get_by_id(invoice.session_id)
        if not session:
            return self._fail(device, payload, plate, "Parking session not found.")

        exit_time = utc_now()
        total_minutes, short, _ = duration_between(session.entry_time, exit_time)
        fee = self.fee_service.calculate_fee(total_minutes)

        session.fee_amount = fee
        session.updated_at = exit_time
        invoice.amount = fee

        self.devices.touch_last_seen(device)
        self.devices.log_event(
            device,
            "EXIT_VERIFY",
            license_plate=plate,
            payload=payload.model_dump(by_alias=True),
            success=True,
            message="Invoice and plate verified.",
        )
        self.db.commit()

        return ExitVerifyOut(
            success=True,
            message="Invoice and plate verified.",
            session_id=session.id,
            invoice_id=invoice.id,
            plate_number=plate,
            entry_time=format_display_datetime(session.entry_time),
            exit_time=format_display_datetime(exit_time),
            duration=short,
            amount=float(fee),
            payment_status=invoice.status,
        )

    def open_gate(self, payload: OpenGateIn, device: IotDevice) -> OpenGateOut:
        session = self.parking.get_by_id(payload.session_id)
        if not session:
            return OpenGateOut(success=False, message="Session not found.")
        if session.status != "Completed":
            return OpenGateOut(success=False, message="Session must be completed and paid before opening gate.")

        self.devices.touch_last_seen(device)
        self.devices.log_event(
            device,
            "OPEN_GATE",
            license_plate=session.license_plate,
            payload=payload.model_dump(by_alias=True),
            success=True,
            message="Gate opened.",
        )
        self.db.commit()
        return OpenGateOut(success=True, message="Gate opened.")

    def _fail(self, device: IotDevice, payload: ExitVerifyIn, plate: str, message: str) -> ExitVerifyOut:
        self.devices.log_event(
            device,
            "EXIT_VERIFY",
            license_plate=plate,
            payload=payload.model_dump(by_alias=True),
            success=False,
            message=message,
        )
        self.db.commit()
        return ExitVerifyOut(success=False, message=message)
