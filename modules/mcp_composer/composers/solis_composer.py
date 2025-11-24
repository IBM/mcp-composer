import os
import asyncio
from mcp_composer.core.tools.ibm_document_search_tool import IBMDocumentSearchTool
from mcp_composer.middleware.tool.tool_filter import ListFilteredTool
from mcp_composer import MCPComposer


gw = MCPComposer("solis-composer")


async def main():
    """_summary_

    Raises:
        ValueError: _description_
    """
    mode = os.getenv("MCP_MODE", "sse").lower()
    gw.add_middleware(ListFilteredTool(gw))
    deep_research_tool = IBMDocumentSearchTool(
        {
            "name": "ibm_document_search",
            "resource_manager": gw.resource_manager,
        }
    )
    gw.add_tool(deep_research_tool)
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
