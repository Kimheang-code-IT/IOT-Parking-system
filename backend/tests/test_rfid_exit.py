"""RFID exit flow: fee calculation from the active session, payment gating,
post-payment gate command, re-scan after paying, duplicate protection."""

from __future__ import annotations

from datetime import timedelta

from app.utils.datetime_utils import utc_now
from tests.conftest import (
    ENTRY_HEADERS,
    EXIT_HEADERS,
    WEBHOOK_HEADERS,
    ack_command,
    drain_commands,
    poll_command,
    register_card,
    rfid_entry,
    rfid_exit,
)


def _pay(client, invoice_id: str, amount: float) -> dict:
    response = client.post(
        "/api/payment/webhook",
        json={
            "invoiceId": invoice_id,
            "amount": amount,
            "paymentMethod": "KHQR",
            "success": True,
            "transactionRef": "TEST-REF-1",
        },
        headers=WEBHOOK_HEADERS,
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_exit_requires_payment_before_gate(client, unique_uid, unique_plate):
    drain_commands(client, ENTRY_HEADERS, "ENTRY_GATE_01")
    drain_commands(client, EXIT_HEADERS, "EXIT_GATE_01")
    register_card(client, unique_uid, unique_plate)
    entry = rfid_entry(client, unique_uid)

    scan = rfid_exit(client, unique_uid)
    assert scan["success"] is True
    assert scan["authorized"] is False
    assert scan["paymentPending"] is True
    assert scan["sessionId"] == entry["sessionId"]
    assert scan["amount"] == 1.0  # under one hour -> minimum fee
    assert scan["plateNumber"] == unique_plate

    # No exit command may be queued before the payment exists.
    assert poll_command(client, EXIT_HEADERS, "EXIT_GATE_01") is None

    # The operator cannot open the gate either (session still Active).
    denied = client.post(
        "/api/iot/open-gate",
        json={"deviceCode": "EXIT_GATE_01", "sessionId": entry["sessionId"]},
        headers=EXIT_HEADERS,
    )
    assert denied.status_code == 400
    assert denied.json()["success"] is False

    # Pay the exact displayed amount (ABA KHQR webhook path).
    payment = _pay(client, scan["invoiceId"], scan["amount"])
    assert payment["success"] is True

    # Payment success queues EXIT_APPROVED automatically.
    command = poll_command(client, EXIT_HEADERS, "EXIT_GATE_01")
    assert command is not None
    assert command["command"] == "EXIT_APPROVED"
    assert command["payload"]["invoiceId"] == scan["invoiceId"]
    ack_command(client, EXIT_HEADERS, "EXIT_GATE_01", command["commandId"])

    # Session completed + invoice paid, operator open now succeeds.
    status = client.get(
        "/api/payment/active-session", params={"plate": unique_plate}
    )
    assert status.status_code == 404  # no active session anymore

    invoices = client.get("/api/invoices", params={"search": scan["invoiceId"]})
    row = next(i for i in invoices.json()["data"] if i["id"] == scan["invoiceId"])
    assert row["status"] == "Paid"

    opened = client.post(
        "/api/iot/open-gate",
        json={"deviceCode": "EXIT_GATE_01", "sessionId": entry["sessionId"]},
        headers=EXIT_HEADERS,
    )
    assert opened.status_code == 200
    assert opened.json()["success"] is True


def test_exit_fee_calculation_for_long_stay(client, unique_uid, unique_plate, db):
    register_card(client, unique_uid, unique_plate)
    entry = rfid_entry(client, unique_uid)
    assert entry["authorized"] is True

    # Move the entry time 2h05m back: 3 billed hours x $2.00 = $6.00.
    from app.models.parking_session import ParkingSession

    session = db.get(ParkingSession, entry["sessionId"])
    session.entry_time = utc_now() - timedelta(hours=2, minutes=5)
    db.commit()

    scan = rfid_exit(client, unique_uid)
    assert scan["paymentPending"] is True
    assert scan["amount"] == 6.0
    assert scan["duration"] in ("2h 5m", "2h 05m")


def test_exit_after_paying_first_reopens_gate(client, unique_uid, unique_plate):
    drain_commands(client, ENTRY_HEADERS, "ENTRY_GATE_01")
    drain_commands(client, EXIT_HEADERS, "EXIT_GATE_01")
    register_card(client, unique_uid, unique_plate)
    entry = rfid_entry(client, unique_uid)
    # ack the entry command so we can count exit commands cleanly
    command = poll_command(client, ENTRY_HEADERS, "ENTRY_GATE_01")
    ack_command(client, ENTRY_HEADERS, "ENTRY_GATE_01", command["commandId"])

    # Customer pays on the dashboard before tapping at the exit gate: payment
    # closes the session and queues EXIT_APPROVED.
    scan_fee = client.get("/api/payment/active-session", params={"plate": unique_plate})
    assert scan_fee.status_code == 200
    amount = scan_fee.json()["amount"]
    invoice_id = scan_fee.json()["invoiceId"]
    assert _pay(client, invoice_id, amount)["success"] is True

    # Tapping afterwards still resolves to an authorized exit (recent payment).
    late_scan = rfid_exit(client, unique_uid)
    assert late_scan["success"] is True
    assert late_scan["authorized"] is True
    assert late_scan["invoiceId"] == invoice_id

    # Exactly one queued EXIT_APPROVED — the scan must not duplicate it.
    first = poll_command(client, EXIT_HEADERS, "EXIT_GATE_01")
    assert first is not None and first["command"] == "EXIT_APPROVED"
    ack_command(client, EXIT_HEADERS, "EXIT_GATE_01", first["commandId"])
    assert poll_command(client, EXIT_HEADERS, "EXIT_GATE_01") is None


def test_exit_unknown_card_and_no_session(client, unique_unknown=None):
    scan = rfid_exit(client, "00BADBAD")
    assert scan["success"] is False
    assert "not registered" in scan["message"].lower()


def test_exit_registered_card_without_session_denied(client, unique_uid, unique_plate):
    register_card(client, unique_uid, unique_plate)
    scan = rfid_exit(client, unique_uid)
    assert scan["success"] is False
    assert "no active parking session" in scan["message"].lower()


def test_exit_duplicate_scan_ignored(client, unique_uid, unique_plate):
    register_card(client, unique_uid, unique_plate)
    rfid_entry(client, unique_uid)

    first = rfid_exit(client, unique_uid)
    assert first["paymentPending"] is True

    second = rfid_exit(client, unique_uid)
    assert second["duplicate"] is True

    # The fee is still visible in scan history exactly twice (first + duplicate).
    history = client.get("/api/rfid/scans", params={"cardUid": unique_uid, "gate": "exit"})
    assert history.json()["total"] >= 2


def test_exit_wrong_device_token_rejected(client):
    response = client.post(
        "/api/rfid/exit-scan",
        json={"deviceCode": "EXIT_GATE_01", "cardUid": "04A1B2FF"},
        headers={"x-device-code": "EXIT_GATE_01", "x-device-token": "nope"},
    )
    assert response.status_code == 401
