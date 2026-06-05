from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.dashboard import (
    DashboardStatOut,
    InteractiveChartOut,
    PeakHoursOut,
    TrendPointOut,
    VehicleTypePointOut,
)
from app.core.parking_revision import get_parking_revision
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/revision")
def parking_revision() -> dict[str, float]:
    """Frontend polls this; when value changes, reload dashboard / parking / payment."""
    return {"revision": get_parking_revision()}


@router.get("/stats", response_model=list[DashboardStatOut])
def dashboard_stats(db: Session = Depends(get_db)) -> list[DashboardStatOut]:
    return DashboardService(db).stats()


@router.get("/occupancy-trend", response_model=list[TrendPointOut])
def occupancy_trend(db: Session = Depends(get_db)) -> list[TrendPointOut]:
    return DashboardService(db).occupancy_trend()


@router.get("/vehicle-types", response_model=list[VehicleTypePointOut])
def vehicle_types(db: Session = Depends(get_db)) -> list[VehicleTypePointOut]:
    return DashboardService(db).vehicle_types()


@router.get("/peak-hours", response_model=PeakHoursOut)
def peak_hours(db: Session = Depends(get_db)) -> PeakHoursOut:
    return DashboardService(db).peak_hours()


@router.get("/interactive-chart", response_model=InteractiveChartOut)
def interactive_chart(vehicle_type: str | None = None, db: Session = Depends(get_db)) -> InteractiveChartOut:
    """Return interactive chart dataset. Optional `vehicle_type` query filters to a single vehicle type (e.g. 'Car')."""
    return DashboardService(db).interactive_chart(vehicle_type)
