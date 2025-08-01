# Use the specified builder base image and tag
ARG BUILDER_IMAGE=icr.io/ibm-dreadnought-prod-images/ubi9/python312-builder
ARG DREADNOUGHT_PYTHON312_TAG=SET_VALID_TAG

FROM ${BUILDER_IMAGE}:${DREADNOUGHT_PYTHON312_TAG}

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

USER root

WORKDIR /app

RUN mkdir -p /app && chmod -R 0777 /app
RUN mkdir -p /tmp/.cache/uv && chmod -R 0777 /tmp/.cache

COPY pyproject.toml uv.lock ./

RUN uv sync --locked --no-install-project --no-dev

COPY . /app

RUN chmod -R 0777 /app

# Set correct env variables
ENV PATH="/app/.venv/bin:$PATH"
ENV UV_CACHE_DIR=/tmp/.cache/uv
ENV XDG_CACHE_HOME=/tmp/.cache        
ENV SERVER_CONFIG_FILE_PATH=/app/example/mcsp_trio_server/mcsp_trio_master.json


CMD ["uv", "run", "test/test_composer.py"]
