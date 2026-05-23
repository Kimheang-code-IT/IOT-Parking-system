import base64
import hashlib
import hmac
import io
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import httpx
import qrcode
from PIL import Image, ImageDraw

from app.core.config import get_settings
from app.schemas.payment import AbaPayStatusOut, AbaQrOut

logger = logging.getLogger(__name__)

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_ABA_LOGO = _BACKEND_ROOT / "assets" / "aba_bank_logo.png"


class AbaPayError(Exception):
    def __init__(self, code: str, message: str, trace_id: str | None = None) -> None:
        self.code = code
        self.message = message
        self.trace_id = trace_id
        super().__init__(message)


class AbaPayService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def generate_qr(
        self,
        amount: float,
        plate_number: str,
        invoice_id: str | None = None,
    ) -> AbaQrOut:
        if amount < 0.01:
            raise AbaPayError("48", "Amount must be at least 0.01 USD.")

        tran_id = self._build_tran_id(plate_number, invoice_id)
        if self.settings.use_aba_mock:
            logger.info("ABA QR mock mode for plate=%s amount=%s", plate_number, amount)
            return self._mock_qr(amount, plate_number, tran_id)

        if not (self.settings.aba_pay_merchant_id and self.settings.aba_pay_api_key):
            raise AbaPayError("96", "ABA PayWay credentials are not configured.")

        return self._call_payway(amount, plate_number, tran_id, invoice_id)

    def _build_tran_id(self, plate_number: str, invoice_id: str | None) -> str:
        base = re.sub(r"[^A-Za-z0-9]", "", (invoice_id or plate_number).upper())
        stamp = datetime.now(timezone.utc).strftime("%H%M%S")
        return f"{base[:12]}{stamp}"[:20]

    def _mock_qr(self, amount: float, plate_number: str, tran_id: str) -> AbaQrOut:
        qr_string = (
            f"00020101021230510016abaakhppxxx@abaa01151250212145328460208ABA"
            f"Bank5204824953038405404{amount:.2f}5802KH5925PARKING {plate_number[:12]}"
        )
        bank_logo = self._bank_logo_data_url()
        qr_image = self._png_data_url(qr_string, embed_logo=True)
        deeplink = f"abamobilebank://ababank.com?type=payway&qrcode={quote(qr_string)}"

        return AbaQrOut(
            qr_string=qr_string,
            qr_image=qr_image,
            bank_logo=bank_logo,
            logo_embedded=bool(bank_logo),
            abapay_deeplink=deeplink,
            app_store="https://itunes.apple.com/al/app/aba-mobile-bank/id968860649?mt=8",
            play_store="https://play.google.com/store/apps/details?id=com.paygo24.ibank",
            amount=round(amount, 2),
            currency=self.settings.aba_pay_currency,
            tran_id=tran_id,
            status=AbaPayStatusOut(
                code="0",
                message="Mock QR for local testing (set ABA_PAY_USE_MOCK=false and credentials for sandbox).",
                trace_id=f"mock-{tran_id}",
            ),
        )

    def _resolve_logo_path(self) -> Path | None:
        custom = (self.settings.aba_pay_bank_logo_path or "").strip()
        if custom:
            path = Path(custom)
            if path.is_file():
                return path
        if _DEFAULT_ABA_LOGO.is_file():
            return _DEFAULT_ABA_LOGO
        return None

    def _bank_logo_data_url(self) -> str | None:
        path = self._resolve_logo_path()
        if not path:
            return None
        raw = path.read_bytes()
        b64 = base64.b64encode(raw).decode("ascii")
        suffix = path.suffix.lower().lstrip(".")
        mime = "image/png" if suffix == "png" else "image/jpeg" if suffix in {"jpg", "jpeg"} else "image/png"
        return f"data:{mime};base64,{b64}"

    def _embed_logo(self, qr_img: Image.Image) -> Image.Image:
        """Center ABA logo as a circle (KHQR-style) on the QR code."""
        path = self._resolve_logo_path()
        if not path:
            return qr_img

        logo = Image.open(path).convert("RGBA")
        qr_rgb = qr_img.convert("RGB")
        qr_w, qr_h = qr_rgb.size

        # ~16% of QR — smaller center logo (KHQR-style, still scannable)
        logo_size = max(24, int(min(qr_w, qr_h) * 0.16))
        logo = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)

        circle_mask = Image.new("L", (logo_size, logo_size), 0)
        ImageDraw.Draw(circle_mask).ellipse((0, 0, logo_size, logo_size), fill=255)
        logo_circle = Image.new("RGBA", (logo_size, logo_size), (0, 0, 0, 0))
        logo_circle.paste(logo, (0, 0), circle_mask)

        outer = int(logo_size * 1.08)
        badge = Image.new("RGBA", (outer, outer), (0, 0, 0, 0))
        white_bg = Image.new("RGBA", (outer, outer), (0, 0, 0, 0))
        ImageDraw.Draw(white_bg).ellipse((0, 0, outer, outer), fill=(255, 255, 255, 255))
        badge = Image.alpha_composite(badge, white_bg)
        inset = (outer - logo_size) // 2
        badge.paste(logo_circle, (inset, inset), logo_circle)

        pos = ((qr_w - outer) // 2, (qr_h - outer) // 2)
        qr_rgba = qr_rgb.convert("RGBA")
        qr_rgba.paste(badge, pos, badge)
        return qr_rgba.convert("RGB")

    def _png_data_url(self, content: str, *, embed_logo: bool = False) -> str:
        img = qrcode.make(content)
        if embed_logo:
            img = self._embed_logo(img)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/png;base64,{b64}"

    def _call_payway(
        self,
        amount: float,
        plate_number: str,
        tran_id: str,
        invoice_id: str | None,
    ) -> AbaQrOut:
        req_time = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        items_json = json.dumps(
            [{"name": f"Parking {plate_number}", "quantity": 1, "price": round(amount, 2)}]
        )
        items_b64 = base64.b64encode(items_json.encode()).decode()
        callback_b64 = ""
        if self.settings.aba_pay_callback_url:
            callback_b64 = base64.b64encode(self.settings.aba_pay_callback_url.encode()).decode()

        payload = {
            "req_time": req_time,
            "merchant_id": self.settings.aba_pay_merchant_id,
            "tran_id": tran_id,
            "amount": round(amount, 2),
            "currency": self.settings.aba_pay_currency,
            "purchase_type": "purchase",
            "payment_option": self.settings.aba_pay_payment_option,
            "items": items_b64,
            "callback_url": callback_b64 or None,
            "lifetime": self.settings.aba_pay_qr_lifetime_minutes,
            "qr_image_template": self.settings.aba_pay_qr_template,
            "first_name": "",
            "last_name": "",
            "email": "",
            "phone": "",
            "return_deeplink": None,
            "custom_fields": None,
            "return_params": None,
            "payout": None,
        }
        payload["hash"] = self._build_hash(payload)

        url = f"{self.settings.aba_pay_api_url.rstrip('/')}/api/payment-gateway/v1/payments/generate-qr"
        with httpx.Client(timeout=30.0) as client:
            response = client.post(url, json=payload, headers={"Content-Type": "application/json"})
            data = response.json()

        status = data.get("status") or {}
        if status.get("code") != "0":
            raise AbaPayError(
                str(status.get("code", "8")),
                status.get("message", "ABA PayWay error."),
                status.get("trace_id"),
            )

        bank_logo = self._bank_logo_data_url()
        return AbaQrOut(
            qr_string=data["qrString"],
            qr_image=data["qrImage"],
            bank_logo=bank_logo,
            logo_embedded=True,
            abapay_deeplink=data.get("abapay_deeplink"),
            app_store=data.get("app_store"),
            play_store=data.get("play_store"),
            amount=float(data.get("amount", amount)),
            currency=data.get("currency", self.settings.aba_pay_currency),
            tran_id=tran_id,
            status=AbaPayStatusOut(
                code=str(status.get("code", "0")),
                message=status.get("message", "Success."),
                trace_id=status.get("trace_id"),
            ),
        )

    def _build_hash(self, payload: dict) -> str:
        amount_str = str(payload["amount"])
        parts = [
            payload["req_time"],
            payload["merchant_id"],
            payload["tran_id"],
            amount_str,
            payload.get("items") or "",
            payload.get("first_name") or "",
            payload.get("last_name") or "",
            payload.get("email") or "",
            payload.get("phone") or "",
            payload.get("purchase_type") or "",
            payload.get("payment_option") or "",
            payload.get("callback_url") or "",
            payload.get("return_deeplink") or "",
            payload.get("currency") or "",
            payload.get("custom_fields") or "",
            payload.get("return_params") or "",
            payload.get("payout") or "",
            str(payload.get("lifetime") or ""),
            payload.get("qr_image_template") or "",
        ]
        b4hash = "".join(parts)
        digest = hmac.new(
            self.settings.aba_pay_api_key.encode(),
            b4hash.encode(),
            hashlib.sha512,
        ).digest()
        return base64.b64encode(digest).decode()
