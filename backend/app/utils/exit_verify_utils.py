import base64
import hashlib
import hmac
import io
import re

import barcode
from barcode.writer import ImageWriter

# 12-char Code128-friendly hash shown on ticket and scanned at exit
_HASH_RE = re.compile(r"^[A-Z0-9]{8,20}$")


def generate_exit_verify_hash(
    *,
    invoice_id: str,
    session_id: str,
    license_plate: str,
    secret: str,
) -> str:
    """Deterministic exit verification code from entry session + plate."""
    payload = f"{invoice_id}|{session_id}|{license_plate.strip().upper()}"
    digest = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    # 12 uppercase alphanumeric chars — compact for barcode scanners
    return "".join(chr(65 + (int(digest[i : i + 2], 16) % 26)) for i in range(0, 24, 2))


def normalize_verify_hash_scan(raw: str) -> str | None:
    text = (raw or "").strip().upper()
    if not text:
        return None
    if text.startswith("IOT-PARKING:"):
        text = text.split(":", 1)[1].strip()
    if _HASH_RE.match(text):
        return text
    return None


def barcode_data_url(verify_hash: str) -> str:
    code = barcode.get("code128", verify_hash, writer=ImageWriter())
    buf = io.BytesIO()
    code.write(buf, options={"write_text": True, "font_size": 6, "module_height": 10})
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"
