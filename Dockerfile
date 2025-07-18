ARG BUILDER_IMAGE=icr.io/ibm-dreadnought-prod-images/ubi9/python312-builder
ARG RUNTIME_IMAGE=icr.io/ibm-dreadnought-prod-images/ubi9/python312-runtime
ARG DREADNOUGHT_PYTHON312_TAG=SET_VALID_TAG

FROM ${BUILDER_IMAGE}:${DREADNOUGHT_PYTHON312_TAG} AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/


WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN uv sync --locked --no-install-project --no-dev

COPY . /app
RUN uv sync --locked --no-dev

# RUNTIME STAGE
FROM ${RUNTIME_IMAGE}:${DREADNOUGHT_PYTHON312_TAG}

WORKDIR /app

COPY --from=builder /app /app

ENV PATH="/app/.venv/bin:$PATH"
ENV SERVER_CONFIG_FILE_PATH=/app/example/mcsp_trio_server/mcsp_trio_master.json

ENTRYPOINT []
CMD ["uv", "run", "test/test_composer.py"]

