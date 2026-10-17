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
    app_env: str = "development"  # development | production (logging/health label)
    log_level: str = "DEBUG"  # DEBUG for local dev; production compose sets INFO
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

    # Thermal receipt (dev: saved to disk; see services/gate_receipt_printer.py)
    gate_receipt_dir: str = "data/receipts"

    # RFID access control
    # Duplicate-scan protection: a second accepted scan of the same card at the
    # same gate inside this window is logged and answered with duplicate=true.
    rfid_scan_cooldown_seconds: int = 8
    # Optional shared secret for the card-management endpoints
    # (GET/POST /api/rfid/cards, /api/rfid/scans, /api/rfid/gate-activity).
    # Empty = open (local dev only). Set it in production and send header
    # x-rfid-admin-token from the dashboard/reverse proxy.
    rfid_admin_token: str = ""

    # Gate commands older than this are expired server-side (safety: a stale
    # "open gate" approval must never execute much later). Keep aligned with
    # the firmware PARKING_COMMAND_VALIDITY_MS.
    gate_command_timeout_seconds: int = 180

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
    def safe_database_url(self) -> str:
        """Database URL with the password masked — safe for logs."""
        try:
            from sqlalchemy.engine.url import make_url

            url = make_url(self.database_url)
            if url.password:
                url = url.set(password="***")
            return url.render_as_string(hide_password=True)
        except Exception:
            return self.database_url.split("@")[-1] if "@" in self.database_url else self.database_url

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
