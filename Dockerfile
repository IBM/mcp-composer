# ARG BUILDER_IMAGE=icr.io/ibm-dreadnought-prod-images/ubi9/python312-builder
# ARG RUNTIME_IMAGE=icr.io/ibm-dreadnought-prod-images/ubi9/python312-runtime
# ARG DREADNOUGHT_PYTHON312_TAG=SET_VALID_TAG

# FROM ${BUILDER_IMAGE}:${DREADNOUGHT_PYTHON312_TAG} AS builder

# COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/


# WORKDIR /app

# COPY pyproject.toml uv.lock ./

# RUN uv sync --locked --no-install-project --no-dev

# COPY . /app
# RUN uv sync --locked --no-dev

# # RUNTIME STAGE
# FROM ${RUNTIME_IMAGE}:${DREADNOUGHT_PYTHON312_TAG}

# WORKDIR /app

# COPY --from=builder /app /app

# ENV PATH="/app/.venv/bin:$PATH"
# ENV SERVER_CONFIG_FILE_PATH=/app/example/mcsp_trio_server/mcsp_trio_master.json

# ENTRYPOINT []
# CMD ["uv", "run", "test/test_composer.py"]


ARG BUILDER_IMAGE=icr.io/ibm-dreadnought-prod-images/ubi9/python312-builder
ARG DREADNOUGHT_PYTHON312_TAG=SET_VALID_TAG

FROM ${BUILDER_IMAGE}:${DREADNOUGHT_PYTHON312_TAG}

ENV ENABLE_PACKAGE_MANAGER=true

RUN dnf install -y \
    gcc-c++ \
    python3.12 \
    python3.12-devel \
    python3-devel \
    && g++ --version

RUN dnf clean all && rm -rf /var/cache/dnf /tmp/*

RUN find / -name Python.h || true

ENV CXXFLAGS="-std=c++11"


COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project --no-dev

COPY . /app
# RUN --mount=type=cache,target=/root/.cache/uv \
#     uv venv && \
#     uv pip install --no-deps -e .

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

ENV PATH="/app/.venv/bin:$PATH"

ENV SERVER_CONFIG_FILE_PATH=/app/example/mcsp_trio_server/mcsp_trio_master.json

CMD ["uv", "run", "test/test_composer.py"]
