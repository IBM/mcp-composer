import os
import sys
import asyncio
from mcp_composer.middleware.tool.tool_filter import ListFilteredTool
from mcp_composer import MCPComposer

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))


gw = MCPComposer("solis-composer")


async def main():
    """_summary_

    Raises:
        ValueError: _description_
    """
    mode = os.getenv("MCP_MODE", "sse").lower()
    gw.add_middleware(ListFilteredTool(gw))
    await gw.setup_member_servers()

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
