from app.schemas.common import CamelModel


class DashboardStatOut(CamelModel):
    label: str
    value: str
    icon: str


class TrendPointOut(CamelModel):
    name: str
    value: int


class VehicleTypePointOut(CamelModel):
    name: str
    value: int


class PeakHoursOut(CamelModel):
    labels: list[str]
    values: list[int]


class InteractiveChartOut(CamelModel):
    source: list[list[str | int | float]]
