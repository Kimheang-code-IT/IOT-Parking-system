"""PC webcam capture — OpenCV plate OCR with auto-close preview on success."""

from __future__ import annotations

import logging
import re
import time

from app.core.config import get_settings
from app.utils.tesseract_setup import configure_tesseract, tesseract_available

logger = logging.getLogger(__name__)

# Cambodia-style plates: 2A-1234, ABC-1234, 12AB3456, etc.
_PLATE_PATTERNS = [
    re.compile(r"\b[A-Z]{1,3}[-\s]?\d{1,4}[A-Z]{0,2}\b", re.IGNORECASE),
    re.compile(r"\b[A-Z]{2,3}\d{3,6}\b", re.IGNORECASE),
    re.compile(r"\b\d{1,2}[A-Z]{1,3}[-\s]?\d{3,5}\b", re.IGNORECASE),
]


class GateCameraService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def scan_entry_plate(self, *, use_camera: bool, mock_plate: str | None = None) -> str:
        if mock_plate and mock_plate.strip():
            return self._normalize_plate(mock_plate)
        if use_camera and self.settings.gate_use_camera:
            plate = self._capture_plate_opencv(mode="entry")
            if plate:
                return plate
        if self.settings.gate_camera_fallback_plate:
            return self._normalize_plate(self.settings.gate_camera_fallback_plate)
        raise ValueError("Could not read license plate from camera. Point plate at webcam or press SPACE.")

    def scan_exit_barcode(self, *, use_camera: bool) -> str | None:
        if use_camera and self.settings.gate_use_camera:
            return self._capture_exit_barcode_opencv()
        return None

    def _capture_plate_opencv(self, *, mode: str = "entry") -> str | None:
        try:
            import cv2  # type: ignore
        except ImportError:
            logger.warning("opencv-python not installed — pip install opencv-python")
            return None

        cap = cv2.VideoCapture(self.settings.gate_camera_index)
        if not cap.isOpened():
            logger.warning("Camera %s not available", self.settings.gate_camera_index)
            return None

        window = "IOT Parking ENTRY — prepare, then scan plate (SPACE / ESC)"
        prepare_sec = max(0, self.settings.gate_camera_prepare_seconds)
        scan_sec = max(5, self.settings.gate_camera_scan_seconds)
        prepare_end = time.time() + prepare_sec
        scan_end = prepare_end + scan_sec
        last_ocr_at = 0.0
        preview = self.settings.gate_show_camera_preview
        last_debug = ""

        try:
            while time.time() < scan_end:
                ok, frame = cap.read()
                if not ok or frame is None:
                    continue

                preparing = time.time() < prepare_end
                display = frame.copy()
                if preview:
                    cv2.rectangle(display, (8, 8), (display.shape[1] - 8, 70), (0, 0, 0), -1)
                    if preparing:
                        countdown = int(prepare_end - time.time()) + 1
                        status = f"Prepare scan... {countdown}s  (ESC=cancel)"
                    else:
                        status = "Scanning... SPACE=force  ESC=cancel"
                    cv2.putText(
                        display,
                        status,
                        (16, 32),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.55,
                        (0, 255, 0),
                        1,
                        cv2.LINE_AA,
                    )
                    if not preparing and last_debug:
                        cv2.putText(
                            display,
                            "OCR: " + last_debug[:40],
                            (16, 58),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.5,
                            (200, 200, 200),
                            1,
                            cv2.LINE_AA,
                        )

                key = 255
                if preview:
                    cv2.imshow(window, display)
                    key = cv2.waitKey(1) & 0xFF
                    if key == 27:
                        return None

                if preparing:
                    continue

                if key == 32:
                    plate = self._plate_from_frame(frame)
                    if plate:
                        self._flash_success(cv2, window, frame, plate, preview)
                        return plate

                now = time.time()
                if now - last_ocr_at >= 0.6:
                    last_ocr_at = now
                    text = self._ocr_text_multi(frame)
                    last_debug = text.replace("\n", " ")[:60]
                    plate = self._find_plate_in_text(text)
                    if plate:
                        logger.info("Plate OCR entry success: %s", plate)
                        self._flash_success(cv2, window, frame, plate, preview)
                        return plate

            return None
        finally:
            cap.release()
            if preview:
                try:
                    import cv2  # type: ignore

                    self._close_preview(cv2)
                except ImportError:
                    pass

    @staticmethod
    def _flash_success(cv2, window: str, frame, plate: str, preview: bool) -> None:
        if not preview:
            return
        display = frame.copy()
        cv2.rectangle(display, (0, 0), (display.shape[1], display.shape[0]), (0, 180, 0), 8)
        cv2.putText(
            display,
            "OK " + plate,
            (20, 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.2,
            (0, 255, 0),
            2,
            cv2.LINE_AA,
        )
        cv2.imshow(window, display)
        cv2.waitKey(700)
        GateCameraService._close_preview(cv2)

    @staticmethod
    def _close_preview(cv2) -> None:
        if cv2 is None:
            return
        try:
            cv2.destroyAllWindows()
            cv2.waitKey(1)
        except Exception:
            pass

    def _capture_exit_barcode_opencv(self) -> str | None:
        try:
            import cv2  # type: ignore
        except ImportError:
            logger.warning("opencv-python not installed — pip install opencv-python")
            return None

        cap = cv2.VideoCapture(self.settings.gate_camera_index)
        if not cap.isOpened():
            logger.warning("Camera %s not available", self.settings.gate_camera_index)
            return None

        window = "IOT Parking EXIT — scan ticket barcode (SPACE / ESC)"
        prepare_sec = max(0, self.settings.gate_camera_prepare_seconds)
        scan_sec = max(5, self.settings.gate_camera_scan_seconds)
        prepare_end = time.time() + prepare_sec
        scan_end = prepare_end + scan_sec
        preview = self.settings.gate_show_camera_preview

        try:
            while time.time() < scan_end:
                ok, frame = cap.read()
                if not ok or frame is None:
                    continue

                preparing = time.time() < prepare_end
                display = frame.copy()
                if preview:
                    cv2.rectangle(display, (8, 8), (display.shape[1] - 8, 70), (0, 0, 0), -1)
                    if preparing:
                        countdown = int(prepare_end - time.time()) + 1
                        status = f"Prepare scan... {countdown}s  (ESC=cancel)"
                    else:
                        status = "Scan ticket barcode... SPACE=retry  ESC=cancel"
                    cv2.putText(
                        display,
                        status,
                        (16, 32),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.55,
                        (0, 255, 0),
                        1,
                        cv2.LINE_AA,
                    )
                    cv2.imshow(window, display)
                    key = cv2.waitKey(1) & 0xFF
                    if key == 27:
                        return None
                    if preparing:
                        continue
                    if key == 32:
                        payload = self._scan_barcodes(frame)
                        if payload:
                            self._flash_barcode_ok(cv2, window, frame, preview)
                            return payload
                elif not preparing:
                    payload = self._scan_barcodes(frame)
                    if payload:
                        return payload
                    continue

                payload = self._scan_barcodes(frame)
                if payload:
                    logger.info("Exit barcode scanned: %s", payload[:48])
                    self._flash_barcode_ok(cv2, window, frame, preview)
                    return payload

            return None
        finally:
            cap.release()
            if preview:
                try:
                    import cv2  # type: ignore

                    self._close_preview(cv2)
                except ImportError:
                    pass

    @staticmethod
    def _flash_barcode_ok(cv2, window: str, frame, preview: bool) -> None:
        if not preview:
            return
        display = frame.copy()
        cv2.rectangle(display, (0, 0), (display.shape[1], display.shape[0]), (0, 180, 0), 8)
        cv2.putText(
            display,
            "Barcode OK",
            (20, 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.2,
            (0, 255, 0),
            2,
            cv2.LINE_AA,
        )
        cv2.imshow(window, display)
        cv2.waitKey(700)
        GateCameraService._close_preview(cv2)

    def _read_single_frame(self):
        try:
            import cv2  # type: ignore
        except ImportError:
            return None

        cap = cv2.VideoCapture(self.settings.gate_camera_index)
        if not cap.isOpened():
            return None
        try:
            for _ in range(8):
                cap.read()
            ok, frame = cap.read()
            return frame if ok else None
        finally:
            cap.release()

    def _preprocess_variants(self, frame):
        import cv2  # type: ignore

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        blur = cv2.GaussianBlur(enhanced, (3, 3), 0)
        thresh = cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
        return [gray, enhanced, thresh]

    def _ocr_text_multi(self, frame) -> str:
        texts: list[str] = []
        for variant in self._preprocess_variants(frame):
            texts.append(self._ocr_on_image(variant))
        h, w = frame.shape[:2]
        if h > 80 and w > 80:
            center = frame[int(h * 0.25) : int(h * 0.85), int(w * 0.1) : int(w * 0.9)]
            for variant in self._preprocess_variants(center):
                texts.append(self._ocr_on_image(variant))
        return "\n".join(t for t in texts if t)

    def _ocr_on_image(self, image) -> str:
        if not tesseract_available():
            return ""
        try:
            import pytesseract  # type: ignore
        except ImportError:
            return ""
        configure_tesseract()
        configs = [
            "--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-",
            "--psm 6",
            "--psm 11",
        ]
        parts: list[str] = []
        for cfg in configs:
            try:
                parts.append(pytesseract.image_to_string(image, config=cfg) or "")
            except Exception as exc:
                logger.debug("Tesseract %s: %s", cfg, exc)
        return "\n".join(parts)

    def _plate_from_frame(self, frame) -> str | None:
        return self._find_plate_in_text(self._ocr_text_multi(frame))

    def _scan_barcodes(self, frame) -> str | None:
        try:
            from pyzbar.pyzbar import decode  # type: ignore
        except ImportError:
            return None
        for item in decode(frame):
            raw = item.data.decode("utf-8", errors="ignore").strip()
            if len(raw) >= 8:
                return raw
        return None

    def _find_plate_in_text(self, text: str) -> str | None:
        upper = text.upper()
        for pattern in _PLATE_PATTERNS:
            for match in pattern.finditer(upper):
                candidate = self._normalize_plate(match.group(0))
                if len(candidate) >= 4:
                    return candidate
        for token in re.split(r"[\s\n\r,;|]+", upper):
            cleaned = re.sub(r"[^A-Z0-9-]", "", token)
            if len(cleaned) >= 4:
                normalized = self._normalize_plate(cleaned)
                for pattern in _PLATE_PATTERNS:
                    if pattern.search(normalized):
                        return normalized
        return None

    @staticmethod
    def _normalize_plate(value: str) -> str:
        v = value.strip().upper().replace(" ", "-")
        while "--" in v:
            v = v.replace("--", "-")
        return v
