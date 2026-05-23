import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.bootstrap import bootstrap_database
from app.core.config import get_settings
from app.core.database import engine
from app.core.logging_config import setup_logging
from app.routers import dashboard, invoices, iot, parking, payment

logger = logging.getLogger(__name__)
settings = get_settings()
limiter = Limiter(key_func=get_remote_address, default_limits=[settings.rate_limit])


@asynccontextmanager
async def lifespan(_: FastAPI):
    setup_logging()
    bootstrap_database()
    logger.info("Started %s [development] db=%s", settings.app_name, settings.database_url)
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"success": False, "message": "Validation error.", "errors": exc.errors()},
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(_: Request, exc: StarletteHTTPException):
    detail = exc.detail
    content = detail if isinstance(detail, dict) else {"success": False, "message": str(detail)}
    return JSONResponse(status_code=exc.status_code, content=content)


@app.get("/health")
@limiter.limit(settings.rate_limit)
def health(request: Request):
    db_status = "ok"
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        logger.exception("Database health check failed")
        db_status = f"error: {exc}"
    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "service": settings.app_name,
        "environment": "development",
        "database": db_status,
    }


app.include_router(parking.router)
app.include_router(invoices.router)
app.include_router(payment.router)
app.include_router(dashboard.router)
app.include_router(iot.router)
