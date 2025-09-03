# MCP Composer REST API

This FastMCP application dynamically exposes all registered MCP Composer tools as REST API endpoints.

## ✨ Features

- Dynamically loads and registers tools at startup
- Automatically generates request schemas based on each tool's parameters
- Clean Swagger UI with tool-specific input fields
- Compatible with Pydantic v2+

---

## 📂 Project Structure

```
mcp_composer_app/
├── app.py                  # FastAPI app exposing tools as REST endpoints
├── __init__.py
├── pyproject.toml          # Project metadata and dependencies
├── uv.lock                 # Lockfile for uv sync
```

---

## ⚖️ Usage

### 1. Install dependencies

```bash
uv sync --locked --no-dev
```

> Requires `uv`: https\://github.com/astral-sh/uv

### 2. Run the app

```bash
uvicorn mcp_composer_app.app:app --reload
```

### 3. Access API Docs

- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- Redoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## ⚡ Endpoint Overview

### List Tools

```http
GET /tools
```

Returns a list of tool names.

### Execute Tool

```http
POST /tools/<tool_name>
```

Request body will dynamically match each tool's parameter schema. Example:

```json
{
  "server_id": "abc123",
  "new_config": {
    "url": "http://example.com"
  }
}
```

#### Example cURL Command

```bash
curl -X POST http://localhost:8000/tools/register_mcp_server \
  -H "Content-Type: application/json" \
  -d '{
        "config": {
            "id": "server1",
            "url": "http://localhost:9000",
            "type": "rest"
        }
      }'
```

---

## 🌐 Docker (Optional)

To run via Docker:

```dockerfile
# Use official Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy application code
COPY . /app

# Copy from the cache instead of linking since it's a mounted volume
ENV UV_LINK_MODE=copy

# Install the project's dependencies using the lockfile and settings
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev

COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

# Place executables in the environment at the front of the path
ENV PATH="/app/.venv/bin:$PATH"
ENTRYPOINT []

# Start the FastAPI app using uvicorn
CMD ["uvicorn", "mcp_composer_app.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

> Make sure to install `uv` inside the container or include it in your Docker base image.

---

## 🚀 Deployment Notes

- Ensure tools are properly defined and loadable via `MCPComposer()`.
- This app uses `lifespan()` for dynamic route registration.
- Ideal for container-based deployment (e.g., IBM Code Engine).
- You can mount secrets, configs, or tokens via environment variables as needed.

---
