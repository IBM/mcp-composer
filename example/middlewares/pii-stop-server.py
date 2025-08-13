import asyncio
from fastmcp import FastMCP
from mcp_composer.middleware.stop_pii import SecretsAndPIIMiddleware, RedactionStrategy

app = FastMCP("Secrets & PII Demo Server")


# Example tool: just echoes the input back
@app.tool()
async def process_form(data: dict) -> dict:
    """
    Pretend to process a form submission and return stored values.
    """
    return {"status": "ok", "received": data}


# Attach the Secrets & PII Redaction middleware
app.add_middleware(
    SecretsAndPIIMiddleware(
        strategy=RedactionStrategy(mode="mask"),  # mask, hash, or tokenize
        allowlist_tools=[],  # no exemptions
        allowlist_fields=["public_info"],  # these fields won't be redacted
        redact_inputs=True,
        redact_outputs=True,
    )
)


async def main():
    await app.run_http_async(host="0.0.0.0", port=8000, log_level="debug", path="/mcp")


if __name__ == "__main__":
    asyncio.run(main())
