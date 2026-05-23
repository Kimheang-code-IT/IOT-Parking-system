#!/usr/bin/env python3
"""
Lane PC workstation — real hardware mode (host webcam + FastAPI).

Wokwi cannot access the PC camera; use wokwi/parking-gate buttons for simulation.
This script is for real deployment: capture plate / invoice QR, POST to /api/gate/*.

Usage:
  set API_BASE_URL=http://127.0.0.1:8000
  python devices/lane_workstation.py entry --plate 2A-1234
  python devices/lane_workstation.py exit --hash ABCD1234EFGH --plate 2A-1234
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx

BASE = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def post_entry(plate: str, vehicle_type: str = "Car") -> dict:
    body = {
        "licensePlate": plate,
        "vehicleType": vehicle_type,
        "source": "camera",
        "targetDevice": "ENTRY_GATE_01",
    }
    r = httpx.post(f"{BASE}/api/gate/entry/process", json=body, timeout=15.0)
    r.raise_for_status()
    return r.json()


def post_exit(verify_hash: str, plate: str, invoice_id: str | None = None) -> dict:
    body = {
        "verifyHash": verify_hash,
        "licensePlate": plate,
        "source": "camera",
        "targetDevice": "EXIT_GATE_01",
        "requirePaid": True,
    }
    if invoice_id:
        body["invoiceId"] = invoice_id
    r = httpx.post(f"{BASE}/api/gate/exit/process", json=body, timeout=15.0)
    return r.json()


def main() -> None:
    parser = argparse.ArgumentParser(description="Lane PC gate workstation")
    sub = parser.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("entry", help="Camera OCR entry")
    e.add_argument("--plate", required=True)
    e.add_argument("--type", default="Car", choices=["Car", "Motorcycle", "Truck"])
    x = sub.add_parser("exit", help="Camera invoice + plate exit")
    x.add_argument("--hash", required=True, help="verifyHash from printed ticket barcode")
    x.add_argument("--plate", required=True)
    x.add_argument("--invoice", default=None)
    args = parser.parse_args()

    if args.cmd == "entry":
        data = post_entry(args.plate, args.type)
        print(json.dumps(data, indent=2))
        print("\nESP32 at ENTRY_GATE_01 should poll ENTRY_APPROVED via GET /api/iot/commands/next")
    else:
        data = post_exit(args.hash, args.plate, args.invoice)
        print(json.dumps(data, indent=2))
        if data.get("success"):
            print("\nESP32 at EXIT_GATE_01 should poll EXIT_APPROVED")
        else:
            print("\nEXIT_DENIED — check payment or plate match")


if __name__ == "__main__":
    main()
