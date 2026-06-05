#!/usr/bin/env python3
"""
Full stack integration test: API + SQLite + IoT + ABA QR + frontend-shaped endpoints.

Run (backend must be on :8000):
  python -m scripts.test_integration
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BASE = "http://127.0.0.1:8000"
WEBHOOK_SECRET = "change-me-webhook-secret"
ENTRY_HEADERS = {
    "Content-Type": "application/json",
    "x-device-code": "ENTRY_GATE_01",
    "x-device-token": "secret-entry-token",
}
EXIT_HEADERS = {
    "Content-Type": "application/json",
    "x-device-code": "EXIT_GATE_01",
    "x-device-token": "secret-exit-token",
}
SIM_HEADERS = {
    "Content-Type": "application/json",
    "x-device-code": "GATE_SIM_01",
    "x-device-token": "secret-entry-token",
}


def req(
    method: str,
    path: str,
    body: dict | None = None,
    headers: dict | None = None,
    timeout: int = 15,
) -> tuple[int, dict]:
    url = f"{BASE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    h = {"Content-Type": "application/json", **(headers or {})}
    request = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            code = resp.getcode()
            raw = resp.read().decode()
            if code == 204 or not raw:
                return code, {}
            return code, json.loads(raw)
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, {"error": raw}


def check(name: str, cond: bool, detail: str = "") -> bool:
    tag = "PASS" if cond else "FAIL"
    print(f"  [{tag}] {name}" + (f" — {detail}" if detail else ""))
    return cond


def main() -> int:
    plate = f"E2E-{int(time.time()) % 100000}"
    passed = 0
    total = 0
    print(f"\n=== IOT Parking integration test @ {BASE} ===\n")
    print(f"Test plate: {plate}\n")

    # --- Backend alive ---
    code, health = req("GET", "/health")
    total += 1
    if check("1. Health", code == 200 and health.get("status") == "ok"):
        passed += 1

    # --- Dashboard (frontend Home) ---
    for path, label in [
        ("/api/dashboard/stats", "2. Dashboard stats"),
        ("/api/dashboard/occupancy-trend", "3. Occupancy trend"),
        ("/api/dashboard/vehicle-types", "4. Vehicle types"),
        ("/api/dashboard/peak-hours", "5. Peak hours"),
        ("/api/dashboard/interactive-chart", "6. Interactive chart"),
    ]:
        code, data = req("GET", path)
        total += 1
        ok = code == 200 and data is not None
        if check(label, ok, str(type(data).__name__)):
            passed += 1

    # --- Tables (frontend Parkings / Invoices) ---
    code, parking = req("GET", "/api/parking?limit=5")
    total += 1
    if check("7. Parking list", code == 200 and "data" in parking, f"total={parking.get('total')}"):
        passed += 1

    code, invoices = req("GET", "/api/invoices?limit=5")
    total += 1
    if check("8. Invoices list", code == 200 and "data" in invoices, f"total={invoices.get('total')}"):
        passed += 1

    code, bank = req("GET", "/api/payment/bank-info")
    total += 1
    if check("9. Bank info", code == 200 and bank.get("name"), bank.get("name", "")):
        passed += 1

    # --- Gate ENTRY (Wokwi parking-gate — one button) ---
    code, gate_entry = req(
        "POST",
        "/api/gate/entry/trigger",
        {
            "source": "simulator",
            "mockPlate": plate,
            "vehicleType": "Car",
            "autoCloseSeconds": 60,
        },
        timeout=30,
    )
    total += 1
    ge_ok = code == 200 and gate_entry.get("success")
    if check("10. Gate entry trigger (Wokwi)", ge_ok, gate_entry.get("message", str(gate_entry))[:60]):
        passed += 1

    session_id = gate_entry.get("sessionId")
    invoice_id = gate_entry.get("invoiceId")
    verify_hash = gate_entry.get("verifyHash")
    receipt_path = gate_entry.get("printSavedPath")

    total += 1
    if check("11. Receipt printed to disk", bool(receipt_path), receipt_path or ""):
        passed += 1

    # Legacy IoT entry (still supported)
    code, entry = req(
        "POST",
        "/api/iot/entry-scan",
        {
            "deviceCode": "ENTRY_GATE_01",
            "licensePlate": plate + "-LEG",
            "vehicleType": "Car",
        },
        ENTRY_HEADERS,
    )
    total += 1
    if check("12. IoT entry-scan (legacy)", code == 409 or code == 200, "duplicate plate ok on -LEG"):
        passed += 1

    if not session_id:
        session_id = entry.get("sessionId")
    if not invoice_id:
        invoice_id = entry.get("invoiceId")
    print_data = {"verifyHash": verify_hash} if verify_hash else entry.get("printData")
    total += 1
    if check(
        "13. Verify hash on ticket",
        bool(print_data and print_data.get("verifyHash")),
        (print_data or {}).get("verifyHash", ""),
    ):
        passed += 1

    # --- Frontend Payment: active session + ABA QR ---
    code, active = req("GET", f"/api/payment/active-session?plate={plate}")
    total += 1
    active_ok = code == 200 and active.get("plateNumber") == plate
    if check("14. Active session (payment page)", active_ok, active.get("plateNumber", str(active))):
        passed += 1

    amount = float(active.get("amount") or 1.0)
    code, aba = req("GET", f"/api/payment/aba-qr?plateNumber={plate}&amount={amount}&invoiceId={invoice_id or ''}")
    total += 1
    aba_ok = (
        code == 200
        and aba.get("qrImage", "").startswith("data:image")
        and aba.get("status", {}).get("code") == "0"
    )
    if check(
        "15. ABA QR generate (payment page)",
        aba_ok,
        aba.get("status", {}).get("message", str(aba))[:80],
    ):
        passed += 1

    code, parking2 = req("GET", f"/api/parking?search={plate}")
    total += 1
    found = any(r.get("licensePlate") == plate for r in parking2.get("data", []))
    if check("16. Parking DB reflects entry", code == 200 and found):
        passed += 1

    if not (session_id and invoice_id and verify_hash):
        print("\n  [SKIP] Exit flow — missing session/invoice/verifyHash\n")
    else:
        # --- Gate EXIT (Wokwi one button + mock pay) ---
        exit_barcode = f"IOT-PARKING:{plate}|{invoice_id}|{verify_hash}"
        code, gate_exit = req(
            "POST",
            "/api/gate/exit/trigger",
            {
                "source": "simulator",
                "useCamera": False,
                "exitBarcode": exit_barcode,
                "mockPayment": True,
                "waitForPayment": True,
                "waitPaymentSeconds": 30,
            },
            timeout=120,
        )
        total += 1
        gx_ok = code == 200 and gate_exit.get("success")
        fee = float(gate_exit.get("amount") or amount)
        if check("17. Gate exit trigger (Wokwi)", gx_ok, f"fee=${fee:.2f} {gate_exit.get('message','')[:40]}"):
            passed += 1

        # --- IoT EXIT (legacy verify + webhook) ---
        verify_hash = (print_data or {}).get("verifyHash") or verify_hash
        code, exit_res = req(
            "POST",
            "/api/iot/exit-verify",
            {
                "deviceCode": "EXIT_GATE_01",
                "verifyHash": verify_hash,
                "licensePlate": plate,
            },
            EXIT_HEADERS,
        )
        total += 1
        exit_ok = code == 200 and exit_res.get("success")
        fee = float(exit_res.get("amount") or amount)
        if check("18. IoT exit verify (legacy)", exit_ok, f"fee=${fee:.2f}"):
            passed += 1

        code, webhook = req(
            "POST",
            "/api/payment/webhook",
            {
                "invoiceId": invoice_id,
                "amount": fee,
                "paymentMethod": "KHQR",
                "success": True,
            },
            {"x-webhook-secret": WEBHOOK_SECRET},
        )
        total += 1
        if check("19. Payment webhook (legacy)", code == 200 and webhook.get("success"), webhook.get("message", "")):
            passed += 1

        code, status = req("GET", f"/api/iot/session-status?sessionId={session_id}", headers=EXIT_HEADERS)
        total += 1
        if check(
            "20. Session ready for gate",
            code == 200 and status.get("canOpenGate") is True,
            f"paid={status.get('paymentStatus')}",
        ):
            passed += 1

        code, gate = req(
            "POST",
            "/api/iot/open-gate",
            {"deviceCode": "EXIT_GATE_01", "sessionId": session_id},
            EXIT_HEADERS,
        )
        total += 1
        if check("21. Open exit gate", code == 200 and gate.get("success"), gate.get("message", "")):
            passed += 1

        code, invoices2 = req("GET", f"/api/invoices?search={invoice_id}")
        total += 1
        paid_inv = next((i for i in invoices2.get("data", []) if i.get("id") == invoice_id), None)
        if check("22. Invoice marked Paid in DB", paid_inv and paid_inv.get("status") == "Paid", str(paid_inv)):
            passed += 1

        code, cmd = req("GET", "/api/iot/commands/next?deviceCode=GATE_SIM_01", headers=SIM_HEADERS)
        total += 1
        if check("23. Device command poll (no pending ok)", code in (200, 204), str(cmd)[:40] or "empty"):
            passed += 1

    # --- CORS header for frontend ---
    try:
        cors_req = urllib.request.Request(
            f"{BASE}/api/parking",
            method="OPTIONS",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        with urllib.request.urlopen(cors_req, timeout=5) as resp:
            allow = resp.headers.get("Access-Control-Allow-Origin", "")
            total += 1
            if check("24. CORS for frontend :3000", "localhost:3000" in allow or allow == "*", allow):
                passed += 1
    except Exception as exc:
        total += 1
        check("24. CORS for frontend :3000", False, str(exc))

    print(f"\n=== Result: {passed}/{total} passed ===\n")
    if passed == total:
        print("All systems connected. Open http://localhost:3000 and verify UI visually.\n")
    else:
        print("Fix FAIL items above, restart: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000\n")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
