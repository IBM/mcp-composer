ARG BUILDER_IMAGE=icr.io/ibm-dreadnought-prod-images/ubi9/python312-builder
ARG RUNTIME_IMAGE=icr.io/ibm-dreadnought-prod-images/ubi9/python312-runtime
ARG DREADNOUGHT_PYTHON312_TAG=v9.6.84

#########################################
# -------- Stage 1: Builder --------
#########################################
FROM ${BUILDER_IMAGE}:${DREADNOUGHT_PYTHON312_TAG} AS builder

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Must be set BEFORE using dnf
ENV ENABLE_PACKAGE_MANAGER=true

USER root

RUN dnf -y update-minimal --security && \
    dnf install -y \
        gcc-c++ \
        python3.12 \
        python3.12-devel \
        python3-devel \
        postgresql-devel \
        binutils-gold \
        gdb-gdbserver && \
    dnf clean all && rm -rf /var/cache/dnf /tmp/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN python3.12 -m pip install --no-cache-dir --upgrade "pip==25.2"

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN uv sync --locked --no-install-project --no-dev

COPY . /app


#########################################
# -------- Stage 2: Runtime --------
#########################################
FROM ${RUNTIME_IMAGE}:${DREADNOUGHT_PYTHON312_TAG} AS final

# OpenShift hardened images → no RUN allowed and no fixed user.
USER 1001

WORKDIR /app

COPY --from=builder /app /app
COPY --from=builder /bin/uv /bin/uv
COPY --from=builder /bin/uvx /bin/uvx

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH=/app/src
ENV UV_CACHE_DIR="/.cache/uv"

CMD ["uv", "run", "--no-project", "composers/solis_composer.py"]
