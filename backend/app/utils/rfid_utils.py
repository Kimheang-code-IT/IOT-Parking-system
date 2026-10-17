"""RFID UID normalization helpers."""

import re

_SEPARATOR_RE = re.compile(r"[:;\-\s]+")
_HEX_RE = re.compile(r"^[0-9A-F]{8,14}$")


def normalize_card_uid(raw: str) -> str:
    """Uppercases a card UID and strips separators.

    Accepts 4-byte (8 hex chars) and 7-byte (14 hex chars) MIFARE UIDs.
    Raises ValueError for anything else.
    """
    cleaned = _SEPARATOR_RE.sub("", (raw or "").strip()).upper()
    if not cleaned:
        raise ValueError("Card UID is required.")
    if len(cleaned) % 2 != 0 or not _HEX_RE.match(cleaned):
        raise ValueError("Card UID must be 8-14 hex characters (4 or 7 byte UID).")
    return cleaned


def is_valid_card_uid(uid: str) -> bool:
    try:
        normalize_card_uid(uid)
        return True
    except ValueError:
        return False
