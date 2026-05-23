from datetime import date
from typing import Literal

from pydantic import Field

from app.schemas.common import CamelModel, ListResult


class ParkingEntryOut(CamelModel):
    id: str
    license_plate: str = Field(alias="licensePlate")
    type: Literal["Car", "Motorcycle", "Truck"]
    entry_time: str = Field(alias="entryTime")
    exit_time: str = Field(alias="exitTime")
    duration: str
    status: Literal["Active", "Completed"]


class ParkingListResult(ListResult[ParkingEntryOut]):
    pass


class ParkingListParams(CamelModel):
    page: int = 1
    limit: int = 50
    sort_by: str | None = Field(default=None, alias="sortBy")
    sort_order: Literal["asc", "desc"] | None = Field(default=None, alias="sortOrder")
    search: str | None = None
    status: list[str] | None = None
    type: list[str] | None = None
    start_date: date | None = Field(default=None, alias="startDate")
    end_date: date | None = Field(default=None, alias="endDate")
