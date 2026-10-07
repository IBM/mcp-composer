
## Observability with Middleware and OpenTelemetry

This project supports OpenTelemetry-based tracing and metrics. Tracing and metrics are controlled via `pyproject.toml` defaults and can be overridden with environment variables.

### 1) Install tracing/metrics dependencies

If you plan to enable tracing/metrics, install the optional extras defined in `pyproject.toml`:

```bash
pip install -e ".[tracing]"
```

### 2) Configure via `pyproject.toml`

Defaults live under `[tool.mcp_composer]` and are read by `src/mcp_composer/features/config.py`.

```toml
[tool.mcp_composer]
tracing_enabled = false
tracing_protocol = "http"   # "http" | "grpc"
tracing_endpoint = "http://localhost:4318"
service_name = "mcp-composer"
environment = "dev"
```

You can override these with environment variables (see below).

### 3) Environment variables

Tracing (used by `init_tracing_if_enabled()` in `src/mcp_composer/features/tracing_setup.py`):
- `MCP_TRACING_ENABLED`: "true"/"false" to toggle tracing
- `MCP_TRACING_PROTOCOL`: `http` or `grpc`
- `OTEL_EXPORTER_OTLP_ENDPOINT`: collector endpoint (e.g., `http://localhost:4318`)
- `OTEL_SERVICE_NAME`: service name for traces/metrics
- `OTEL_RESOURCE_ATTRIBUTES`: comma-separated resource attrs, e.g. `deployment.environment=dev,team=platform`

Metrics (used by `init_metrics_if_enabled()` in `src/mcp_composer/features/tracing_setup.py`):
- `MCP_METRICS_ENABLED`: "true"/"false" to toggle metrics
- `OTEL_EXPORTER_OTLP_METRICS_ENDPOINT`: metrics endpoint; falls back to `OTEL_EXPORTER_OTLP_ENDPOINT`
- `OTEL_METRIC_EXPORT_INTERVAL`: export interval in ms (default 60000)
- `MCP_ENV`: used in resource attrs when exporting metrics

Note: When using HTTP exporters, the collector endpoints must include the correct paths:
- Traces: `.../v1/traces`
- Metrics: `.../v1/metrics`

`tracing_setup.py` automatically appends these paths when needed.

### 4) Initialize in your application

At process startup, enable tracing/metrics if configured, and register instruments:

```python
from mcp_composer.features.tracing_setup import init_tracing_if_enabled, init_metrics_if_enabled
from mcp_composer.features.opentelemetry_metrics_registry import init_instruments, tool_calls

# Enable tracing (no-op if disabled)
init_tracing_if_enabled()

# Enable metrics and register standard instruments
meter = init_metrics_if_enabled()
init_instruments(meter)

# Example usage of a metric (if enabled)
if tool_calls is not None:
    tool_calls.add(1, {"tool": "example", "status": "ok"})
```

### 5) Adding new metrics

Standard instruments are defined in `src/mcp_composer/features/opentelemetry_metrics_registry.py` (`tool_calls`, `tool_errors`, `tool_duration`, `in_bytes`, `out_bytes`). To add a new metric:
1. Define it inside `init_instruments(meter)` in `opentelemetry_metrics_registry.py`.
2. Use it in your code after `init_instruments(meter)` has been called at startup.

Example addition in the registry:

```python
custom_counter = meter.create_counter(
    name="mcp.custom.events",
    unit="1",
    description="Custom domain events",
)
```

Then record metrics where appropriate:

```python
from mcp_composer.features import opentelemetry_metrics_registry as metrics

if metrics.custom_counter is not None:
    metrics.custom_counter.add(1, {"event": "cache_miss"})
```

### 6) Run the OpenTelemetry Collector

Update the configuration in `config/otel-collector-config.yaml` if needed.

```bash
docker run --rm \
  -p 4318:4318 -p 4317:4317 \
  -v "$(pwd)/config/otel-collector-config.yaml":/etc/otelcol/config.yaml \
  otel/opentelemetry-collector:latest
```

Or:

```bash
podman run --rm --name otel-collector -p 4318:4318 -p 55681:55681 \
  -v "$(pwd)/config/otel-collector-config.yaml":/etc/otelcol/config.yaml:Z \
  otel/opentelemetry-collector:latest
```

### 7) Run Jaeger UI (Zipkin ingest enabled)

```bash
docker run -d --name jaeger \
  -e COLLECTOR_ZIPKIN_HOST_PORT=:9411 \
  -p 9411:9411 \
  -p 16686:16686 \
  jaegertracing/all-in-one:latest
```

Or:

```bash
podman run -d --name jaeger \
  -e COLLECTOR_ZIPKIN_HOST_PORT=:9411 \
  -p 9411:9411 \
  -p 16686:16686 \
  jaegertracing/all-in-one:latest
```

Open Jaeger UI at http://localhost:16686 and search for `service.name = mcp-composer` (or your configured `OTEL_SERVICE_NAME`).

