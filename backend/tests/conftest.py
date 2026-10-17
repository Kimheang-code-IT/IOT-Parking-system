"""Shared fixtures for the backend integration tests.

The suite runs against an isolated temporary SQLite database (never the dev
database) and boots the real FastAPI app, so every test exercises the actual
routers, services, security dependencies and command queue.
"""

from __future__ import annotations

import itertools
import os
import sys
import tempfile
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

# --- environment must be set before app modules import settings -------------
_TEST_DB_DIR = Path(tempfile.mkdtemp(prefix="iot_parking_tests_"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_TEST_DB_DIR / 'test_parking.db').as_posix()}"
os.environ["RATE_LIMIT"] = "100000/minute"  # the suite fires many requests
os.environ["RFID_ADMIN_TOKEN"] = ""
os.environ["RFID_SCAN_COOLDOWN_SECONDS"] = "8"
os.environ["GATE_COMMAND_TIMEOUT_SECONDS"] = "180"
os.environ["PAYMENT_WEBHOOK_SECRET"] = "test-webhook-secret"
os.environ["IOT_ENTRY_DEVICE_TOKEN"] = "secret-entry-token"
os.environ["IOT_EXIT_DEVICE_TOKEN"] = "secret-exit-token"
os.environ["ABA_PAY_USE_MOCK"] = "true"
os.environ["SEED_DEMO_DATA"] = "false"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

WEBHOOK_SECRET = "test-webhook-secret"

ENTRY_HEADERS = {
    "x-device-code": "ENTRY_GATE_01",
    "x-device-token": "secret-entry-token",
}
EXIT_HEADERS = {
    "x-device-code": "EXIT_GATE_01",
    "x-device-token": "secret-exit-token",
}
WEBHOOK_HEADERS = {"x-webhook-secret": WEBHOOK_SECRET}


@pytest.fixture(scope="session")
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


_uid_counter = itertools.count(1)


@pytest.fixture
def unique_uid() -> str:
    """A fresh valid 4-byte card UID for each test."""
    return f"04A1B2{next(_uid_counter):02X}"


@pytest.fixture
def unique_plate() -> str:
    return f"RF-{next(_uid_counter):05X}"


@pytest.fixture
def db():
    from app.core.database import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def register_card(client: TestClient, card_uid: str, plate: str, **extra) -> dict:
    response = client.post(
        "/api/rfid/cards",
        json={"cardUid": card_uid, "licensePlate": plate, "vehicleType": "Car", **extra},
    )
    assert response.status_code == 200, response.text
    return response.json()


def rfid_entry(client: TestClient, card_uid: str) -> dict:
    response = client.post(
        "/api/rfid/entry-scan",
        json={"deviceCode": "ENTRY_GATE_01", "cardUid": card_uid},
        headers=ENTRY_HEADERS,
    )
    assert response.status_code == 200, response.text
    return response.json()


def rfid_exit(client: TestClient, card_uid: str) -> dict:
    response = client.post(
        "/api/rfid/exit-scan",
        json={"deviceCode": "EXIT_GATE_01", "cardUid": card_uid},
        headers=EXIT_HEADERS,
    )
    assert response.status_code == 200, response.text
    return response.json()


def poll_command(client: TestClient, headers: dict, device_code: str) -> dict | None:
    response = client.get(
        f"/api/iot/commands/next?deviceCode={device_code}",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


def ack_command(client: TestClient, headers: dict, device_code: str, command_id: str, status="completed") -> None:
    response = client.post(
        "/api/iot/commands/ack",
        json={"deviceCode": device_code, "commandId": command_id, "status": status},
        headers=headers,
    )
    assert response.status_code == 200, response.text


def drain_commands(client: TestClient, headers: dict, device_code: str) -> int:
    """Poll + ack every queued command so a test starts from a clean queue."""
    drained = 0
    while True:
        command = poll_command(client, headers, device_code)
        if command is None:
            return drained
        ack_command(client, headers, device_code, command["commandId"])
        drained += 1
