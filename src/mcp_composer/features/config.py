import os
import tomllib
from pathlib import Path


def _from_pyproject():
    try:
        data = tomllib.loads(Path("pyproject.toml").read_text())
        return data.get("tool", {}).get("mcp_composer", {})
    except Exception:
        return {}


_cfg = _from_pyproject()

TRACING_ENABLED = os.getenv(
    "MCP_TRACING_ENABLED", str(_cfg.get("tracing_enabled", "false"))
).lower() in ("1", "true", "yes", "on")
TRACING_PROTOCOL = os.getenv(
    "MCP_TRACING_PROTOCOL", _cfg.get("tracing_protocol", "http")
)
TRACING_ENDPOINT = os.getenv(
    "OTEL_EXPORTER_OTLP_ENDPOINT", _cfg.get("tracing_endpoint", "http://localhost:4318")
)
SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", _cfg.get("service_name", "mcp-composer"))
ENVIRONMENT = os.getenv(
    "OTEL_RESOURCE_ATTRIBUTES",
    f"deployment.environment={_cfg.get('environment','dev')}",
)
