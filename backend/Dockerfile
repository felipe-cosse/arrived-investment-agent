# Backend image (spec §11): multi-stage — uv dependency build → slim non-root runtime.
# Base images pinned by major tag (R24); the committed uv.lock pins dependencies.

# --- Stage 1: resolve locked dependencies into a standalone virtualenv --------
FROM python:3.12-slim AS builder

RUN pip install --no-cache-dir uv

ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /build
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# --- Stage 2: slim runtime, non-root -------------------------------------------
FROM python:3.12-slim

RUN useradd --create-home --user-group app

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY src ./src
# DB_PATH default data/arrived.duckdb resolves here; compose mounts a volume over it.
RUN mkdir -p /app/data && chown -R app:app /app/data

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1

USER app
EXPOSE 8000

# Compose gates `web` on this (§11). Stdlib urllib: slim ships no curl/wget,
# and urlopen raises (non-zero exit) on any non-2xx response.
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=2)"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
