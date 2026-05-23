from fastapi import Header, HTTPException, status

from app.core.config import get_settings


def verify_payment_webhook(x_webhook_secret: str = Header(..., alias="x-webhook-secret")) -> None:
    settings = get_settings()
    if x_webhook_secret != settings.payment_webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"success": False, "message": "Invalid webhook secret."},
        )
