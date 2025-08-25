# metrics_registry.py
from __future__ import annotations
from typing import Optional

# These are set after init_metrics_if_enabled() returns a meter.
tool_calls = None
tool_errors = None
tool_duration = None
in_bytes = None
out_bytes = None


def init_instruments(meter) -> None:
    global tool_calls, tool_errors, tool_duration, in_bytes, out_bytes
    if meter is None:
        return

    tool_calls = meter.create_counter(
        name="mcp.tool.calls",
        unit="1",
        description="Number of MCP tool calls",
    )
    tool_errors = meter.create_counter(
        name="mcp.tool.errors",
        unit="1",
        description="Number of MCP tool call errors",
    )
    tool_duration = meter.create_histogram(
        name="mcp.tool.duration",
        unit="ms",
        description="Latency of MCP tool calls",
    )
    in_bytes = meter.create_histogram(
        name="mcp.tool.input_bytes",
        unit="By",
        description="Input payload size (bytes)",
    )
    out_bytes = meter.create_histogram(
        name="mcp.tool.output_bytes",
        unit="By",
        description="Output payload size (bytes)",
    )
