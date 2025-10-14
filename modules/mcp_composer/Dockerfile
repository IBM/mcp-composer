ARG BUILDER_IMAGE=icr.io/ibm-dreadnought-prod-images/ubi9/python312-builder
ARG DREADNOUGHT_PYTHON312_TAG=SET_VALID_TAG

FROM ${BUILDER_IMAGE}:${DREADNOUGHT_PYTHON312_TAG} AS builder

ENV ENABLE_PACKAGE_MANAGER=true
USER root

RUN dnf install -y \
    gcc-c++ \
    python3.12 \
    python3.12-devel \
    python3-devel \
    postgresql-devel && \
    dnf clean all && rm -rf /var/cache/dnf /tmp/*

# Copy UV binaries
ENV CXXFLAGS="-std=c++11"

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
COPY pyproject.toml uv.lock ./

RUN mkdir -p /.cache/uv && chmod -R 0777 /.cache/uv

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project --no-dev

COPY . /app
RUN chmod -R 0777 /app

# ---------- STAGE 2: Runtime ----------
FROM registry.access.redhat.com/ubi9-minimal:latest

# Copy only what’s needed
COPY --from=builder /app /app
COPY --from=builder /bin/uv /bin/uv
COPY --from=builder /bin/uvx /bin/uvx

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH=/app/src
ENV UV_CACHE_DIR=/.cache/uv

WORKDIR /app

CMD ["uv", "run", "--no-project", "composers/solis_composer.py"]
    