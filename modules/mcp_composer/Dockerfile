# Generic multi-stage image for MCP Composer (open source).
# Build from modules/mcp_composer:
#   docker build -t mcp-composer:local .

ARG PYTHON_IMAGE=python:3.12-slim-bookworm

#########################################
# -------- Stage 1: Builder --------
#########################################
FROM ${PYTHON_IMAGE} AS builder

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
COPY . .

ENV UV_LINK_MODE=copy
ENV UV_COMPILE_BYTECODE=1

RUN uv sync --locked --no-install-project --no-dev

#########################################
# -------- Stage 2: Runtime --------
#########################################
FROM ${PYTHON_IMAGE} AS final

RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1001 --shell /usr/sbin/nologin appuser

WORKDIR /app

COPY --from=builder /app /app
COPY --from=builder /bin/uv /bin/uv
COPY --from=builder /bin/uvx /bin/uvx

ENV PYTHONPATH=/app/src
ENV UV_CACHE_DIR=/tmp/.cache/uv
ENV UV_NO_SYNC=1
ENV MCP_MODE=http

USER 1001

EXPOSE 9000

# Bind loopback by default; override host / add --auth-type oauth for non-loopback.
CMD ["uv", "run", "--no-project", "mcp-composer", "run", "--mode", "http", "--host", "127.0.0.1", "--port", "9000"]
