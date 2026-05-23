#!/usr/bin/env python3
"""
Exit lane controller — run on the device at the exit.

Flow:
  1. Barcode scanner reads verify hash from ticket
  2. Camera reads license plate
  3. POST /api/iot/exit-verify (verifyHash + licensePlate)
  4. Show fee / trigger KHQR on payment terminal
  5. Poll /api/iot/session-status until canOpenGate=true
     (payment terminal calls POST /api/payment/webhook when paid)
  6. POST /api/iot/open-gate

Usage:
  set DEVICE_CODE=EXIT_GATE_01, DEVICE_TOKEN=secret-exit-token
  python devices/exit_station.py
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from devices.client import ParkingDeviceClient


def read_exit_barcode() -> str:
    """Integrate USB barcode scanner (keyboard wedge) or serial scanner."""
    raw = input("Scan exit barcode / verify code: ").strip()
    if raw.lower().startswith("iot-parking:"):
        return raw.split(":", 1)[1].strip().upper()
    return raw.upper()


def read_plate_camera() -> str:
    return input("License plate from exit camera: ").strip()


def trigger_payment_terminal(invoice_id: str, amount: float) -> None:
    """
    Tell your ABA/KHQR terminal to show QR for this amount.
    When paid, the terminal (or bank) must POST /api/payment/webhook.
    """
    print(f"[PAYMENT] Display KHQR/ABA for invoice {invoice_id} amount ${amount:.2f}")


def open_exit_gate() -> None:
    print("[GPIO] Exit gate opening.")


def wait_for_payment(client: ParkingDeviceClient, session_id: str, timeout_sec: int = 300) -> bool:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        status = client.session_status(session_id)
        if status.get("canOpenGate"):
            return True
        if status.get("paymentStatus") == "Paid" and status.get("sessionStatus") == "Completed":
            return True
        print(f"  Waiting payment... {status.get('paymentStatus')} / {status.get('sessionStatus')}")
        time.sleep(2)
    return False


def run_exit_flow(client: ParkingDeviceClient, verify_hash: str, plate: str, poll_timeout: int) -> None:
    client.heartbeat()
    verify = client.exit_verify(verify_hash, plate)
    if not verify.get("success"):
        print(f"Exit verify failed: {verify.get('message')}")
        return

    session_id = verify["sessionId"]
    amount = verify.get("amount", 0)
    print(f"Fee ${amount:.2f} | duration {verify.get('duration')} | pay status {verify.get('paymentStatus')}")

    if verify.get("paymentStatus") == "Paid":
        gate = client.open_gate(session_id)
        print(gate.get("message", "Gate opened."))
        open_exit_gate()
        return

    trigger_payment_terminal(verify.get("invoiceId") or verify_hash, amount)

    if wait_for_payment(client, session_id, poll_timeout):
        gate = client.open_gate(session_id)
        print(gate.get("message", "Gate opened."))
        open_exit_gate()
    else:
        print("Payment timeout — gate stays closed.")


def main() -> None:
    parser = argparse.ArgumentParser(description="IOT Parking exit station")
    parser.add_argument("--hash", help="Exit verify hash from barcode")
    parser.add_argument("--invoice", help="(legacy) invoice id")
    parser.add_argument("--plate", help="Plate from camera")
    parser.add_argument("--poll-timeout", type=int, default=300)
    parser.add_argument("--loop", action="store_true")
    args = parser.parse_args()

    client = ParkingDeviceClient()
    if not client.device_code or not client.device_token:
        print("Set DEVICE_CODE and DEVICE_TOKEN (use EXIT_GATE_01 / secret-exit-token).")
        sys.exit(1)

    print(f"Exit station online -> {client.base_url} as {client.device_code}")

    while True:
        verify_hash = args.hash or args.invoice or read_exit_barcode()
        plate = args.plate or read_plate_camera()
        if not verify_hash or not plate:
            break
        run_exit_flow(client, verify_hash, plate, args.poll_timeout)
        args.hash = args.invoice = args.plate = None
        if not args.loop:
            break


if __name__ == "__main__":
    main()
