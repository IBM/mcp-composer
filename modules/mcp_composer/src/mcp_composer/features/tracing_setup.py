# tracing_setup.py
from __future__ import annotations
from .config import (
    TRACING_ENABLED,
    TRACING_PROTOCOL,
    TRACING_ENDPOINT,
    SERVICE_NAME,
    ENVIRONMENT,
)
import os
from typing import Optional


def init_tracing_if_enabled():
    """_summary_

    Returns:
        _type_: _description_
    """
    if not TRACING_ENABLED:
        return False
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        if TRACING_PROTOCOL == "grpc":
            # gRPC expects host:port (no /v1/traces)
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )

            exporter = OTLPSpanExporter(endpoint=TRACING_ENDPOINT)
        else:
            # HTTP must include /v1/traces when you pass endpoint here
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter,
            )

            http_endpoint = TRACING_ENDPOINT.rstrip("/")
            if not http_endpoint.endswith("/v1/traces"):
                http_endpoint = f"{http_endpoint}/v1/traces"
            exporter = OTLPSpanExporter(endpoint=http_endpoint)

        res = Resource.create({"service.name": SERVICE_NAME})
        # merge extra resource attrs from ENVIRONMENT (comma-separated k=v)
        for kv in ENVIRONMENT.split(","):
            if "=" in kv:
                k, v = kv.split("=", 1)
                res = res.merge(Resource.create({k.strip(): v.strip()}))

        provider = TracerProvider(resource=res)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        return True
    except Exception as e:
        print(f"[tracing] disabled (reason: {e})")
        return False


def init_metrics_if_enabled() -> Optional["Meter"]:
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
        from opentelemetry import metrics
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
            OTLPMetricExporter,
        )
        from opentelemetry.sdk.resources import Resource

        # Endpoint: use OTEL_EXPORTER_OTLP_METRICS_ENDPOINT if set; otherwise OTEL_EXPORTER_OTLP_ENDPOINT; fallback :4318
        endpoint = os.getenv("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT") or os.getenv(
            "OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318"
        )
        # Exporter expects full path for HTTP:
        if endpoint.endswith("/"):
            endpoint = endpoint[:-1]
        if not endpoint.endswith("/v1/metrics"):
            endpoint = f"{endpoint}/v1/metrics"

        resource = Resource.create(
            {
                "service.name": os.getenv("OTEL_SERVICE_NAME", "mcp-composer"),
                "deployment.environment": os.getenv("MCP_ENV", "dev"),
            }
        )

        reader = PeriodicExportingMetricReader(
            OTLPMetricExporter(endpoint=endpoint),
            export_interval_millis=int(
                os.getenv("OTEL_METRIC_EXPORT_INTERVAL", "60000")
            ),  # 60s
        )

        provider = MeterProvider(resource=resource, metric_readers=[reader])
        metrics.set_meter_provider(provider)
        meter = metrics.get_meter("mcp-composer.metrics")
        return meter

    except Exception as e:
        print(f"[metrics] disabled (reason: {e})")
        return None
