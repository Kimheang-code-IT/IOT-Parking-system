from typing import Literal

from pydantic import Field

from app.schemas.common import CamelModel
from app.schemas.iot import PrintDataOut

RfidCardStatus = Literal["Active", "Blocked"]


class RfidCardIn(CamelModel):
    """Register a new parking card."""

    card_uid: str = Field(alias="cardUid")
    license_plate: str = Field(alias="licensePlate")
    vehicle_type: Literal["Car", "Motorcycle", "Truck"] = Field(default="Car", alias="vehicleType")
    label: str | None = None


class RfidCardUpdateIn(CamelModel):
    """Update plate / type / label / status of a registered card."""

    license_plate: str | None = Field(default=None, alias="licensePlate")
    vehicle_type: Literal["Car", "Motorcycle", "Truck"] | None = Field(default=None, alias="vehicleType")
    label: str | None = None
    status: RfidCardStatus | None = None


class RfidCardOut(CamelModel):
    card_uid: str = Field(alias="cardUid")
    license_plate: str = Field(alias="licensePlate")
    vehicle_type: str = Field(alias="vehicleType")
    label: str | None = None
    status: str
    last_used_at: str | None = Field(default=None, alias="lastUsedAt")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")


class RfidCardListOut(CamelModel):
    data: list[RfidCardOut]
    total: int


class RfidScanIn(CamelModel):
    """RFID scan sent by a gate ESP32 (device-authenticated)."""

    device_code: str = Field(alias="deviceCode")
    card_uid: str = Field(alias="cardUid")
    vehicle_type: Literal["Car", "Motorcycle", "Truck"] | None = Field(default=None, alias="vehicleType")


class RfidScanOut(CamelModel):
    success: bool
    message: str
    gate: Literal["entry", "exit"]
    authorized: bool = False
    duplicate: bool = False
    card_uid: str | None = Field(default=None, alias="cardUid")
    card_status: str | None = Field(default=None, alias="cardStatus")
    plate_number: str | None = Field(default=None, alias="plateNumber")
    session_id: str | None = Field(default=None, alias="sessionId")
    invoice_id: str | None = Field(default=None, alias="invoiceId")
    entry_time: str | None = Field(default=None, alias="entryTime")
    duration: str | None = None
    amount: float | None = None
    payment_status: str | None = Field(default=None, alias="paymentStatus")
    payment_pending: bool = Field(default=False, alias="paymentPending")
    print_data: PrintDataOut | None = Field(default=None, alias="printData")
    print_saved_path: str | None = Field(default=None, alias="printSavedPath")


class RfidScanEventOut(CamelModel):
    id: int
    card_uid: str = Field(alias="cardUid")
    gate: str
    license_plate: str | None = Field(default=None, alias="licensePlate")
    session_id: str | None = Field(default=None, alias="sessionId")
    invoice_id: str | None = Field(default=None, alias="invoiceId")
    accepted: bool
    reason: str | None = None
    created_at: str = Field(alias="createdAt")


class RfidScanListOut(CamelModel):
    data: list[RfidScanEventOut]
    total: int


class GateCommandStateOut(CamelModel):
    command_id: str = Field(alias="commandId")
    device_code: str = Field(alias="deviceCode")
    command: str
    status: str
    created_at: str = Field(alias="createdAt")
    delivered_at: str | None = Field(default=None, alias="deliveredAt")
    acked_at: str | None = Field(default=None, alias="ackedAt")
    expires_at: str | None = Field(default=None, alias="expiresAt")
    message: str = ""


class GateActivityOut(CamelModel):
    commands: list[GateCommandStateOut]
