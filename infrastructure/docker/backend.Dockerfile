# syntax=docker/dockerfile:1
# Smart IoT Parking — FastAPI backend (production image)
#
# Build context: ../backend  (docker build -f infrastructure/docker/backend.Dockerfile backend)

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_RETRIES=10 \
    PIP_DEFAULT_TIMEOUT=120

WORKDIR /app

# Non-root runtime user
RUN groupadd --system app \
    && useradd --system --gid app --create-home app

# Dependencies first: this layer is cached until requirements.txt changes.
# Retries/timeouts above keep slow-network builds from failing hard.
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt

# Application source (see backend/.dockerignore for exclusions)
COPY . .

# Persistent receipt storage (mounted as a named volume in compose).
# Created here so the volume inherits the app user's ownership on first use.
RUN mkdir -p /app/data/receipts \
    && chown -R app:app /app

USER app

EXPOSE 8000

# --proxy-headers + forwarded-allow-ips: rate limiting / logs get the real
# client IP from nginx instead of the proxy container address.
CMD ["sh", "-c", "exec uvicorn app.main:app \
  --host 0.0.0.0 --port 8000 \
  --proxy-headers --forwarded-allow-ips \"${FORWARDED_ALLOW_IPS:-*}\" \
  --workers \"${WEB_CONCURRENCY:-1}\" \
  --timeout-graceful-shutdown 20 \
  --no-server-header"]
