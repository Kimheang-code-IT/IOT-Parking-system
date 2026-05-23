from decimal import Decimal
import math

from app.core.config import get_settings


class ParkingFeeService:
    def __init__(self) -> None:
        settings = get_settings()
        self.rate_per_hour = Decimal(str(settings.rate_per_hour))
        self.minimum_fee = Decimal(str(settings.minimum_fee))

    def calculate_fee(self, total_minutes: int) -> Decimal:
        if total_minutes < 60:
            return self.minimum_fee
        billed_hours = math.ceil(total_minutes / 60)
        return Decimal(billed_hours) * self.rate_per_hour
