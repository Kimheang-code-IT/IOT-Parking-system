from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.parking import ParkingListResult
from app.services.parking_service import ParkingService

router = APIRouter(prefix="/api/parking", tags=["parking"])


@router.get("", response_model=ParkingListResult)
def list_parking(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    sort_by: str | None = Query(None, alias="sortBy"),
    sort_order: str | None = Query(None, alias="sortOrder"),
    search: str | None = None,
    status: list[str] | None = Query(None),
    vehicle_type: list[str] | None = Query(None, alias="type"),
    entry_date_from: date | None = Query(None, alias="entryDateFrom"),
    entry_date_to: date | None = Query(None, alias="entryDateTo"),
    exit_date_from: date | None = Query(None, alias="exitDateFrom"),
    exit_date_to: date | None = Query(None, alias="exitDateTo"),
    db: Session = Depends(get_db),
) -> ParkingListResult:
    data, total, aggregates = ParkingService(db).list_sessions(
        page=page,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
        search=search,
        status=status,
        vehicle_type=vehicle_type,
        entry_date_from=entry_date_from,
        entry_date_to=entry_date_to,
        exit_date_from=exit_date_from,
        exit_date_to=exit_date_to,
    )
    return ParkingListResult(data=data, total=total, aggregates=aggregates)
