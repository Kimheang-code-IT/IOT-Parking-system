from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.invoice import Invoice
from app.models.parking_session import ParkingSession
from app.schemas.dashboard import (
    DashboardStatOut,
    InteractiveChartOut,
    PeakHoursOut,
    TrendPointOut,
    VehicleTypePointOut,
)
from app.utils.datetime_utils import utc_now


class DashboardService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()

    def get_buckets(self) -> list[tuple[str, datetime, datetime]]:
        """Generate the last 7 2-hour intervals in local time ending at the current hour.
        Returns a list of tuples: (label, start_utc, end_utc)
        """
        local_now = utc_now().astimezone()
        buckets = []
        for i in range(6, -1, -1):
            dt = local_now - timedelta(hours=i * 2)
            local_start = dt.replace(minute=0, second=0, microsecond=0)
            local_end = local_start + timedelta(hours=2)
            
            label = local_start.strftime("%H") + ":00"
            start_utc = local_start.astimezone(timezone.utc)
            end_utc = local_end.astimezone(timezone.utc)
            
            buckets.append((label, start_utc, end_utc))
        return buckets

    def stats(self) -> list[DashboardStatOut]:
        active = self.db.scalar(
            select(func.count()).select_from(ParkingSession).where(ParkingSession.status == "Active")
        ) or 0
        today = date.today()
        revenue = self.db.scalar(
            select(func.coalesce(func.sum(Invoice.amount), 0)).where(
                Invoice.invoice_date == today,
                Invoice.status == "Paid",
            )
        ) or 0
        entries_today = self.db.scalar(
            select(func.count()).select_from(ParkingSession).where(func.date(ParkingSession.entry_time) == today)
        ) or 0
        available = max(self.settings.total_parking_spots - int(active), 0)

        return [
            DashboardStatOut(label="Active Vehicles", value=str(active), icon="i-lucide-car"),
            DashboardStatOut(label="Available Spots", value=str(available), icon="i-lucide-parking-circle"),
            DashboardStatOut(label="Today Revenue", value=f"${float(revenue):,.0f}", icon="i-lucide-banknote"),
            DashboardStatOut(label="Total Entries", value=str(entries_today), icon="i-lucide-arrow-right-left"),
        ]

    def occupancy_trend(self) -> list[TrendPointOut]:
        buckets = self.get_buckets()
        return [
            TrendPointOut(name=label, value=self._entries_between(start_utc, end_utc))
            for label, start_utc, end_utc in buckets
        ]

    def vehicle_types(self) -> list[VehicleTypePointOut]:
        rows = self.db.execute(
            select(ParkingSession.vehicle_type, func.count())
            .group_by(ParkingSession.vehicle_type)
            .order_by(func.count().desc())
        ).all()
        return [VehicleTypePointOut(name=row[0], value=int(row[1])) for row in rows]

    def peak_hours(self) -> PeakHoursOut:
        buckets = self.get_buckets()
        labels = [label for label, _, _ in buckets]
        values = [self._entries_between(start_utc, end_utc) for _, start_utc, end_utc in buckets]
        return PeakHoursOut(labels=labels, values=values)

    def interactive_chart(self, vehicle_type: str | None = None) -> InteractiveChartOut:
        """Build dataset for interactive chart. If `vehicle_type` is provided, only include that type.
        Otherwise include all vehicle types present in the database.
        """
        buckets = self.get_buckets()
        labels = [label for label, _, _ in buckets]
        header: list[str | int | float] = ["Type / Hour", *labels]
        rows: list[list[str | int | float]] = [header]

        # Determine which vehicle types to include
        if vehicle_type and vehicle_type.lower() != 'all':
            types = [vehicle_type]
        else:
            # query distinct vehicle types from ParkingSession
            types = [r[0] for r in self.db.execute(select(ParkingSession.vehicle_type).distinct()).all()]

        for vt in types:
            row: list[str | int | float] = [vt]
            for _, start_utc, end_utc in buckets:
                row.append(self._entries_between_for_type(start_utc, end_utc, vt))
            rows.append(row)
        return InteractiveChartOut(source=rows)

    def _entries_between_for_type(self, start: datetime, end: datetime, vehicle_type: str) -> int:
        count = self.db.scalar(
            select(func.count())
            .select_from(ParkingSession)
            .where(
                ParkingSession.entry_time >= start,
                ParkingSession.entry_time < end,
                ParkingSession.vehicle_type == vehicle_type,
            )
        )
        return int(count or 0)

    def _entries_between(self, start: datetime, end: datetime) -> int:
        count = self.db.scalar(
            select(func.count())
            .select_from(ParkingSession)
            .where(ParkingSession.entry_time >= start, ParkingSession.entry_time < end)
        )
        return int(count or 0)
