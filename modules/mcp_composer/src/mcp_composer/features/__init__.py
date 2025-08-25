"""
Features module for MCP Composer.

This module provides advanced features including:
- OpenTelemetry tracing setup and configuration
- Metrics collection and instrumentation
- Feature configuration management
"""

from .config import (
    TRACING_ENABLED,
    TRACING_PROTOCOL,
    TRACING_ENDPOINT,
    SERVICE_NAME,
    ENVIRONMENT,
)
from .tracing_setup import init_tracing_if_enabled, init_metrics_if_enabled
from .opentelemetry_metrics_registry import (
    init_instruments,
    tool_calls,
    tool_errors,
    tool_duration,
    in_bytes,
    out_bytes,
)

__all__ = [
    # Configuration constants
    "TRACING_ENABLED",
    "TRACING_PROTOCOL",
    "TRACING_ENDPOINT",
    "SERVICE_NAME",
    "ENVIRONMENT",
    
    # Tracing functions
    "init_tracing_if_enabled",
    "init_metrics_if_enabled",
    
    # Metrics functions and instruments
    "init_instruments",
    "tool_calls",
    "tool_errors", 
    "tool_duration",
    "in_bytes",
    "out_bytes",
]
