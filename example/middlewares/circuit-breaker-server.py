from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from mcp_composer.middleware.circuit_breaker import CircuitBreakerMiddleware
import asyncio
import random

app = FastMCP("Circuit Breaker Demo Server")


# Example tool that sometimes fails to demonstrate circuit breaker
@app.tool()
async def unreliable_service(data: str) -> dict:
    """
    A service that randomly fails to demonstrate circuit breaker behavior.
    """
    # Simulate random failures (30% failure rate)
    if random.random() < 0.3:
        raise ToolError("Service temporarily unavailable")

    # Simulate some processing time
    await asyncio.sleep(0.1)

    return {
        "status": "success",
        "processed_data": data,
        "timestamp": asyncio.get_event_loop().time(),
    }


# Add circuit breaker middleware
app.add_middleware(
    CircuitBreakerMiddleware(
        failure_threshold=3,  # Trip after 3 failures
        open_timeout=10.0,  # Stay open for 10 seconds
        window_seconds=30.0,  # Count failures in 30-second window
        exempt_tools=set(),  # No exempt tools
    )
)


async def main():
    await app.run_http_async(host="0.0.0.0", port=8000, log_level="debug", path="/mcp")


if __name__ == "__main__":
    asyncio.run(main())
