from typing import Any, Literal

from pydantic import Field

from app.schemas.common import CamelModel


class DeviceCommandPollOut(CamelModel):
    command_id: str = Field(alias="commandId")
    command: Literal["ENTRY_APPROVED", "EXIT_APPROVED", "EXIT_DENIED"]
    payload: dict[str, Any] = Field(default_factory=dict)
    message: str = ""


class DeviceCommandAckIn(CamelModel):
    device_code: str = Field(alias="deviceCode")
    command_id: str = Field(alias="commandId")
    status: Literal["completed", "failed"] = "completed"
    detail: str | None = None


class GateEventIn(CamelModel):
    device_code: str = Field(alias="deviceCode")
    event: Literal[
        "entry_car_passed",
        "entry_gate_closed",
        "exit_car_passed",
        "exit_gate_closed",
    ]
    session_id: str | None = Field(default=None, alias="sessionId")
    command_id: str | None = Field(default=None, alias="commandId")
