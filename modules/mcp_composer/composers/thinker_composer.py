import os
import asyncio
from fastmcp.tools import Tool
from mcp_composer import MCPComposer
from mcp_composer.core.tools.sequential_thinking_tool import SequentialThinkingTool
from mcp_composer.core.tools.deep_research_tool import DeepResearchTool

gw = MCPComposer("thinker-composer")


async def main():
    """
    Thinker Composer: A specialized MCP Composer focused on thinking and research tools.
    Includes Sequential Thinking Tool and Deep Research Tool for advanced problem-solving.
    """
    mode = os.getenv("MCP_MODE", "sse").lower()
    # Disable all composer tools
    await gw.disable_composer_tool()
    # Add thinking and research tools
    sequential_tool = SequentialThinkingTool({"name": "sequential_thinking"})
    gw.add_tool(sequential_tool)

    deep_research_tool = DeepResearchTool(
        {
            "name": "deep_research",
            "resource_manager": gw.resource_manager,
        }
    )
    gw.add_tool(deep_research_tool)

    # simple_llm_tool = SmallLLMTool({"name": "simple_llm"})
    # gw.add_tool(simple_llm_tool)

    await gw.setup_member_servers()

    if mode == "http":
        await gw.run_http_async(
            host="0.0.0.0", port=9000, log_level="debug", path="/mcp"
        )
    elif mode == "stdio":
        await gw.run_stdio_async()
    elif mode == "sse":
        await gw.run_sse_async(host="localhost", port=9000, log_level="debug")  # type: ignore[attr-defined]
    else:
        raise ValueError(f"Unsupported MCP_MODE: {mode}")


if __name__ == "__main__":
    asyncio.run(main())
