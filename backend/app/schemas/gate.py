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


class GateEntryTriggerIn(CamelModel):
    """One button entry — PC OpenCV plate scan, print receipt, auto-close gate."""

    source: Literal["camera", "simulator"] = "simulator"
    use_camera: bool = Field(default=True, alias="useCamera")
    vehicle_type: Literal["Car", "Motorcycle", "Truck"] = Field(default="Car", alias="vehicleType")
    target_device: str = Field(default="ENTRY_GATE_01", alias="targetDevice")
    mock_plate: str | None = Field(default=None, alias="mockPlate")
    auto_close_seconds: int = Field(default=60, alias="autoCloseSeconds")


class GateExitTriggerIn(CamelModel):
    """Exit button — FIFO queue + wait for payment, then open gate (no exit-lane OCR)."""

    source: Literal["camera", "simulator"] = "simulator"
    use_camera: bool = Field(default=True, alias="useCamera")
    target_device: str = Field(default="EXIT_GATE_01", alias="targetDevice")
    exit_barcode: str | None = Field(
        default=None,
        alias="exitBarcode",
        description="Full IOT-PARKING:plate|invoice|hash payload (simulator without camera).",
    )
    verify_hash: str | None = Field(default=None, alias="verifyHash")
    mock_verify_hash: str | None = Field(default=None, alias="mockVerifyHash")
    mock_plate: str | None = Field(default=None, alias="mockPlate")
    mock_payment: bool = Field(default=False, alias="mockPayment")
    wait_for_payment: bool = Field(default=True, alias="waitForPayment")
    wait_payment_seconds: int = Field(default=120, alias="waitPaymentSeconds")
    auto_close_seconds: int = Field(default=20, alias="autoCloseSeconds")
    defer_gate_open: bool = Field(
        default=False,
        alias="deferGateOpen",
        description="FIFO/OCR verify + fee only — return pending payment without opening gate.",
    )
    complete_after_payment: bool = Field(
        default=False,
        alias="completeAfterPayment",
        description="Open exit gate when invoice is already paid (IoT polls payment first).",
    )
    invoice_id: str | None = Field(
        default=None,
        alias="invoiceId",
        description="Invoice from prepare phase — used with completeAfterPayment.",
    )


class GateTriggerOut(CamelModel):
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
