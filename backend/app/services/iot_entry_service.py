from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.iot_device import IotDevice
from app.schemas.iot import EntryScanIn, EntryScanOut
from app.services.invoice_service import InvoiceService
from app.services.iot_device_service import IotDeviceService
from app.services.parking_service import ParkingService
from app.services.plate_service import normalize_plate
from app.services.printer_service import PrinterService
from app.utils.datetime_utils import format_iso


class IotEntryService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.parking = ParkingService(db)
        self.invoices = InvoiceService(db)
        self.devices = IotDeviceService(db)

    def process_entry(self, payload: EntryScanIn, device: IotDevice) -> EntryScanOut:
        plate = normalize_plate(payload.license_plate)
        if self.parking.get_active_by_plate(plate):
            self.devices.log_event(
                device,
                "ENTRY_SCAN",
                license_plate=plate,
                payload=payload.model_dump(by_alias=True),
                success=False,
                message="Vehicle already has an active session.",
            )
            self.db.commit()
            return EntryScanOut(success=False, message="Vehicle already has an active session.")

        session = self.parking.create_entry(
            plate,
            payload.vehicle_type,
            payload.vehicle_description,
        )
        invoice = self.invoices.create_pending(session.id, plate, Decimal("0.00"))
        print_data = PrinterService.build_print_data(session, invoice.id, invoice.exit_verify_hash or "")

        self.devices.touch_last_seen(device)
        self.devices.log_event(
            device,
            "ENTRY_SCAN",
            license_plate=plate,
            payload=payload.model_dump(by_alias=True),
            success=True,
            message="Vehicle entry recorded.",
        )
        self.db.commit()

        return EntryScanOut(
            success=True,
            message="Vehicle entry recorded.",
            session_id=session.id,
            invoice_id=invoice.id,
            license_plate=plate,
            entry_time=format_iso(session.entry_time),
            print_data=print_data,
        )
