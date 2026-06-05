from pydantic import Field

from app.schemas.common import CamelModel


class ActiveSessionOut(CamelModel):
    plate_number: str = Field(alias="plateNumber")
    vehicle_type: str = Field(alias="vehicleType")
    entry_time: str = Field(alias="entryTime")
    duration: str
    amount: float
    invoice_id: str | None = Field(default=None, alias="invoiceId")
    session_id: str | None = Field(default=None, alias="sessionId")
    payment_status: str | None = Field(default=None, alias="paymentStatus")


class PaymentVerifyIn(CamelModel):
    plate_number: str = Field(alias="plateNumber")
    amount: float
    payment_method: str = Field(alias="paymentMethod")
    invoice_id: str | None = Field(default=None, alias="invoiceId")


class PaymentVerifyOut(CamelModel):
    success: bool
    message: str
    invoice_id: str | None = Field(default=None, alias="invoiceId")
    transaction_ref: str | None = Field(default=None, alias="transactionRef")


class PaymentWebhookIn(CamelModel):
    invoice_id: str = Field(alias="invoiceId")
    amount: float
    payment_method: str = Field(default="KHQR", alias="paymentMethod")
    transaction_ref: str | None = Field(default=None, alias="transactionRef")
    success: bool = True


class BankInfoOut(CamelModel):
    name: str
    account_name: str = Field(alias="accountName")
    account_number: str = Field(alias="accountNumber")


class AbaPayStatusOut(CamelModel):
    code: str
    message: str
    trace_id: str | None = Field(default=None, alias="traceId")


class AbaQrOut(CamelModel):
    qr_string: str = Field(alias="qrString")
    qr_image: str = Field(alias="qrImage")
    bank_logo: str | None = Field(default=None, alias="bankLogo")
    logo_embedded: bool = Field(default=False, alias="logoEmbedded")
    abapay_deeplink: str | None = Field(default=None, alias="abapayDeeplink")
    app_store: str | None = Field(default=None, alias="appStore")
    play_store: str | None = Field(default=None, alias="playStore")
    amount: float
    currency: str = "USD"
    tran_id: str = Field(alias="tranId")
    status: AbaPayStatusOut
