from app.models.parking_session import ParkingSession
from app.schemas.iot import PrintDataOut
from app.utils.datetime_utils import ensure_utc, format_display_datetime
from app.utils.exit_verify_utils import barcode_data_url, format_exit_barcode_payload


def _receipt_date(dt) -> str:
    local = ensure_utc(dt).astimezone()
    return f"{local.month}/{local.day}/{local.year}"


class PrinterService:
    @staticmethod
    def build_print_data(session: ParkingSession, invoice_id: str, verify_hash: str) -> PrintDataOut:
        entry = session.entry_time
        barcode_payload = format_exit_barcode_payload(
            license_plate=session.license_plate,
            invoice_id=invoice_id,
            verify_hash=verify_hash,
        )
        return PrintDataOut(
            invoice_no=invoice_id,
            plate_number=session.license_plate,
            vehicle_type=session.vehicle_type,
            entry_time=format_display_datetime(entry, with_am_pm=True),
            receipt_date=_receipt_date(entry),
            verify_hash=verify_hash,
            barcode_image=barcode_data_url(barcode_payload),
            qr_code=barcode_payload,
        )
