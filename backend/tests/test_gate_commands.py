"""Gate command lifecycle: delivery, acknowledgement, expiry, device guards."""

from __future__ import annotations

from datetime import timedelta

from app.utils.datetime_utils import utc_now
from tests.conftest import (
    ENTRY_HEADERS,
    ack_command,
    poll_command,
    register_card,
    rfid_entry,
)


def test_delivered_but_unacked_command_expires(client, unique_uid, unique_plate, db):
    register_card(client, unique_uid, unique_plate)
    rfid_entry(client, unique_uid)

    delivered = poll_command(client, ENTRY_HEADERS, "ENTRY_GATE_01")
    assert delivered is not None
    assert delivered["command"] == "ENTRY_APPROVED"

    # The gate went offline after delivery: age the command past its window.
    from app.models.device_command import DeviceCommand

    row = db.get(DeviceCommand, delivered["commandId"])
    past = utc_now() - timedelta(minutes=10)
    row.delivered_at = past
    row.expires_at = past
    db.commit()

    activity = client.get("/api/rfid/gate-activity", params={"deviceCode": "ENTRY_GATE_01"})
    statuses = {c["commandId"]: c["status"] for c in activity.json()["commands"]}
    assert statuses[delivered["commandId"]] == "expired"


def test_late_ack_is_recorded(client, unique_uid, unique_plate, db):
    register_card(client, unique_uid, unique_plate)
    rfid_entry(client, unique_uid)
    delivered = poll_command(client, ENTRY_HEADERS, "ENTRY_GATE_01")

    from app.models.device_command import DeviceCommand

    row = db.get(DeviceCommand, delivered["commandId"])
    row.expires_at = utc_now() - timedelta(minutes=1)
    db.commit()

    # Firmware acked late (gate already opened): the ack is still recorded.
    ack_command(client, ENTRY_HEADERS, "ENTRY_GATE_01", delivered["commandId"], status="completed")

    activity = client.get("/api/rfid/gate-activity", params={"deviceCode": "ENTRY_GATE_01"})
    statuses = {c["commandId"]: c["status"] for c in activity.json()["commands"]}
    assert statuses[delivered["commandId"]] == "acked"


def test_poll_with_mismatched_device_code_400(client):
    response = client.get(
        "/api/iot/commands/next?deviceCode=EXIT_GATE_01",
        headers=ENTRY_HEADERS,
    )
    assert response.status_code == 400


def test_ack_from_wrong_device_404(client, unique_uid, unique_plate):
    register_card(client, unique_uid, unique_plate)
    rfid_entry(client, unique_uid)
    delivered = poll_command(client, ENTRY_HEADERS, "ENTRY_GATE_01")

    response = client.post(
        "/api/iot/commands/ack",
        json={
            "deviceCode": "EXIT_GATE_01",
            "commandId": delivered["commandId"],
            "status": "completed",
        },
        headers={"x-device-code": "EXIT_GATE_01", "x-device-token": "secret-exit-token"},
    )
    assert response.status_code == 404


def test_gate_activity_lists_recent_commands(client, unique_uid, unique_plate):
    register_card(client, unique_uid, unique_plate)
    rfid_entry(client, unique_uid)

    activity = client.get("/api/rfid/gate-activity", params={"limit": 5})
    assert activity.status_code == 200
    commands = activity.json()["commands"]
    assert commands
    assert {"commandId", "deviceCode", "command", "status", "createdAt"} <= set(commands[0].keys())
