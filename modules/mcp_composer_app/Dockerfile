ARG BUILDER_IMAGE=icr.io/ibm-dreadnought-prod-images/ubi9/python312-builder
ARG DREADNOUGHT_PYTHON312_TAG=SET_VALID_TAG

FROM ${BUILDER_IMAGE}:${DREADNOUGHT_PYTHON312_TAG} AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

USER root

# Upgrade pip to fix security vulnerability (CVE-2025-*)
RUN pip install --upgrade pip>=25.2

WORKDIR /app

RUN mkdir -p /.cache/uv /app && chmod -R 0777 /.cache /app

COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project --no-dev

COPY . /app

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

RUN chmod -R 0777 /app

ENV PATH="/app/.venv/bin:$PATH"
ENV UV_CACHE_DIR=/.cache/uv
ENV SERVER_CONFIG_FILE_PATH=/app/example/mcsp_trio_server/mcsp_trio_master.json

CMD ["uvicorn", "src.mcp_composer_app.app:app", "--host", "0.0.0.0", "--port", "8000"]