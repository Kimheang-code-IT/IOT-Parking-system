from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class CamelModel(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        from_attributes=True,
        alias_generator=lambda field_name: _to_camel(field_name),
        ser_json_by_alias=True,
    )


def _to_camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


class ListResult(CamelModel, Generic[T]):
    data: list[T]
    total: int
    aggregates: dict[str, Any] | None = None


class ErrorDetail(CamelModel):
    success: bool = False
    message: str
