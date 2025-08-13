from fastmcp import FastMCP
import asyncio

from mcp_composer.middleware.prompt_injection import PromptInjectionMiddleware

app = FastMCP("Prompt Injection Demo Server")


# A simple tool that echoes user input (vulnerable to prompt injection without middleware)
@app.tool()
async def ask_agent(query: str) -> str:
    """
    Sends the user query to an LLM-powered agent and returns the answer.
    """
    return f"Agent answer to: {query}"


# Add the middleware
app.add_middleware(
    PromptInjectionMiddleware(
        block_on_high_risk=True,
        threshold=0.75,
        url_allowlist=["https://safe.example.com/"],
        sanitize_on_medium=True,
        inspect_fields=["query"],
    )
)


async def main():
    await app.run_http_async(host="0.0.0.0", port=8000, log_level="debug", path="/mcp")


if __name__ == "__main__":
    asyncio.run(main())
