"""Save thermal receipt to disk (dev) — wire ESC/POS USB in production."""

from __future__ import annotations

import logging
from pathlib import Path

from app.core.config import _BACKEND_ROOT, get_settings
from app.schemas.iot import PrintDataOut

logger = logging.getLogger(__name__)


class GateReceiptPrinter:
    @staticmethod
    def print_ticket(data: PrintDataOut) -> str:
        settings = get_settings()
        out_dir = _BACKEND_ROOT / settings.gate_receipt_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{data.invoice_no}.txt"
        lines = [
            "========== PARKING RECEIPT ==========",
            f"  DATE:    {data.receipt_date}",
            f"  FROM:    {data.entry_time}",
            f"  PLATE:   {data.plate_number}",
            f"  TYPE:    {data.vehicle_type}",
            f"  INVOICE: {data.invoice_no}",
            f"  EXIT CODE: {data.verify_hash}",
            "  [BARCODE ON TICKET]",
            "====================================",
        ]
        text = "\n".join(lines)
        path.write_text(text, encoding="utf-8")
        logger.info("Receipt saved to %s", path)
        print("\n" + text + "\n")
        return str(path)
