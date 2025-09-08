# Alternative Dockerfile that handles IBM DB2 dependency differently
# Use Python 3.13 slim image as base
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

ENV ENABLE_PACKAGE_MANAGER=true

USER root

RUN apt-get update && apt-get install -y \
    g++ \
    python3-dev \
    build-essential \
    && g++ --version

RUN apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/*

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
ENV PYTHONPATH=/app/src

CMD ["uv", "run", "--no-project", "composers/solis_composer.py"]
