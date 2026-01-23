ARG BUILDER_IMAGE=icr.io/ibm-dreadnought-prod-images/ubi9/python312-builder
ARG RUNTIME_IMAGE=icr.io/ibm-dreadnought-prod-images/ubi9/python312-runtime
ARG DREADNOUGHT_PYTHON312_TAG=SET_VALID_TAG

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

RUN dnf --refresh update -y \
    && dnf install -y libgcc \
    && dnf clean all

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN dnf install -y sqlite sqlite-devel && \
    dnf clean all

WORKDIR /app

COPY . .

ENV UV_PYTHON=/usr/bin/python3.12

RUN uv sync --locked --no-install-project --no-dev


#########################################
# -------- Stage 2: Runtime --------
#########################################
FROM ${RUNTIME_IMAGE}:${DREADNOUGHT_PYTHON312_TAG} AS final

ENV UV_NO_SYNC=1

USER root

WORKDIR /app

COPY --from=builder /app /app
COPY --from=builder /bin/uv /bin/uv
COPY --from=builder /bin/uvx /bin/uvx

COPY --from=builder /etc/pki /etc/pki
COPY --from=builder /etc/ssl /etc/ssl
COPY --from=builder /etc/nsswitch.conf /etc/nsswitch.conf
COPY --from=builder /etc/passwd /etc/passwd
COPY --from=builder /etc/group /etc/group

COPY --from=builder /usr/lib64/libnss_* /usr/lib64/
COPY --from=builder /usr/lib64/libssl.so.* /usr/lib64/
COPY --from=builder /usr/lib64/libcrypto.so.* /usr/lib64/

COPY --from=builder /usr/lib64/libgcc_s.so.* /usr/lib64/
COPY --from=builder /usr/lib64/libstdc++.so.* /usr/lib64/
COPY --from=builder /usr/lib64/librt.so.* /usr/lib64/
COPY --from=builder /usr/lib64/libsqlite3.so.* /usr/lib64/
COPY --from=builder /usr/bin/sqlite3 /usr/bin/sqlite3

ENV PYTHONPATH=/app/src
ENV UV_CACHE_DIR="/tmp/.cache/uv"

CMD ["uv", "run", "--no-project", "composers/solis_composer.py"]
