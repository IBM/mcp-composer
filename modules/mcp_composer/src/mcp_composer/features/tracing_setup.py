# tracing_setup.py
from __future__ import annotations

import importlib
import os
from typing import Any, Optional

from .config import (
    ENVIRONMENT,
    SERVICE_NAME,
    TRACING_ENABLED,
    TRACING_ENDPOINT,
    TRACING_PROTOCOL,
)


def _require_module(module_path: str):
    """Import an optional module, raising ImportError if unavailable."""
    return importlib.import_module(module_path)


def init_tracing_if_enabled() -> bool:
    """Initialize tracing if enabled and opentelemetry is installed."""
    if not TRACING_ENABLED:
        return False
    try:
        trace = _require_module("opentelemetry.trace")
        resources = _require_module("opentelemetry.sdk.resources")
        trace_sdk = _require_module("opentelemetry.sdk.trace")
        exporters = _require_module("opentelemetry.sdk.trace.export")

        if TRACING_PROTOCOL == "grpc":
            exporter_module = _require_module(
                "opentelemetry.exporter.otlp.proto.grpc.trace_exporter"
            )

            exporter = exporter_module.OTLPSpanExporter(endpoint=TRACING_ENDPOINT)
        else:
            exporter_module = _require_module(
                "opentelemetry.exporter.otlp.proto.http.trace_exporter"
            )

            http_endpoint = TRACING_ENDPOINT.rstrip("/")
            if not http_endpoint.endswith("/v1/traces"):
                http_endpoint = f"{http_endpoint}/v1/traces"
            exporter = exporter_module.OTLPSpanExporter(endpoint=http_endpoint)

        res = resources.Resource.create({"service.name": SERVICE_NAME})
        # merge extra resource attrs from ENVIRONMENT (comma-separated k=v)
        for kv in ENVIRONMENT.split(","):
            if "=" in kv:
                k, v = kv.split("=", 1)
                res = res.merge(resources.Resource.create({k.strip(): v.strip()}))

        provider = trace_sdk.TracerProvider(resource=res)
        provider.add_span_processor(exporters.BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        return True
    except (ImportError, ValueError, OSError) as err:
        print(f"[tracing] disabled (reason: {err})")
        return False


def init_metrics_if_enabled() -> Optional[Any]:
    """
    Returns a meter if metrics are enabled and SDK is available, else None.
    Uses OTLP/HTTP exporter by default.
    """
    if os.getenv("MCP_METRICS_ENABLED", "false").lower() not in (
        "1",
        "true",
        "yes",
        "on",
    ):
        return None

    try:
        metrics = _require_module("opentelemetry.metrics")
        meter_sdk = _require_module("opentelemetry.sdk.metrics")
        meter_export = _require_module("opentelemetry.sdk.metrics.export")
        metric_exporter = _require_module(
            "opentelemetry.exporter.otlp.proto.http.metric_exporter"
        )
        resources = _require_module("opentelemetry.sdk.resources")

        # Endpoint preference: METRICS endpoint > generic endpoint > localhost:4318
        endpoint = (
            os.getenv("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT")
            or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
            or "http://localhost:4318"
        )
        # Exporter expects full path for HTTP
        if endpoint.endswith("/"):
            endpoint = endpoint[:-1]
        if not endpoint.endswith("/v1/metrics"):
            endpoint = f"{endpoint}/v1/metrics"

        resource = resources.Resource.create(
            {
                "service.name": os.getenv("OTEL_SERVICE_NAME", "mcp-composer"),
                "deployment.environment": os.getenv("MCP_ENV", "dev"),
            }
        )

        reader = meter_export.PeriodicExportingMetricReader(
            metric_exporter.OTLPMetricExporter(endpoint=endpoint),
            export_interval_millis=int(
                os.getenv("OTEL_METRIC_EXPORT_INTERVAL", "60000")
            ),
        )

        provider = meter_sdk.MeterProvider(resource=resource, metric_readers=[reader])
        metrics.set_meter_provider(provider)
        meter = metrics.get_meter("mcp-composer.metrics")
        return meter

    except (ImportError, ValueError, OSError) as err:
        print(f"[metrics] disabled (reason: {err})")
        return None
