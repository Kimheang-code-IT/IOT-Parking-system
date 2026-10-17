from typing import Literal

from pydantic import Field

from app.schemas.common import CamelModel
from app.schemas.iot import PrintDataOut


class GateEntryProcessIn(CamelModel):
    """Manual / simulator entry request (plate-based).

    There is no camera/OCR path anymore: the RFID firmware entry flow lands on
    POST /api/rfid/entry-scan, which resolves the plate from the card first.
    """

    license_plate: str = Field(alias="licensePlate")
    vehicle_type: Literal["Car", "Motorcycle", "Truck"] = Field(default="Car", alias="vehicleType")
    vehicle_description: str | None = Field(default=None, alias="vehicleDescription")
    source: Literal["camera", "simulator", "manual", "rfid"] = "manual"
    target_device: str = Field(default="ENTRY_GATE_01", alias="targetDevice")


class GateExitProcessIn(CamelModel):
    """Exit verification request (invoice verify hash + plate)."""

    verify_hash: str | None = Field(default=None, alias="verifyHash")
    invoice_id: str | None = Field(default=None, alias="invoiceId")
    license_plate: str = Field(alias="licensePlate")
    source: Literal["camera", "simulator", "manual", "rfid"] = "manual"
    target_device: str = Field(default="EXIT_GATE_01", alias="targetDevice")
    require_paid: bool = Field(default=True, alias="requirePaid")


class GateCommandOut(CamelModel):
    command_id: str = Field(alias="commandId")
    command: Literal["ENTRY_APPROVED", "EXIT_APPROVED", "EXIT_DENIED"]
    message: str
    session_id: str | None = Field(default=None, alias="sessionId")
    invoice_id: str | None = Field(default=None, alias="invoiceId")
    plate_number: str | None = Field(default=None, alias="plateNumber")
    amount: float | None = None
    payment_status: str | None = Field(default=None, alias="paymentStatus")
    print_data: PrintDataOut | None = Field(default=None, alias="printData")


class GateProcessOut(CamelModel):
    success: bool
    message: str
    gate_command: GateCommandOut | None = Field(default=None, alias="gateCommand")
    execute_on_device: bool = Field(
        default=False,
        alias="executeOnDevice",
        description="True when the caller ran the simulation — ESP runs gate locally.",
    )


class GateTriggerOut(CamelModel):
    """Kept for the manual mock-payment helper response."""

    success: bool
    message: str
    verify_hash: str | None = Field(default=None, alias="verifyHash")
    plate_number: str | None = Field(default=None, alias="plateNumber")
    session_id: str | None = Field(default=None, alias="sessionId")
    invoice_id: str | None = Field(default=None, alias="invoiceId")
    amount: float | None = None
    payment_status: str | None = Field(default=None, alias="paymentStatus")
    payment_pending: bool = Field(default=False, alias="paymentPending")
    gate_command: str | None = Field(default=None, alias="gateCommand")
    print_saved_path: str | None = Field(default=None, alias="printSavedPath")
    auto_close_seconds: int = Field(default=60, alias="autoCloseSeconds")
    execute_on_device: bool = Field(default=False, alias="executeOnDevice")
