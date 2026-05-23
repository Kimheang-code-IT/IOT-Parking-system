from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.iot_device import IotDevice
from app.schemas.gate import GateCommandOut, GateEntryProcessIn, GateExitProcessIn, GateProcessOut
from app.schemas.iot import EntryScanIn, ExitVerifyIn
from app.services.gate_command_service import GateCommandService
from app.services.gate_ocr_service import GateOcrService
from app.services.iot_device_service import IotDeviceService
from app.services.iot_entry_service import IotEntryService
from app.services.iot_exit_service import IotExitService
from app.services.printer_service import PrinterService
from app.utils.exit_verify_utils import normalize_verify_hash_scan


class GateLaneService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.commands = GateCommandService(db)
        self.devices = IotDeviceService(db)
        self.entry = IotEntryService(db)
        self.exit = IotExitService(db)

    def process_entry(self, body: GateEntryProcessIn) -> GateProcessOut:
        plate = (body.license_plate or "").strip().upper()
        if not plate:
            try:
                plate = GateOcrService.recognize_plate(image_base64=body.image_base64)
            except ValueError as exc:
                return GateProcessOut(success=False, message=str(exc))

        device = self._device(body.target_device)
        if not device:
            return GateProcessOut(success=False, message=f"Unknown device {body.target_device}.")

        scan = EntryScanIn.model_validate(
            {
                "deviceCode": device.device_code,
                "licensePlate": plate,
                "vehicleType": body.vehicle_type,
                "vehicleDescription": body.vehicle_description or f"Source: {body.source}",
            }
        )
        result = self.entry.process_entry(scan, device)
        if not result.success:
            return GateProcessOut(success=False, message=result.message)

        payload = {
            "sessionId": result.session_id,
            "invoiceId": result.invoice_id,
            "plateNumber": result.license_plate,
            "message": result.message,
        }
        queue_device = "GATE_SIM_01" if body.source == "simulator" else body.target_device
        cmd_row = self.commands.queue(queue_device, "ENTRY_APPROVED", payload)

        gate_cmd = GateCommandOut(
            commandId=cmd_row.id,
            command="ENTRY_APPROVED",
            message="Entry approved — open gate.",
            sessionId=result.session_id,
            invoiceId=result.invoice_id,
            plateNumber=result.license_plate,
            printData=result.print_data,
        )
        execute_local = body.source == "simulator"
        return GateProcessOut(
            success=True,
            message=result.message,
            gateCommand=gate_cmd,
            executeOnDevice=execute_local,
        )

    def process_exit(self, body: GateExitProcessIn) -> GateProcessOut:
        plate = body.license_plate.strip().upper()
        verify_hash = normalize_verify_hash_scan(body.verify_hash or "") if body.verify_hash else ""
        if body.invoice_id and not verify_hash:
            verify_hash = body.invoice_id.strip().upper()

        if not verify_hash:
            return GateProcessOut(success=False, message="Invoice QR / verifyHash is required.")

        device = self._device(body.target_device)
        if not device:
            return GateProcessOut(success=False, message=f"Unknown device {body.target_device}.")

        verify = ExitVerifyIn.model_validate(
            {
                "deviceCode": device.device_code,
                "verifyHash": verify_hash,
                "licensePlate": plate,
                "invoiceId": body.invoice_id,
            }
        )
        result = self.exit.verify_exit(verify, device)
        if not result.success:
            queue_device = "GATE_SIM_01" if body.source == "simulator" else body.target_device
            cmd_row = self.commands.queue(
                queue_device,
                "EXIT_DENIED",
                {"message": result.message, "plateNumber": plate},
            )
            return GateProcessOut(
                success=False,
                message=result.message,
                gateCommand=GateCommandOut(
                    commandId=cmd_row.id,
                    command="EXIT_DENIED",
                    message=result.message,
                    plateNumber=plate,
                ),
                executeOnDevice=body.source == "simulator",
            )

        paid = (result.payment_status or "").lower() == "paid"
        if body.require_paid and not paid:
            msg = "Payment required before exit."
            queue_device = "GATE_SIM_01" if body.source == "simulator" else body.target_device
            cmd_row = self.commands.queue(
                queue_device,
                "EXIT_DENIED",
                {
                    "message": msg,
                    "sessionId": result.session_id,
                    "invoiceId": result.invoice_id,
                    "amount": result.amount,
                    "paymentStatus": result.payment_status,
                },
            )
            return GateProcessOut(
                success=False,
                message=msg,
                gateCommand=GateCommandOut(
                    commandId=cmd_row.id,
                    command="EXIT_DENIED",
                    message=msg,
                    sessionId=result.session_id,
                    invoiceId=result.invoice_id,
                    plateNumber=plate,
                    amount=result.amount,
                    paymentStatus=result.payment_status,
                ),
                executeOnDevice=body.source == "simulator",
            )

        payload = {
            "sessionId": result.session_id,
            "invoiceId": result.invoice_id,
            "plateNumber": plate,
            "amount": result.amount,
            "paymentStatus": result.payment_status,
        }
        queue_device = "GATE_SIM_01" if body.source == "simulator" else body.target_device
        cmd_row = self.commands.queue(queue_device, "EXIT_APPROVED", payload)
        return GateProcessOut(
            success=True,
            message="Exit approved — open gate.",
            gateCommand=GateCommandOut(
                commandId=cmd_row.id,
                command="EXIT_APPROVED",
                message="Exit approved.",
                sessionId=result.session_id,
                invoiceId=result.invoice_id,
                plateNumber=plate,
                amount=result.amount,
                paymentStatus=result.payment_status,
            ),
            executeOnDevice=body.source == "simulator",
        )

    def _device(self, device_code: str) -> IotDevice | None:
        return self.devices.get_by_code(device_code)
