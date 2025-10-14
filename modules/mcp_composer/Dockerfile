ARG BUILDER_IMAGE=icr.io/ibm-dreadnought-prod-images/ubi9/python312-builder
ARG DREADNOUGHT_PYTHON312_TAG=SET_VALID_TAG

FROM ${BUILDER_IMAGE}:${DREADNOUGHT_PYTHON312_TAG}

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

RUN g++ --version

RUN find / -name Python.h || true

ENV CXXFLAGS="-std=c++11"

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN python3.12 -m pip install --no-cache-dir --upgrade "pip==25.2"

WORKDIR /app

RUN mkdir -p /app && chmod -R 0777 /app
RUN mkdir -p /.cache/uv && chmod -R 0777 /.cache/uv

COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project --no-dev

COPY . /app

RUN chmod -R 0777 /app

ENV PATH="/app/.venv/bin:$PATH"
ENV UV_CACHE_DIR=/.cache/uv
ENV PYTHONPATH=/app/src

RUN ld.gold --version && gdbserver --version

CMD ["uv", "run", "--no-project", "composers/solis_composer.py"]
