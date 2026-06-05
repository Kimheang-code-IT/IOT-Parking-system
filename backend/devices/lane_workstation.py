#!/usr/bin/env python3
"""Lane PC — one-button entry/exit with OpenCV (run on same PC as FastAPI)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BASE = os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("entry", help="One button: camera OCR, print, open gate")
    e.add_argument("--plate", help="Skip camera, use fixed plate")
    x = sub.add_parser("exit", help="One button: camera invoice+plate, wait pay")
    x.add_argument("--hash", help="verifyHash from ticket")
    x.add_argument("--plate", help="license plate")
    x.add_argument("--no-mock-pay", action="store_true")
    m = sub.add_parser("mock-pay", help="Test: mark invoice paid")
    m.add_argument("invoice_id")
    m.add_argument("--amount", type=float, default=None)
    args = parser.parse_args()

    if args.cmd == "entry":
        body = {"source": "camera", "useCamera": args.plate is None, "autoCloseSeconds": 60}
        if args.plate:
            body["source"] = "manual"
            body["mockPlate"] = args.plate
            body["useCamera"] = False
        r = httpx.post(f"{BASE}/api/gate/entry/trigger", json=body, timeout=60.0)
        print(json.dumps(r.json(), indent=2))
    elif args.cmd == "exit":
        body = {
            "source": "camera",
            "useCamera": True,
            "mockPayment": not args.no_mock_pay,
            "waitForPayment": True,
            "waitPaymentSeconds": 120,
        }
        if args.hash:
            body["verifyHash"] = args.hash
            body["useCamera"] = False
        if args.plate:
            body["mockPlate"] = args.plate
        r = httpx.post(f"{BASE}/api/gate/exit/trigger", json=body, timeout=180.0)
        print(json.dumps(r.json(), indent=2))
    else:
        params = {"invoiceId": args.invoice_id}
        if args.amount is not None:
            params["amount"] = args.amount
        r = httpx.post(f"{BASE}/api/gate/exit/mock-payment", params=params, timeout=30.0)
        print(json.dumps(r.json(), indent=2))


if __name__ == "__main__":
    main()
