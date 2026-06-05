"""Configure pytesseract to use Tesseract from PATH or GATE_TESSERACT_CMD."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from app.core.config import get_settings

logger = logging.getLogger(__name__)
_configured = False

_WINDOWS_DEFAULTS = (
    Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
    Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
)


def resolve_tesseract_cmd() -> str | None:
    settings = get_settings()
    if settings.gate_tesseract_cmd.strip():
        path = Path(settings.gate_tesseract_cmd.strip())
        if path.is_file():
            return str(path)
        logger.warning("GATE_TESSERACT_CMD not found: %s", path)

    found = shutil.which("tesseract")
    if found:
        return found

    for candidate in _WINDOWS_DEFAULTS:
        if candidate.is_file():
            return str(candidate)

    return None


def configure_tesseract() -> bool:
    global _configured
    if _configured:
        return True

    cmd = resolve_tesseract_cmd()
    if not cmd:
        logger.warning(
            "Tesseract not found. Install from ocr/tesseract-ocr-w64-setup-*.exe "
            "and set GATE_TESSERACT_CMD in backend/.env"
        )
        return False

    try:
        import pytesseract

        pytesseract.pytesseract.tesseract_cmd = cmd
        _configured = True
        logger.info("Tesseract OCR: %s", cmd)
        return True
    except ImportError:
        logger.warning("pytesseract not installed — pip install pytesseract")
        return False


def tesseract_available() -> bool:
    return configure_tesseract()
