from typing import Literal

from pydantic import Field

from app.schemas.common import CamelModel


class EntryScanIn(CamelModel):
    device_code: str = Field(alias="deviceCode")
    license_plate: str = Field(alias="licensePlate")
    vehicle_type: Literal["Car", "Motorcycle", "Truck"] = Field(alias="vehicleType")
    vehicle_description: str | None = Field(default=None, alias="vehicleDescription")
    image_url: str | None = Field(default=None, alias="imageUrl")


class PrintDataOut(CamelModel):
    invoice_no: str = Field(alias="invoiceNo")
    plate_number: str = Field(alias="plateNumber")
    vehicle_type: str = Field(alias="vehicleType")
    entry_time: str = Field(alias="entryTime")
    receipt_date: str = Field(alias="receiptDate")
    verify_hash: str = Field(alias="verifyHash")
    barcode_image: str | None = Field(default=None, alias="barcodeImage")
    qr_code: str = Field(alias="qrCode")


class EntryScanOut(CamelModel):
    success: bool
    message: str
    session_id: str | None = Field(default=None, alias="sessionId")
    invoice_id: str | None = Field(default=None, alias="invoiceId")
    license_plate: str | None = Field(default=None, alias="licensePlate")
    entry_time: str | None = Field(default=None, alias="entryTime")
    print_data: PrintDataOut | None = Field(default=None, alias="printData")


class ExitVerifyIn(CamelModel):
    device_code: str = Field(alias="deviceCode")
    verify_hash: str = Field(alias="verifyHash")
    license_plate: str = Field(alias="licensePlate")
    invoice_id: str | None = Field(default=None, alias="invoiceId")


class ExitVerifyOut(CamelModel):
    success: bool
    message: str
    session_id: str | None = Field(default=None, alias="sessionId")
    invoice_id: str | None = Field(default=None, alias="invoiceId")
    plate_number: str | None = Field(default=None, alias="plateNumber")
    entry_time: str | None = Field(alias="entryTime")
    exit_time: str | None = Field(alias="exitTime")
    duration: str | None = None
    amount: float | None = None
    payment_status: str | None = Field(default=None, alias="paymentStatus")


class OpenGateIn(CamelModel):
    device_code: str = Field(alias="deviceCode")
    session_id: str = Field(alias="sessionId")


class OpenGateOut(CamelModel):
    success: bool
    message: str


class DeviceHeartbeatIn(CamelModel):
    device_code: str = Field(alias="deviceCode")


class DeviceHeartbeatOut(CamelModel):
    success: bool
    message: str
    device_code: str = Field(alias="deviceCode")
    last_seen_at: str | None = Field(default=None, alias="lastSeenAt")


class SessionStatusOut(CamelModel):
    success: bool
    session_id: str = Field(alias="sessionId")
    invoice_id: str | None = Field(default=None, alias="invoiceId")
    plate_number: str | None = Field(default=None, alias="plateNumber")
    session_status: str = Field(alias="sessionStatus")
    payment_status: str = Field(alias="paymentStatus")
    amount: float | None = None
    can_open_gate: bool = Field(alias="canOpenGate")
