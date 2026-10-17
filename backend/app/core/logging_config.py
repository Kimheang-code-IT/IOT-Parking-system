import logging

from app.core.config import get_settings


def setup_logging(level_name: str | None = None) -> None:
    settings = get_settings()
    level = getattr(logging, (level_name or settings.log_level).upper(), logging.DEBUG)
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[logging.StreamHandler()],
        force=True,
    )
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    # Third-party debug streams stay out of container logs unless asked.
    for noisy in ("PIL", "PIL.PngImagePlugin", "httpcore", "httpx"):
        logging.getLogger(noisy).setLevel(logging.WARNING if level > logging.DEBUG else logging.DEBUG)
