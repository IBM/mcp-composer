import os
import sys
import asyncio
from mcp_composer.core.composer import MCPComposer
from mcp_composer.core.middleware.middleware_manager import MiddlewareManager
from mcp_composer.middleware import SecretsAndPIIMiddleware, PromptInjectionMiddleware
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))


gw = MCPComposer("hello-composer")


@gw.tool()
def get_data():
    form_data = {
            "name": "Alice Example",
            "email": "alice@example.com",
            "password": "SuperSecret123!",
            "credit_card": "4111 1111 1111 1111",
            "note": "Please call me at +1-202-555-0123",
            "public_info": "This is fine to show",
        }
    return form_data


async def main():
    """_summary_

    Raises:
        ValueError: _description_
    """
    mode = os.getenv("MCP_MODE", "http").lower()

    await gw.setup_member_servers()

    # gw.add_middleware(
    # SecretsAndPIIMiddleware(
    #     strategy=RedactionStrategy(mode="mask"),  # mask, hash, or tokenize
    #     allowlist_tools=[],  # no exemptions
    #     allowlist_fields=["public_info"],  # these fields won't be redacted
    #     redact_inputs=True,
    #     redact_outputs=True,
    # )
    # )


    gw.add_middleware(
    PromptInjectionMiddleware(
        block_on_high_risk=True,
        threshold=0.75,
        url_allowlist=["https://safe.example.com/"],
        sanitize_on_medium=True,
        inspect_fields=["query"],
    )
)


    mgr = MiddlewareManager("./middlewares/config/middleware-config.json", ensure_imports=True)
    mgr.attach_to_server(gw)
    # Optional: print what got attached in order
    for info in mgr.describe():
        print(f"[middleware] {info['name']} priority={info['priority']} hooks={info['applied_hooks']}")

    if mode == "http":
        await gw.run_http_async(host="0.0.0.0", port=9000, log_level="debug", path="/mcp")
    elif mode == "stdio":
        await gw.run_stdio_async()
    elif mode == "sse":
        await gw.run_sse_async(host="0.0.0.0", port=9000, log_level="debug")
    else:
        raise ValueError(f"Unsupported MCP_MODE: {mode}")


if __name__ == "__main__":
    asyncio.run(main())
