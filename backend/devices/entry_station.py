#!/usr/bin/env python3
"""
Entry lane controller — run on the device at the entrance.

Wiring (replace stubs with your hardware drivers):
  - Camera/LPR  -> read_plate()     (ANPR SDK, RTSP OCR, serial OCR module)
  - Printer     -> print_ticket()   (ESC/POS USB, network thermal printer)
  - Gate relay  -> open_entry_gate() optional welcome gate

Usage:
  set API_BASE_URL, DEVICE_CODE=ENTRY_GATE_01, DEVICE_TOKEN=secret-entry-token
  python devices/entry_station.py
  python devices/entry_station.py --plate 2A-1234 --type Car
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from devices.client import ParkingDeviceClient


def read_plate_from_camera() -> tuple[str, str, str]:
    """Return (plate, vehicle_type, description). Integrate your LPR SDK here."""
    plate = input("License plate from camera/LPR: ").strip()
    vehicle_type = input("Vehicle type [Car/Motorcycle/Truck] (default Car): ").strip() or "Car"
    description = input("Description (optional): ").strip() or None
    return plate, vehicle_type, description or ""


def print_ticket(print_data: dict) -> None:
    """Send ESC/POS or vendor SDK. Stub logs thermal receipt for development."""
    print("\n========== PARKING RECEIPT ==========")
    print(f"  DATE:   {print_data.get('receiptDate', '-')}")
    print(f"  FROM:   {print_data.get('entryTime', '-')}")
    print(f"  PLATE:  {print_data.get('plateNumber', '-')}")
    print(f"  TYPE:   {print_data.get('vehicleType', '-')}")
    print(f"  INVOICE: {print_data.get('invoiceNo', '-')}")
    print(f"  EXIT CODE: {print_data.get('verifyHash', '-')}")
    if print_data.get("barcodeImage"):
        print("  [BARCODE IMAGE — send barcodeImage to printer SDK]")
    print("  Keep this ticket for exit verification and payment.")
    print("====================================\n")


def open_entry_gate() -> None:
    """Pulse GPIO relay for entry barrier if you have one."""
    print("[GPIO] Entry gate signal sent.")


def run_once(client: ParkingDeviceClient, plate: str, vehicle_type: str, description: str) -> None:
    client.heartbeat()
    result = client.entry_scan(plate, vehicle_type, description or None)
    if not result.get("success"):
        print(f"Entry failed: {result.get('message')}")
        return
    print(f"Session {result.get('sessionId')} | Invoice {result.get('invoiceId')}")
    print_data = result.get("printData")
    if print_data:
        print_ticket(print_data)
    open_entry_gate()


def main() -> None:
    parser = argparse.ArgumentParser(description="IOT Parking entry station")
    parser.add_argument("--plate", help="Skip camera; use fixed plate for testing")
    parser.add_argument("--type", default="Car", choices=["Car", "Motorcycle", "Truck"])
    parser.add_argument("--description", default="")
    parser.add_argument("--loop", action="store_true", help="Continuous lane loop")
    args = parser.parse_args()

    client = ParkingDeviceClient()
    if not client.device_code or not client.device_token:
        print("Set DEVICE_CODE and DEVICE_TOKEN environment variables.")
        sys.exit(1)

    print(f"Entry station online -> {client.base_url} as {client.device_code}")

    while True:
        if args.plate:
            plate, vtype, desc = args.plate, args.type, args.description
        else:
            plate, vtype, desc = read_plate_from_camera()
        if not plate:
            break
        run_once(client, plate, vtype, desc)
        if not args.loop:
            break
        time.sleep(1)


if __name__ == "__main__":
    main()
