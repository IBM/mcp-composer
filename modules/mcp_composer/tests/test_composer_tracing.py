import os
import sys
import asyncio
from mcp_composer.features.tracing_setup import (
    init_tracing_if_enabled,
    init_metrics_if_enabled,
)
from mcp_composer.middleware.tracing_middleware import TracingMiddleware
from mcp_composer.features.config import TRACING_ENABLED
from mcp_composer import MCPComposer
from mcp_composer.features.opentelemetry_metrics_registry import init_instruments

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

ok = init_tracing_if_enabled()
print("Tracing init:", ok)

_meter = init_metrics_if_enabled()
init_instruments(_meter)

gw = MCPComposer("hello-composer")


async def main():
    """_summary_

    Raises:
        ValueError: _description_
    """
    mode = os.getenv("MCP_MODE", "http").lower()
    gw.add_middleware(
        TracingMiddleware(
            enable_tracing=TRACING_ENABLED,
            log_tools=True,
            trace_args_digest=True,
            trace_results_digest=True,
            trace_payload_sizes=True,
        )
    )

    await gw.setup_member_servers()

    if mode == "http":
        await gw.run_http_async(
            host="0.0.0.0", port=9000, log_level="debug", path="/mcp"
        )
    elif mode == "stdio":
        await gw.run_stdio_async()
    elif mode == "sse":
        await gw.run_sse_async(host="0.0.0.0", port=9000, log_level="debug")
    else:
        raise ValueError(f"Unsupported MCP_MODE: {mode}")


if __name__ == "__main__":
    asyncio.run(main())
