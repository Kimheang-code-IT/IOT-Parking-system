"""RFID card registry: registration, status changes, listing, duplicate UIDs."""

from __future__ import annotations

from tests.conftest import ENTRY_HEADERS, register_card, rfid_entry


def test_register_and_list_card(client, unique_uid, unique_plate):
    card = register_card(client, unique_uid, unique_plate, label="Staff car")
    assert card["cardUid"] == unique_uid
    assert card["licensePlate"] == unique_plate
    assert card["status"] == "Active"
    assert card["label"] == "Staff car"

    listing = client.get("/api/rfid/cards", params={"search": unique_uid})
    assert listing.status_code == 200
    body = listing.json()
    assert body["total"] == 1
    assert body["data"][0]["cardUid"] == unique_uid


def test_register_duplicate_card_conflict(client, unique_uid, unique_plate):
    register_card(client, unique_uid, unique_plate)
    response = client.post(
        "/api/rfid/cards",
        json={"cardUid": unique_uid, "licensePlate": "OTHER-1", "vehicleType": "Car"},
    )
    assert response.status_code == 409
    assert "already registered" in response.json()["message"]


def test_register_invalid_uid_rejected(client):
    response = client.post(
        "/api/rfid/cards",
        json={"cardUid": "XYZ", "licensePlate": "AA-11", "vehicleType": "Car"},
    )
    assert response.status_code == 400


def test_uid_normalized_with_separators(client, unique_plate):
    uid = "04:A1:B2:FD"
    response = client.post(
        "/api/rfid/cards",
        json={"cardUid": uid, "licensePlate": unique_plate, "vehicleType": "Car"},
    )
    assert response.status_code == 200
    assert response.json()["cardUid"] == "04A1B2FD"


def test_blocked_card_is_denied_at_entry(client, unique_uid, unique_plate):
    register_card(client, unique_uid, unique_plate)

    update = client.post(
        f"/api/rfid/cards/{unique_uid}",
        json={"status": "Blocked"},
    )
    assert update.status_code == 200
    assert update.json()["status"] == "Blocked"

    scan = rfid_entry(client, unique_uid)
    assert scan["success"] is False
    assert "blocked" in scan["message"].lower()

    # Re-activating the card restores access (verified by the entry flow tests).
    reactivate = client.post(f"/api/rfid/cards/{unique_uid}", json={"status": "Active"})
    assert reactivate.status_code == 200
    assert reactivate.json()["status"] == "Active"


def test_update_unknown_card_404(client):
    response = client.post("/api/rfid/cards/DEADBEEF", json={"label": "x"})
    assert response.status_code == 404


def test_scan_history_records_rejections(client, unique_uid, unique_plate):
    register_card(client, unique_uid, unique_plate)
    client.post(
        "/api/rfid/entry-scan",
        json={"deviceCode": "ENTRY_GATE_01", "cardUid": "AABBCCDD"},
        headers=ENTRY_HEADERS,
    )

    history = client.get("/api/rfid/scans", params={"cardUid": "AABBCCDD"})
    assert history.status_code == 200
    body = history.json()
    assert body["total"] >= 1
    assert body["data"][0]["accepted"] is False
    assert "not registered" in (body["data"][0]["reason"] or "").lower()


def test_admin_token_guard_enforced_when_configured(client, monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "rfid_admin_token", "top-secret")
    try:
        denied = client.get("/api/rfid/cards")
        assert denied.status_code == 401

        allowed = client.get("/api/rfid/cards", headers={"x-rfid-admin-token": "top-secret"})
        assert allowed.status_code == 200
    finally:
        monkeypatch.setattr(settings, "rfid_admin_token", "")
