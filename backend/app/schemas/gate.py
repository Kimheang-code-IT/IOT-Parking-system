from typing import Literal

from pydantic import Field

from app.schemas.common import CamelModel
from app.schemas.iot import PrintDataOut


class GateEntryProcessIn(CamelModel):
    """Lane PC (camera OCR) or simulator — entry request."""

    license_plate: str = Field(alias="licensePlate")
    vehicle_type: Literal["Car", "Motorcycle", "Truck"] = Field(default="Car", alias="vehicleType")
    vehicle_description: str | None = Field(default=None, alias="vehicleDescription")
    source: Literal["camera", "simulator", "manual"] = "camera"
    target_device: str = Field(default="ENTRY_GATE_01", alias="targetDevice")
    image_base64: str | None = Field(default=None, alias="imageBase64")


class GateExitProcessIn(CamelModel):
    """Lane PC — invoice QR + plate from cameras."""

    verify_hash: str | None = Field(default=None, alias="verifyHash")
    invoice_id: str | None = Field(default=None, alias="invoiceId")
    license_plate: str = Field(alias="licensePlate")
    source: Literal["camera", "simulator", "manual"] = "camera"
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
        description="True when source=simulator — ESP runs gate locally from HTTP response.",
    )
