from fastmcp import FastMCP
from mcp_composer.middleware.rate_limit import RateLimiterMiddleware
import asyncio
import time

app = FastMCP("Rate Limiter Demo Server")


# Example tool with different rate limits
@app.tool()
async def search_docs(query: str) -> dict:
    """
    A search tool with lower rate limits.
    """
    await asyncio.sleep(0.1)  # Simulate processing

    return {
        "status": "success",
        "query": query,
        "results": [f"Result for: {query}"],
        "timestamp": time.time(),
    }


@app.tool()
async def ask_llm(query: str) -> dict:
    """
    An LLM tool with higher rate limits but higher cost.
    """
    await asyncio.sleep(0.2)  # Simulate processing

    return {
        "status": "success",
        "query": query,
        "response": f"AI response to: {query}",
        "tokens_used": len(query.split()) * 2,  # Rough estimate
        "timestamp": time.time(),
    }


# Add rate limiter middleware
app.add_middleware(
    RateLimiterMiddleware(
        per_tool={
            # tool: (capacity, refill_per_sec, default_cost)
            "search_docs": (5.0, 0.5, 1.0),  # burst 5, 0.5/s (~30/min)
            "ask_llm": (10.0, 1.0, 5.0),  # burst 10, 1/s, cost ~5 per call
        },
        per_tenant_global=(20.0, 2.0),  # burst 20, 2/s across all tools
        per_tenant_daily_budget=1000.0,  # 1000 "cost units" per rolling 24h
        estimate_cost=lambda tool, args: (len((args.get("query") or "")) / 10 if tool == "ask_llm" else 1.0),
        get_tenant=lambda ctx: getattr(ctx, "tenant_id", "default"),
        get_user=lambda ctx: getattr(ctx, "user_id", "default"),
    )
)


async def main():
    await app.run_http_async(host="0.0.0.0", port=8000, log_level="debug", path="/mcp")


if __name__ == "__main__":
    asyncio.run(main())
