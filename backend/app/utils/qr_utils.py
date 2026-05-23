import base64
import io
import re

import qrcode

# Plain invoice id — exit scanner sends this to POST /api/iot/exit-verify
_INVOICE_ID_RE = re.compile(r"^IN-\d+$", re.IGNORECASE)


def invoice_qr_payload(invoice_id: str) -> str:
    return invoice_id.strip().upper()


def parse_invoice_qr_scan(raw: str) -> str | None:
    """Normalize scanner input to an invoice id (plain id or iot-parking:IN-000001)."""
    text = (raw or "").strip()
    if not text:
        return None
    if text.lower().startswith("iot-parking:"):
        text = text.split(":", 1)[1].strip()
    if _INVOICE_ID_RE.match(text):
        return text.upper()
    return None


def invoice_qr_data_url(invoice_id: str, *, box_size: int = 6, border: int = 2) -> str:
    payload = invoice_qr_payload(invoice_id)
    img = qrcode.make(payload, box_size=box_size, border=border)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"
