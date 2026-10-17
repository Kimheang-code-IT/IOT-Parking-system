"""RFID entry flow: session + invoice + ENTRY_APPROVED command, duplicates,
re-entry with an active session, and disconnected-device command expiry."""

from __future__ import annotations

from datetime import timedelta

from app.utils.datetime_utils import utc_now
from tests.conftest import (
    ENTRY_HEADERS,
    ack_command,
    drain_commands,
    poll_command,
    register_card,
    rfid_entry,
)


def test_entry_scan_creates_session_invoice_and_gate_command(client, unique_uid, unique_plate):
    drain_commands(client, ENTRY_HEADERS, "ENTRY_GATE_01")
    register_card(client, unique_uid, unique_plate)

    scan = rfid_entry(client, unique_uid)
    assert scan["success"] is True
    assert scan["authorized"] is True
    assert scan["duplicate"] is False
    assert scan["plateNumber"] == unique_plate
    assert scan["sessionId"]
    assert scan["invoiceId"]
    assert scan["printData"]["verifyHash"]
    assert scan["printSavedPath"]

    # Parking history reflects the entry.
    listing = client.get("/api/parking", params={"search": unique_plate})
    assert listing.status_code == 200
    rows = listing.json()["data"]
    assert any(row["licensePlate"] == unique_plate and row["status"] == "Active" for row in rows)

    # The backend queued ENTRY_APPROVED for the entry gate.
    command = poll_command(client, ENTRY_HEADERS, "ENTRY_GATE_01")
    assert command is not None
    assert command["command"] == "ENTRY_APPROVED"
    assert command["payload"]["sessionId"] == scan["sessionId"]
    assert command["payload"]["invoiceId"] == scan["invoiceId"]

    ack_command(client, ENTRY_HEADERS, "ENTRY_GATE_01", command["commandId"])

    # Acknowledged: nothing left to deliver.
    assert poll_command(client, ENTRY_HEADERS, "ENTRY_GATE_01") is None

    activity = client.get("/api/rfid/gate-activity", params={"deviceCode": "ENTRY_GATE_01"})
    assert activity.status_code == 200
    statuses = [c["status"] for c in activity.json()["commands"]]
    assert "acked" in statuses


def test_duplicate_scan_is_ignored(client, unique_uid, unique_plate):
    register_card(client, unique_uid, unique_plate)
    first = rfid_entry(client, unique_uid)
    assert first["authorized"] is True

    second = rfid_entry(client, unique_uid)
    assert second["duplicate"] is True
    assert second["authorized"] is False

    # No second session was created.
    listing = client.get("/api/parking", params={"search": unique_plate})
    active = [r for r in listing.json()["data"] if r["status"] == "Active"]
    assert len(active) == 1


def test_entry_scan_unknown_card_denied(client):
    scan = rfid_entry(client, "FEEDFACE")
    assert scan["success"] is False
    assert "not registered" in scan["message"].lower()


def test_entry_rescan_with_active_session_reopens_gate(client, unique_uid, unique_plate, db):
    drain_commands(client, ENTRY_HEADERS, "ENTRY_GATE_01")
    register_card(client, unique_uid, unique_plate)
    first = rfid_entry(client, unique_uid)
    # ack the first command so the resume path queues a fresh one
    command = poll_command(client, ENTRY_HEADERS, "ENTRY_GATE_01")
    ack_command(client, ENTRY_HEADERS, "ENTRY_GATE_01", command["commandId"])

    # Backdate the previous scan event so duplicate protection does not fire.
    from app.models.rfid_scan_event import RfidScanEvent

    for row in db.query(RfidScanEvent).filter(RfidScanEvent.card_uid == unique_uid).all():
        row.created_at = utc_now() - timedelta(minutes=5)
    db.commit()

    second = rfid_entry(client, unique_uid)
    assert second["authorized"] is True
    assert second["sessionId"] == first["sessionId"]  # same session, no duplicate

    resumed = poll_command(client, ENTRY_HEADERS, "ENTRY_GATE_01")
    assert resumed is not None
    assert resumed["command"] == "ENTRY_APPROVED"
    assert resumed["payload"]["sessionId"] == first["sessionId"]


def test_wrong_device_token_rejected(client, unique_uid):
    response = client.post(
        "/api/rfid/entry-scan",
        json={"deviceCode": "ENTRY_GATE_01", "cardUid": unique_uid},
        headers={"x-device-code": "ENTRY_GATE_01", "x-device-token": "wrong"},
    )
    assert response.status_code == 401


def test_device_code_mismatch_rejected(client, unique_uid):
    response = client.post(
        "/api/rfid/entry-scan",
        json={"deviceCode": "EXIT_GATE_01", "cardUid": unique_uid},
        headers=ENTRY_HEADERS,
    )
    assert response.status_code == 400


def test_disconnected_device_command_expires(client, unique_uid, unique_plate, db):
    """A gate that never polls must not receive the approval later."""
    drain_commands(client, ENTRY_HEADERS, "ENTRY_GATE_01")
    register_card(client, unique_uid, unique_plate)
    scan = rfid_entry(client, unique_uid)
    assert scan["authorized"] is True

    # Simulate the device being offline: the command ages past its window.
    from app.models.device_command import DeviceCommand

    rows = (
        db.query(DeviceCommand)
        .filter(
            DeviceCommand.device_code == "ENTRY_GATE_01",
            DeviceCommand.status == "pending",
        )
        .all()
    )
    assert rows, "expected a pending ENTRY_APPROVED"
    past = utc_now() - timedelta(minutes=10)
    for row in rows:
        row.created_at = past
        row.expires_at = past
    db.commit()

    # The gate reconnects: the server refuses to deliver the stale approval.
    assert poll_command(client, ENTRY_HEADERS, "ENTRY_GATE_01") is None

    activity = client.get("/api/rfid/gate-activity", params={"deviceCode": "ENTRY_GATE_01"})
    statuses = [c["status"] for c in activity.json()["commands"]]
    assert "expired" in statuses


def test_ack_unknown_command_404(client):
    response = client.post(
        "/api/iot/commands/ack",
        json={"deviceCode": "ENTRY_GATE_01", "commandId": "not-a-command", "status": "completed"},
        headers=ENTRY_HEADERS,
    )
    assert response.status_code == 404


def test_entry_gate_events_and_heartbeat(client):
    heartbeat = client.post(
        "/api/iot/heartbeat",
        json={"deviceCode": "ENTRY_GATE_01"},
        headers=ENTRY_HEADERS,
    )
    assert heartbeat.status_code == 200
    assert heartbeat.json()["success"] is True

    event = client.post(
        "/api/iot/gate/event",
        json={"deviceCode": "ENTRY_GATE_01", "event": "entry_car_passed"},
        headers=ENTRY_HEADERS,
    )
    assert event.status_code == 200

    fault = client.post(
        "/api/iot/gate/event",
        json={"deviceCode": "ENTRY_GATE_01", "event": "gate_fault", "detail": "passage blocked"},
        headers=ENTRY_HEADERS,
    )
    assert fault.status_code == 200
