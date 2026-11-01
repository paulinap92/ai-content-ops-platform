# syntax=docker/dockerfile:1
FROM python:3.13-slim AS deps
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

RUN apt-get update && apt-get install -y --no-install-recommends curl build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.13.4 /uv /uvx /bin/
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

FROM python:3.13-slim AS runtime
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=deps /app/.venv /app/.venv
COPY . .
RUN groupadd --gid 10001 editor && useradd --uid 10001 --gid editor --no-create-home editor \
    && mkdir -p /app/output /app/photo_inbox \
    && chown -R editor:editor /app/output /app/photo_inbox

USER 10001:10001

EXPOSE 8000
CMD ["python", "-m", "src.core.run"]

