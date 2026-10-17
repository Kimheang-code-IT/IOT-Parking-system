"""Existing invoice / ABA KHQR / payment functionality stays intact.

These tests assert the preserved business logic: invoices, payment status,
ABA KHQR generation (mock), payment verification, webhook security.
"""

from __future__ import annotations

from tests.conftest import ENTRY_HEADERS, EXIT_HEADERS, drain_commands, register_card, rfid_entry


def test_webhook_requires_valid_secret(client):
    response = client.post(
        "/api/payment/webhook",
        json={"invoiceId": "NOPE", "amount": 1.0, "paymentMethod": "KHQR", "success": True},
        headers={"x-webhook-secret": "wrong"},
    )
    assert response.status_code == 401


def test_payment_verify_marks_invoice_paid(client, unique_uid, unique_plate):
    register_card(client, unique_uid, unique_plate)
    entry = rfid_entry(client, unique_uid)

    # Fee is calculated at exit scan (or defaults to the minimum before that).
    active = client.get("/api/payment/active-session", params={"plate": unique_plate})
    assert active.status_code == 200
    body = active.json()
    assert body["plateNumber"] == unique_plate
    assert body["invoiceId"] == entry["invoiceId"]
    assert body["paymentStatus"] == "Pending"

    verified = client.post(
        "/api/payment/verify",
        json={
            "plateNumber": unique_plate,
            "amount": body["amount"],
            "paymentMethod": "ABA PAY",
            "invoiceId": entry["invoiceId"],
        },
    )
    assert verified.status_code == 200
    assert verified.json()["success"] is True

    invoices = client.get("/api/invoices", params={"search": entry["invoiceId"]})
    row = next(i for i in invoices.json()["data"] if i["id"] == entry["invoiceId"])
    assert row["status"] == "Paid"


def test_aba_qr_generation_still_works(client, unique_uid, unique_plate):
    register_card(client, unique_uid, unique_plate)
    entry = rfid_entry(client, unique_uid)

    qr = client.get(
        "/api/payment/aba-qr",
        params={"plateNumber": unique_plate, "amount": 1.0, "invoiceId": entry["invoiceId"]},
    )
    assert qr.status_code == 200
    body = qr.json()
    assert body["qrImage"].startswith("data:image")
    assert body["status"]["code"] == "0"


def test_mock_payment_helper_marks_paid_and_queues_gate(client, unique_uid, unique_plate):
    drain_commands(client, ENTRY_HEADERS, "ENTRY_GATE_01")
    drain_commands(client, EXIT_HEADERS, "EXIT_GATE_01")
    register_card(client, unique_uid, unique_plate)
    entry = rfid_entry(client, unique_uid)

    paid = client.post(
        "/api/gate/exit/mock-payment",
        params={"invoiceId": entry["invoiceId"], "amount": 1.0},
    )
    assert paid.status_code == 200
    assert paid.json()["success"] is True

    command = client.get(
        "/api/iot/commands/next?deviceCode=EXIT_GATE_01",
        headers=EXIT_HEADERS,
    )
    assert command.status_code == 200
    body = command.json()
    assert body is not None
    assert body["command"] == "EXIT_APPROVED"


def test_health_and_bank_info(client):
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    bank = client.get("/api/payment/bank-info")
    assert bank.status_code == 200
    assert bank.json()["name"]
