from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_SQLITE_PATH = _BACKEND_ROOT / "data" / "iot_parking.db"
_DEFAULT_SQLITE_URL = f"sqlite:///{_DEFAULT_SQLITE_PATH.as_posix()}"


class Settings(BaseSettings):
    """Local development settings (SQLite + mock-friendly defaults)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = _DEFAULT_SQLITE_URL
    cors_origins: str = "http://localhost:3000"
    rate_limit: str = "120/minute"
    total_parking_spots: int = 200
    rate_per_hour: float = 2.0
    minimum_fee: float = 1.0
    app_name: str = "IOT Parking API"
    payment_webhook_secret: str = "change-me-webhook-secret"
    exit_verify_secret: str = ""
    api_base_url: str = "http://localhost:8000"

    iot_entry_device_token: str = "secret-entry-token"
    iot_exit_device_token: str = "secret-exit-token"

    # ABA PayWay sandbox — mock QR by default; set merchant + key for live sandbox QR
    aba_pay_use_mock: bool = True
    aba_pay_api_url: str = "https://checkout-sandbox.payway.com.kh"
    aba_pay_merchant_id: str = ""
    aba_pay_api_key: str = ""
    aba_pay_callback_url: str = ""
    aba_pay_currency: str = "USD"
    aba_pay_payment_option: str = "abapay_khqr"
    aba_pay_qr_template: str = "template3_color"
    aba_pay_qr_lifetime_minutes: int = 30
    aba_pay_bank_logo_path: str = ""

    # When true, bootstrap/seed adds sample sessions (off by default — use scripts/reset_db.py --demo)
    seed_demo_data: bool = False

    gate_use_camera: bool = True
    gate_camera_index: int = 0
    gate_camera_warmup_ms: int = 1500
    gate_camera_prepare_seconds: int = 10
    gate_camera_scan_seconds: int = 30
    gate_show_camera_preview: bool = True
    gate_tesseract_cmd: str = ""
    gate_camera_fallback_plate: str = "WK-SIM01"
    gate_receipt_dir: str = "data/receipts"
    gate_auto_mock_payment: bool = True
    gate_exit_use_fifo: bool = True

    @model_validator(mode="after")
    def set_callback_url(self) -> "Settings":
        if not self.aba_pay_callback_url:
            self.aba_pay_callback_url = f"{self.api_base_url.rstrip('/')}/api/payment/webhook"
        if not self.exit_verify_secret:
            self.exit_verify_secret = self.payment_webhook_secret
        return self

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def sqlite_path(self) -> Path | None:
        if not self.is_sqlite:
            return None
        raw = self.database_url.removeprefix("sqlite:///")
        return Path(raw)

    @property
    def use_aba_mock(self) -> bool:
        if self.aba_pay_use_mock:
            return True
        return not (self.aba_pay_merchant_id and self.aba_pay_api_key)

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if settings.is_sqlite and settings.sqlite_path:
        settings.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    return settings
