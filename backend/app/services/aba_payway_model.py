"""ABA PayWay generate-QR request model (PayWay API v1).

Hash order matches ABA documentation:
req_time + merchant_id + tran_id + amount + items + first_name + last_name + email
+ phone + purchase_type + payment_option + callback_url + return_deeplink + currency
+ custom_fields + return_params + payout + lifetime + qr_image_template
"""

from __future__ import annotations

import base64
import hashlib
import hmac
from dataclasses import dataclass
from typing import Any


@dataclass
class AbaPaywayQrRequest:
    """PayWay `POST /api/payment-gateway/v1/payments/generate-qr` body."""

    amount: float
    currency: str
    hash: str
    lifetime: int
    merchant_id: str
    payment_option: str
    qr_image_template: str
    req_time: str
    tran_id: str
    callback_url: str | None = None
    custom_fields: str | None = None
    email: str | None = None
    first_name: str | None = None
    items: str | None = None
    last_name: str | None = None
    payout: str | None = None
    phone: str | None = None
    purchase_type: str | None = None
    return_deeplink: str | None = None
    return_params: str | None = None

    def hash_payload(self) -> str:
        amount_str = str(self.amount)
        parts = [
            self.req_time,
            self.merchant_id,
            self.tran_id,
            amount_str,
            self.items or "",
            self.first_name or "",
            self.last_name or "",
            self.email or "",
            self.phone or "",
            self.purchase_type or "",
            self.payment_option or "",
            self.callback_url or "",
            self.return_deeplink or "",
            self.currency or "",
            self.custom_fields or "",
            self.return_params or "",
            self.payout or "",
            str(self.lifetime or ""),
            self.qr_image_template or "",
        ]
        return "".join(parts)

    def compute_hash(self, api_key: str) -> str:
        digest = hmac.new(api_key.encode(), self.hash_payload().encode(), hashlib.sha512).digest()
        return base64.b64encode(digest).decode()

    def with_hash(self, api_key: str) -> AbaPaywayQrRequest:
        return AbaPaywayQrRequest(
            amount=self.amount,
            currency=self.currency,
            hash=self.compute_hash(api_key),
            lifetime=self.lifetime,
            merchant_id=self.merchant_id,
            payment_option=self.payment_option,
            qr_image_template=self.qr_image_template,
            req_time=self.req_time,
            tran_id=self.tran_id,
            callback_url=self.callback_url,
            custom_fields=self.custom_fields,
            email=self.email,
            first_name=self.first_name,
            items=self.items,
            last_name=self.last_name,
            payout=self.payout,
            phone=self.phone,
            purchase_type=self.purchase_type,
            return_deeplink=self.return_deeplink,
            return_params=self.return_params,
        )

    def to_api_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "req_time": self.req_time,
            "merchant_id": self.merchant_id,
            "tran_id": self.tran_id,
            "amount": self.amount,
            "currency": self.currency,
            "purchase_type": self.purchase_type,
            "payment_option": self.payment_option,
            "items": self.items,
            "lifetime": self.lifetime,
            "qr_image_template": self.qr_image_template,
            "hash": self.hash,
        }
        optional = {
            "callback_url": self.callback_url,
            "custom_fields": self.custom_fields,
            "email": self.email,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "phone": self.phone,
            "return_deeplink": self.return_deeplink,
            "return_params": self.return_params,
            "payout": self.payout,
        }
        for key, value in optional.items():
            if value is not None:
                result[key] = value
        return result

    @classmethod
    def from_api_dict(cls, obj: dict[str, Any]) -> AbaPaywayQrRequest:
        return cls(
            amount=float(obj["amount"]),
            currency=str(obj["currency"]),
            hash=str(obj["hash"]),
            lifetime=int(obj["lifetime"]),
            merchant_id=str(obj["merchant_id"]),
            payment_option=str(obj["payment_option"]),
            qr_image_template=str(obj["qr_image_template"]),
            req_time=str(obj["req_time"]),
            tran_id=str(obj["tran_id"]),
            callback_url=obj.get("callback_url"),
            custom_fields=obj.get("custom_fields"),
            email=obj.get("email"),
            first_name=obj.get("first_name"),
            items=obj.get("items"),
            last_name=obj.get("last_name"),
            payout=obj.get("payout"),
            phone=obj.get("phone"),
            purchase_type=obj.get("purchase_type"),
            return_deeplink=obj.get("return_deeplink"),
            return_params=obj.get("return_params"),
        )
