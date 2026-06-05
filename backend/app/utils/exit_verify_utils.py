import base64
import hashlib
import hmac
import io
import re
from dataclasses import dataclass

import barcode
from barcode.writer import ImageWriter

from app.services.plate_service import normalize_plate

BARCODE_PREFIX = "IOT-PARKING:"
# 12-char Code128-friendly hash shown on ticket and scanned at exit
_HASH_RE = re.compile(r"^[A-Z0-9]{8,20}$")


@dataclass(frozen=True)
class ExitBarcodePayload:
    license_plate: str
    invoice_id: str
    verify_hash: str


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
    return "".join(chr(65 + (int(digest[i : i + 2], 16) % 26)) for i in range(0, 24, 2))


def format_exit_barcode_payload(
    *,
    license_plate: str,
    invoice_id: str,
    verify_hash: str,
) -> str:
    """Code128 payload: plate + invoice + hash for exit gate scan."""
    plate = normalize_plate(license_plate)
    inv = invoice_id.strip().upper()
    h = verify_hash.strip().upper()
    return f"{BARCODE_PREFIX}{plate}|{inv}|{h}"


def parse_exit_barcode(raw: str) -> ExitBarcodePayload | None:
    text = (raw or "").strip()
    if not text:
        return None
    upper = text.upper()
    if upper.startswith(BARCODE_PREFIX.upper()):
        body = text[len(BARCODE_PREFIX) :].strip()
        parts = [p.strip() for p in body.split("|") if p.strip()]
        if len(parts) != 3:
            return None
        plate, invoice_id, verify_hash = parts
        h = normalize_verify_hash_scan(verify_hash) or verify_hash.upper()
        return ExitBarcodePayload(
            license_plate=normalize_plate(plate),
            invoice_id=invoice_id.upper(),
            verify_hash=h,
        )
    h = normalize_verify_hash_scan(text)
    if h:
        return ExitBarcodePayload(license_plate="", invoice_id="", verify_hash=h)
    return None


def validate_exit_barcode_against_invoice(
    scan: ExitBarcodePayload,
    *,
    invoice_id: str,
    license_plate: str,
    verify_hash: str,
    session_id: str,
    secret: str,
) -> str | None:
    """Return error message if barcode fields do not match the invoice record."""
    if not scan.license_plate or not scan.invoice_id:
        return None
    expected = generate_exit_verify_hash(
        invoice_id=invoice_id,
        session_id=session_id,
        license_plate=license_plate,
        secret=secret,
    )
    if scan.verify_hash.upper() != expected.upper():
        return "Exit barcode hash does not match invoice."
    if scan.invoice_id.upper() != invoice_id.strip().upper():
        return "Exit barcode invoice does not match."
    if normalize_plate(scan.license_plate) != normalize_plate(license_plate):
        return "Exit barcode plate does not match invoice."
    return None


def normalize_verify_hash_scan(raw: str) -> str | None:
    text = (raw or "").strip().upper()
    if not text:
        return None
    if text.startswith(BARCODE_PREFIX.upper()):
        parsed = parse_exit_barcode(raw)
        return parsed.verify_hash if parsed else None
    if _HASH_RE.match(text):
        return text
    return None


def barcode_data_url(payload: str) -> str:
    code = barcode.get("code128", payload, writer=ImageWriter())
    buf = io.BytesIO()
    code.write(buf, options={"write_text": True, "font_size": 6, "module_height": 10})
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"
