ARG BUILDER_IMAGE=icr.io/ibm-dreadnought-prod-images/ubi9/python312-builder
ARG DREADNOUGHT_PYTHON312_TAG=v9.6.27

FROM ${BUILDER_IMAGE}:${DREADNOUGHT_PYTHON312_TAG}

ENV ENABLE_PACKAGE_MANAGER=true

USER root

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

RUN mkdir -p /app && chmod -R 0777 /app
RUN mkdir -p /tmp/.cache/uv && chmod -R 0777 /tmp/.cache

COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project --no-dev

COPY . /app

RUN chmod -R 0777 /app

ENV PATH="/app/.venv/bin:$PATH"
ENV UV_CACHE_DIR=/.cache/uv

CMD ["uv", "run", "composers/solis_composer.py"]
