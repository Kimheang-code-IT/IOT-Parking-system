import re


def normalize_plate(plate: str) -> str:
    cleaned = re.sub(r"\s+", "", plate.strip().upper())
    return cleaned
