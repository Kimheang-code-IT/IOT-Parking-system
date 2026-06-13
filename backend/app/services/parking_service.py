from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.invoice import Invoice
from app.models.parking_session import ParkingSession
from app.schemas.parking import ParkingEntryOut
from app.services.parking_fee_service import ParkingFeeService
from app.services.plate_service import normalize_plate
from app.utils.datetime_utils import duration_between, format_display_datetime, utc_now
from app.utils.id_generator import next_parking_session_id


class ParkingService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.fee_service = ParkingFeeService()
        settings = get_settings()
        self.rate_per_hour = Decimal(str(settings.rate_per_hour))

    def get_active_by_plate(self, plate: str) -> ParkingSession | None:
        normalized = normalize_plate(plate)
        return (
            self.db.query(ParkingSession)
            .filter(
                ParkingSession.license_plate == normalized,
                ParkingSession.status == "Active",
            )
            .first()
        )

    def get_by_id(self, session_id: str) -> ParkingSession | None:
        return self.db.get(ParkingSession, session_id)

    def create_entry(
        self,
        license_plate: str,
        vehicle_type: str,
        vehicle_description: str | None,
    ) -> ParkingSession:
        now = utc_now()
        session = ParkingSession(
            id=next_parking_session_id(self.db),
            license_plate=license_plate,
            vehicle_type=vehicle_type,
            vehicle_description=vehicle_description,
            entry_time=now,
            exit_time=None,
            duration_display="-",
            status="Active",
            fee_amount=None,
            rate_per_hour=self.rate_per_hour,
            created_at=now,
            updated_at=now,
        )
        self.db.add(session)
        self.db.flush()
        return session

    def close_session(self, session: ParkingSession, exit_time: datetime | None = None) -> ParkingSession:
        end = exit_time or utc_now()
        _, short, _ = duration_between(session.entry_time, end)
        total_minutes, _, _ = duration_between(session.entry_time, end)
        fee = self.fee_service.calculate_fee(total_minutes)
        session.exit_time = end
        session.duration_display = short
        session.fee_amount = fee
        session.status = "Completed"
        session.updated_at = utc_now()
        self.db.add(session)
        return session

    def list_sessions(
        self,
        *,
        page: int,
        limit: int,
        sort_by: str | None,
        sort_order: str | None,
        search: str | None,
        status: list[str] | None,
        vehicle_type: list[str] | None,
        entry_date_from: date | None,
        entry_date_to: date | None,
        exit_date_from: date | None,
        exit_date_to: date | None,
    ) -> tuple[list[ParkingEntryOut], int, dict[str, float]]:
        query = select(ParkingSession)
        filters = []

        if search:
            term = f"%{search.lower()}%"
            filters.append(
                or_(
                    func.lower(ParkingSession.id).like(term),
                    func.lower(ParkingSession.license_plate).like(term),
                    func.lower(ParkingSession.vehicle_type).like(term),
                )
            )
        if status:
            filters.append(ParkingSession.status.in_(status))
        if vehicle_type:
            filters.append(ParkingSession.vehicle_type.in_(vehicle_type))
        if entry_date_from:
            filters.append(func.date(ParkingSession.entry_time) >= entry_date_from)
        if entry_date_to:
            filters.append(func.date(ParkingSession.entry_time) <= entry_date_to)
        if exit_date_from:
            filters.append(func.date(ParkingSession.exit_time) >= exit_date_from)
        if exit_date_to:
            filters.append(func.date(ParkingSession.exit_time) <= exit_date_to)

        count_stmt = select(func.count()).select_from(ParkingSession)
        if filters:
            count_stmt = count_stmt.where(*filters)
            query = query.where(*filters)

        sort_map = {
            "id": ParkingSession.id,
            "licensePlate": ParkingSession.license_plate,
            "type": ParkingSession.vehicle_type,
            "entryTime": ParkingSession.entry_time,
            "exitTime": ParkingSession.exit_time,
            "duration": ParkingSession.duration_display,
            "status": ParkingSession.status,
        }
        sort_col = sort_map.get(sort_by or "entryTime", ParkingSession.entry_time)
        order_fn = desc if sort_order == "desc" else asc
        query = query.order_by(order_fn(sort_col))

        total = self.db.scalar(count_stmt) or 0
        rows = self.db.scalars(query.offset((page - 1) * limit).limit(limit)).all()

        active_count = sum(1 for r in rows if r.status == "Active")
        aggregates = {"activeCount": float(active_count)}

        return [self._to_out(row) for row in rows], int(total), aggregates

    def _to_out(self, session: ParkingSession) -> ParkingEntryOut:
        return ParkingEntryOut(
            id=session.id,
            license_plate=session.license_plate,
            type=session.vehicle_type,  # type: ignore[arg-type]
            entry_time=format_display_datetime(session.entry_time),
            exit_time=format_display_datetime(session.exit_time),
            duration=session.duration_display or "-",
            status=session.status,  # type: ignore[arg-type]
        )

    def active_session_card(self, plate: str) -> dict | None:
        session = self.get_active_by_plate(plate)
        if not session:
            return None
        now = utc_now()
        total_minutes, _, long_display = duration_between(session.entry_time, now)
        if session.fee_amount is not None:
            amount = float(session.fee_amount)
        else:
            amount = float(self.fee_service.calculate_fee(total_minutes))
        vehicle_type = session.vehicle_description or session.vehicle_type
        invoice = (
            self.db.query(Invoice)
            .filter(Invoice.session_id == session.id)
            .order_by(Invoice.created_at.desc())
            .first()
        )
        if invoice and invoice.amount and session.fee_amount is not None:
            amount = float(invoice.amount)
        payment_status = invoice.status if invoice else None
        return {
            "plateNumber": session.license_plate,
            "vehicleType": vehicle_type,
            "entryTime": format_display_datetime(session.entry_time, with_am_pm=True),
            "duration": long_display,
            "amount": amount,
            "invoiceId": invoice.id if invoice else None,
            "sessionId": session.id,
            "paymentStatus": payment_status,
            "verifyHash": invoice.exit_verify_hash if invoice else None,
        }
