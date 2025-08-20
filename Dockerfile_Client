ARG BUILDER_IMAGE=icr.io/ibm-dreadnought-prod-images/ubi9/python312-builder
ARG NODE_BUILDER_IMAGE=icr.io/ibm-dreadnought-prod-images/ubi9/nodejs20-builder

ARG DREADNOUGHT_PYTHON312_TAG=SET_VALID_TAG
ARG NODE_BUILDER_TAG=v9.6.49

FROM ${NODE_BUILDER_IMAGE}:${NODE_BUILDER_TAG} AS node-deps

RUN npm install -g @ivotoby/openapi-mcp-server

FROM ${BUILDER_IMAGE}:${DREADNOUGHT_PYTHON312_TAG} AS builder

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
# Update package lists and install GCC 13 which is required by hnswlib
# RUN echo "deb http://deb.debian.org/debian testing main" >> /etc/apt/sources.list && \
#     apt-get update && \
#     apt-get install -y gcc-13 g++-13 build-essential && \
#     apt-get clean && \
#     rm -rf /var/lib/apt/lists/*

# # Set GCC 13 as the default compiler
# RUN update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-13 100 \
#     && update-alternatives --install /usr/bin/g++ g++ /usr/bin/g++-13 100

# Install the project into `/app`

WORKDIR /app

RUN mkdir -p /.cache/uv /app && chmod -R 0777 /.cache /app

COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project --no-dev

COPY . /app

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev


## ----- Download emedding model -----
# Install required packages
# RUN pip install huggingface_hub

# Set model name (change this to your desired model)
# ARG MODEL_NAME=BAAI/bge-small-en-v1.5
# ARG MODEL_NAME=sentence-transformers/all-mpnet-base-v2

# Download model
# RUN python -c "from huggingface_hub import snapshot_download; snapshot_download('${MODEL_NAME}', local_dir='/app/models')"
## ----- Download emedding model -----
    
# Place executables in the environment at the front of the path
RUN chmod -R 0777 /app

ENV PATH="/app/.venv/bin:$PATH"

CMD ["uv", "run", "src/mcp_composer_client/acp_server.py"]
