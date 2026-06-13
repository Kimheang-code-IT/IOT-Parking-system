"""Auto-open exit gate when dashboard payment succeeds (no exit button)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.schemas.gate import GateExitTriggerIn, GateTriggerOut


class GateExitAutoService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()

    def open_after_payment(self, invoice_id: str) -> GateTriggerOut | None:
        from app.services.gate_trigger_service import GateTriggerService

        if not self.settings.gate_exit_use_fifo:
            return None
        body = GateExitTriggerIn.model_validate(
            {
                "source": "simulator",
                "useCamera": False,
                "completeAfterPayment": True,
                "invoiceId": invoice_id,
                "autoCloseSeconds": 20,
            }
        )
        result = GateTriggerService(self.db).exit_trigger(body)
        if result.success:
            return result
        return None
