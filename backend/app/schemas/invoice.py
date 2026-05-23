from typing import Literal

from pydantic import Field

from app.schemas.common import CamelModel, ListResult


class InvoiceOut(CamelModel):
    id: str
    date: str
    plate: str
    amount: str
    method: Literal["Cash", "ABA", "KHQR"]
    status: Literal["Paid", "Pending", "Cancelled"]
    entry_time: str | None = Field(default=None, alias="entryTime")
    exit_time: str | None = Field(default=None, alias="exitTime")


class InvoiceListResult(ListResult[InvoiceOut]):
    pass


class InvoiceExitBarcodeOut(CamelModel):
    invoice_id: str = Field(alias="invoiceId")
    verify_hash: str = Field(alias="verifyHash")
    barcode_image: str = Field(alias="barcodeImage")
    plate: str
