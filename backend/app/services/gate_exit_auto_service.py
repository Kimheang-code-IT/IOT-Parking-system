"""Auto-open exit gates when a payment succeeds.

Payment can complete from the dashboard (Payment page), the ABA KHQR webhook,
or a mock/dev verify call. Whichever path marks the invoice Paid ends here and
queues EXIT_APPROVED for every active exit-capable device. The ESP32 firmware
only executes the approval when a car is present and the command has not
expired (gate_command_timeout_seconds).
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.invoice import Invoice
from app.models.iot_device import IotDevice
from app.models.parking_session import ParkingSession
from app.services.gate_command_service import GateCommandService


class GateExitAutoService:
    EXIT_DEVICE_TYPES = ("EXIT_GATE", "GATE_SIM")

    def __init__(self, db: Session) -> None:
        self.db = db
        self.commands = GateCommandService(db)

    def open_after_payment(self, invoice_id: str) -> list[str]:
        """Queue EXIT_APPROVED for the exit gate(s). Returns queued device codes."""
        invoice = self.db.get(Invoice, invoice_id)
        if not invoice or (invoice.status or "").lower() != "paid":
            return []

        session = self.db.get(ParkingSession, invoice.session_id)
        amount = 0.0
        if session and session.fee_amount is not None:
            amount = float(session.fee_amount)
        elif invoice.amount is not None:
            amount = float(invoice.amount)

        payload = {
            "sessionId": invoice.session_id,
            "invoiceId": invoice.id,
            "plateNumber": invoice.license_plate,
            "amount": amount,
            "paymentStatus": invoice.status,
            "message": "Payment received — exit gate open.",
        }

        devices = (
            self.db.query(IotDevice)
            .filter(
                IotDevice.status == "Active",
                IotDevice.device_type.in_(self.EXIT_DEVICE_TYPES),
            )
            .all()
        )
        queued: list[str] = []
        for device in devices:
            if self.commands.has_open_command(device.device_code, "EXIT_APPROVED", invoice.id):
                continue
            self.commands.queue(device.device_code, "EXIT_APPROVED", payload)
            queued.append(device.device_code)
        return queued
