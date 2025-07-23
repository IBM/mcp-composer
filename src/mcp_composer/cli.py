# src/mcp_composer/cli.py
import asyncio
import argparse

from mcp_composer import MCPComposer
from mcp_composer.middleware.tool_filter import ListFilteredTool

mcp = MCPComposer("composer")


async def run(mode: str, host: str, port: int, log_level: str, path: str):
    mcp.add_middleware(ListFilteredTool(mcp))
    await mcp.setup_member_servers()

    if mode == "http":
        await mcp.run_http_async(host=host, port=port, log_level=log_level, path=path)
    elif mode == "stdio":
        await mcp.run_stdio_async()
    else:
        raise ValueError(f"Unsupported MCP_MODE: {mode}")


def main():
    parser = argparse.ArgumentParser(description="Run MCP Composer")

    parser.add_argument("--mode", choices=["http", "stdio"], default="http", help="MCP mode to run (http or stdio)")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind (http mode)")
    parser.add_argument("--port", type=int, default=9000, help="Port to bind (http mode)")
    parser.add_argument("--log-level", default="debug", help="Log level")
    parser.add_argument("--path", default="/mcp", help="Path to mount (http mode)")

    args = parser.parse_args()
    asyncio.run(run(args.mode, args.host, args.port, args.log_level, args.path))


if __name__ == "__main__":
    main()
