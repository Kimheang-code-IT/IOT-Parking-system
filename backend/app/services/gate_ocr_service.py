"""OCR stub — replace with OpenCV / cloud LPR in production."""


class GateOcrService:
    @staticmethod
    def recognize_plate(
        *,
        image_base64: str | None = None,
        hint: str | None = None,
    ) -> str:
        if hint and hint.strip():
            return hint.strip().upper()
        if image_base64:
            return "OCR-PLATE-001"
        raise ValueError("Provide licensePlate or imageBase64 for OCR.")
