"""
HTTP client for parking IoT edge devices (camera, gate, printer, scanner).
Run on Raspberry Pi, ESP32 gateway, or industrial PC at the lane.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


class ParkingDeviceClient:
    def __init__(
        self,
        base_url: str | None = None,
        device_code: str | None = None,
        device_token: str | None = None,
    ) -> None:
        self.base_url = (base_url or os.getenv("API_BASE_URL", "http://localhost:8000")).rstrip("/")
        self.device_code = device_code or os.getenv("DEVICE_CODE", "")
        self.device_token = device_token or os.getenv("DEVICE_TOKEN", "")

    def _headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "x-device-code": self.device_code,
            "x-device-token": self.device_token,
        }
        if extra:
            headers.update(extra)
        return headers

    def _request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        query: str = "",
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}{query}"
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, headers=self._headers(extra_headers), method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            payload = exc.read().decode()
            try:
                detail = json.loads(payload)
            except json.JSONDecodeError:
                detail = {"message": payload}
            raise RuntimeError(detail.get("message") or detail) from exc

    def heartbeat(self) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/iot/heartbeat",
            body={"deviceCode": self.device_code},
        )

    def entry_scan(
        self,
        license_plate: str,
        vehicle_type: str = "Car",
        vehicle_description: str | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/iot/entry-scan",
            body={
                "deviceCode": self.device_code,
                "licensePlate": license_plate,
                "vehicleType": vehicle_type,
                "vehicleDescription": vehicle_description,
            },
        )

    def exit_verify(self, verify_hash: str, license_plate: str, invoice_id: str | None = None) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/iot/exit-verify",
            body={
                "deviceCode": self.device_code,
                "verifyHash": verify_hash,
                "licensePlate": license_plate,
                "invoiceId": invoice_id,
            },
        )

    def session_status(self, session_id: str) -> dict[str, Any]:
        return self._request("GET", "/api/iot/session-status", query=f"?sessionId={session_id}")

    def open_gate(self, session_id: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/iot/open-gate",
            body={"deviceCode": self.device_code, "sessionId": session_id},
        )

    def payment_webhook(
        self,
        invoice_id: str,
        amount: float,
        *,
        payment_method: str = "KHQR",
        transaction_ref: str | None = None,
        webhook_secret: str | None = None,
    ) -> dict[str, Any]:
        secret = webhook_secret or os.getenv("PAYMENT_WEBHOOK_SECRET", "")
        return self._request(
            "POST",
            "/api/payment/webhook",
            body={
                "invoiceId": invoice_id,
                "amount": amount,
                "paymentMethod": payment_method,
                "transactionRef": transaction_ref,
                "success": True,
            },
            extra_headers={"x-webhook-secret": secret},
        )
