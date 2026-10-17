#!/usr/bin/env python3
"""
Full stack integration test: API + SQLite + RFID gates + ABA QR + Nuxt-shaped endpoints.

Run (backend must be on :8000):
  python -m scripts.test_integration

The script registers a temporary RFID card, drives the full entry -> park ->
pay -> exit workflow against the live server, and includes negative cases
(duplicate scan, unknown card, blocked card).
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Override to test through the reverse proxy: IOT_PARKING_API_BASE=http://127.0.0.1
BASE = os.environ.get("IOT_PARKING_API_BASE", "http://127.0.0.1:8000").rstrip("/")
# Device tokens / webhook secret — override when the deployment uses custom
# values (e.g. the Docker stack generated secrets in infrastructure/.env).
ENTRY_TOKEN = os.environ.get("IOT_ENTRY_DEVICE_TOKEN", "secret-entry-token")
EXIT_TOKEN = os.environ.get("IOT_EXIT_DEVICE_TOKEN", "secret-exit-token")
WEBHOOK_SECRET = os.environ.get("PAYMENT_WEBHOOK_SECRET", "change-me-webhook-secret")
ENTRY_HEADERS = {
    "Content-Type": "application/json",
    "x-device-code": "ENTRY_GATE_01",
    "x-device-token": ENTRY_TOKEN,
}
EXIT_HEADERS = {
    "Content-Type": "application/json",
    "x-device-code": "EXIT_GATE_01",
    "x-device-token": EXIT_TOKEN,
}
# Card-management endpoints require this header when RFID_ADMIN_TOKEN is set.
RFID_ADMIN_TOKEN = os.environ.get("RFID_ADMIN_TOKEN", "")
ADMIN_HEADERS = (
    {"Content-Type": "application/json", "x-rfid-admin-token": RFID_ADMIN_TOKEN}
    if RFID_ADMIN_TOKEN
    else {"Content-Type": "application/json"}
)


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


def rfid_scan(gate: str, card_uid: str) -> tuple[int, dict]:
    headers = ENTRY_HEADERS if gate == "entry" else EXIT_HEADERS
    device = "ENTRY_GATE_01" if gate == "entry" else "EXIT_GATE_01"
    return req(
        "POST",
        f"/api/rfid/{gate}-scan",
        {"deviceCode": device, "cardUid": card_uid},
        headers,
    )


def drain_commands(device_code: str, headers: dict) -> int:
    drained = 0
    while True:
        code, cmd = req("GET", f"/api/iot/commands/next?deviceCode={device_code}", headers=headers)
        if code != 200 or not cmd:
            return drained
        req(
            "POST",
            "/api/iot/commands/ack",
            {"deviceCode": device_code, "commandId": cmd["commandId"], "status": "completed"},
            headers,
        )
        drained += 1


def main() -> int:
    stamp = int(time.time()) % 100000
    plate = f"E2E-{stamp}"
    card_uid = f"04E2{stamp:04X}"[:8].ljust(8, "0")
    blocked_uid = f"04BB{stamp:04X}"[:8].ljust(8, "0")

    passed = 0
    total = 0
    print(f"\n=== IOT Parking RFID integration test @ {BASE} ===\n")
    print(f"Card UID: {card_uid}  Plate: {plate}\n")

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
        if check(label, code == 200 and data is not None, str(type(data).__name__)):
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

    # --- RFID card registration ---
    code, card = req(
        "POST",
        "/api/rfid/cards",
        {"cardUid": card_uid, "licensePlate": plate, "vehicleType": "Car", "label": "E2E card"},
        ADMIN_HEADERS,
    )
    total += 1
    if check("10. RFID card registered", code == 200 and card.get("cardUid") == card_uid, str(card)[:80]):
        passed += 1

    code, blocked = req(
        "POST",
        "/api/rfid/cards",
        {"cardUid": blocked_uid, "licensePlate": f"{plate}-B", "vehicleType": "Car"},
        ADMIN_HEADERS,
    )
    total += 1
    if check("11. Second card registered", code == 200):
        passed += 1

    code, _ = req("POST", f"/api/rfid/cards/{blocked_uid}", {"status": "Blocked"}, ADMIN_HEADERS)
    total += 1
    if check("12. Card blocked", code == 200):
        passed += 1

    # Make sure no stale commands are pending for this run.
    drain_commands("ENTRY_GATE_01", ENTRY_HEADERS)
    drain_commands("EXIT_GATE_01", EXIT_HEADERS)

    # --- RFID entry ---
    code, entry = rfid_scan("entry", card_uid)
    total += 1
    entry_ok = code == 200 and entry.get("success") and entry.get("authorized")
    if check("13. RFID entry authorized", entry_ok, entry.get("message", str(entry))[:60]):
        passed += 1

    session_id = entry.get("sessionId")
    invoice_id = entry.get("invoiceId")
    verify_hash = (entry.get("printData") or {}).get("verifyHash")
    receipt_path = entry.get("printSavedPath")

    total += 1
    if check("14. RFID entry receipt saved", bool(receipt_path), receipt_path or ""):
        passed += 1

    code, dup = rfid_scan("entry", card_uid)
    total += 1
    if check("15. Duplicate scan suppressed", code == 200 and dup.get("duplicate") is True):
        passed += 1

    code, unknown = rfid_scan("entry", "DEADBEEF")
    total += 1
    if check("16. Unknown card denied", code == 200 and unknown.get("success") is False):
        passed += 1

    code, blocked_scan = rfid_scan("entry", blocked_uid)
    total += 1
    if check(
        "17. Blocked card denied",
        code == 200 and blocked_scan.get("success") is False and "blocked" in blocked_scan.get("message", "").lower(),
    ):
        passed += 1

    # --- Entry gate command (backend-controlled + ack) ---
    code, cmd = req("GET", "/api/iot/commands/next?deviceCode=ENTRY_GATE_01", headers=ENTRY_HEADERS)
    total += 1
    cmd_ok = (
        code == 200
        and cmd
        and cmd.get("command") == "ENTRY_APPROVED"
        and cmd.get("payload", {}).get("sessionId") == session_id
    )
    if check("18. ENTRY_APPROVED queued for entry gate", bool(cmd_ok), str(cmd)[:70]):
        passed += 1

    if cmd_ok:
        code, ack = req(
            "POST",
            "/api/iot/commands/ack",
            {"deviceCode": "ENTRY_GATE_01", "commandId": cmd["commandId"], "status": "completed"},
            ENTRY_HEADERS,
        )
        total += 1
        if check("19. Command acknowledged", code == 200 and ack.get("success"), ack.get("message", "")):
            passed += 1
    else:
        total += 1
        check("19. Command acknowledged", False, "no command to ack")

    # --- Frontend Payment: active session + ABA QR ---
    code, active = req("GET", f"/api/payment/active-session?plate={plate}")
    total += 1
    active_ok = code == 200 and active.get("plateNumber") == plate
    if check("20. Active session (payment page)", active_ok, active.get("plateNumber", str(active))):
        passed += 1

    amount = float(active.get("amount") or 1.0)
    code, aba = req("GET", f"/api/payment/aba-qr?plateNumber={plate}&amount={amount}&invoiceId={invoice_id or ''}")
    total += 1
    aba_ok = (
        code == 200
        and aba.get("qrImage", "").startswith("data:image")
        and aba.get("status", {}).get("code") == "0"
    )
    if check("21. ABA QR generate (payment page)", aba_ok, aba.get("status", {}).get("message", str(aba))[:80]):
        passed += 1

    code, parking2 = req("GET", f"/api/parking?search={plate}")
    total += 1
    found = any(r.get("licensePlate") == plate for r in parking2.get("data", []))
    if check("22. Parking DB reflects entry", code == 200 and found):
        passed += 1

    # --- RFID exit (payment gating) ---
    if not (session_id and invoice_id):
        print("\n  [SKIP] Exit flow — missing session/invoice\n")
    else:
        code, exit_scan = rfid_scan("exit", card_uid)
        total += 1
        pending_ok = (
            code == 200
            and exit_scan.get("paymentPending") is True
            and float(exit_scan.get("amount") or 0) == amount
        )
        if check("23. Exit fee calculated, gate locked", pending_ok, f"fee=${exit_scan.get('amount')}"):
            passed += 1

        code, no_cmd = req("GET", "/api/iot/commands/next?deviceCode=EXIT_GATE_01", headers=EXIT_HEADERS)
        total += 1
        if check("24. No exit command before payment", code == 200 and not no_cmd):
            passed += 1

        code, webhook = req(
            "POST",
            "/api/payment/webhook",
            {
                "invoiceId": invoice_id,
                "amount": amount,
                "paymentMethod": "KHQR",
                "success": True,
                "transactionRef": f"E2E-{stamp}",
            },
            {"x-webhook-secret": WEBHOOK_SECRET},
        )
        total += 1
        if check("25. Payment webhook (KHQR)", code == 200 and webhook.get("success"), webhook.get("message", "")):
            passed += 1

        # After payment the exit gate command is queued automatically.
        command = None
        for _ in range(10):
            code, command = req("GET", "/api/iot/commands/next?deviceCode=EXIT_GATE_01", headers=EXIT_HEADERS)
            if command:
                break
            time.sleep(1)
        total += 1
        exit_cmd_ok = bool(command) and command.get("command") == "EXIT_APPROVED"
        if check("26. EXIT_APPROVED after payment", exit_cmd_ok, str(command)[:70]):
            passed += 1

        if exit_cmd_ok:
            code, ack = req(
                "POST",
                "/api/iot/commands/ack",
                {"deviceCode": "EXIT_GATE_01", "commandId": command["commandId"], "status": "completed"},
                EXIT_HEADERS,
            )
            total += 1
            if check("27. Exit command acknowledged", code == 200 and ack.get("success")):
                passed += 1
        else:
            total += 1
            check("27. Exit command acknowledged", False, "no command to ack")

        code, status = req("GET", f"/api/iot/session-status?sessionId={session_id}", headers=EXIT_HEADERS)
        total += 1
        if check(
            "28. Session ready for gate (operator open)",
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
        if check("29. Operator open exit gate", code == 200 and gate.get("success"), gate.get("message", "")):
            passed += 1

        code, invoices2 = req("GET", f"/api/invoices?search={invoice_id}")
        total += 1
        paid_inv = next((i for i in invoices2.get("data", []) if i.get("id") == invoice_id), None)
        if check("30. Invoice marked Paid in DB", paid_inv and paid_inv.get("status") == "Paid", str(paid_inv)[:60]):
            passed += 1

    # --- Scan history + gate activity (dashboard RFID page) ---
    code, scans = req("GET", f"/api/rfid/scans?cardUid={card_uid}", headers=ADMIN_HEADERS)
    total += 1
    if check("31. RFID scan history", code == 200 and scans.get("total", 0) >= 3, f"events={scans.get('total')}"):
        passed += 1

    code, activity = req("GET", "/api/rfid/gate-activity?limit=10", headers=ADMIN_HEADERS)
    total += 1
    if check("32. Gate command activity", code == 200 and len(activity.get("commands", [])) > 0):
        passed += 1

    # --- Legacy IoT entry (still supported) ---
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
    if check("33. IoT entry-scan (legacy)", code == 200 and entry.get("success"), str(entry)[:60]):
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
            if check("34. CORS for frontend :3000", "localhost:3000" in allow or allow == "*", allow):
                passed += 1
    except Exception as exc:
        total += 1
        check("34. CORS for frontend :3000", False, str(exc))

    print(f"\n=== Result: {passed}/{total} passed ===\n")
    if passed == total:
        print("All systems connected. Open http://localhost:3000 and verify UI visually.\n")
    else:
        print("Fix FAIL items above, restart: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000\n")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
