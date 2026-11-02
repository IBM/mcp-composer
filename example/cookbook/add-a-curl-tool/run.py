"""Create one composer tool from a curl command. The command is not sent."""

import asyncio
import tempfile
from pathlib import Path

from mcp_composer import MCPComposer


async def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        composer = MCPComposer(
            "composer",
            database_config={
                "type": "local_file",
                "file_path": str(Path(tmp) / "servers.json"),
            },
        )
        message = await composer.add_tools_from_curl(
            {
                "name": "list_shelf_items",
                "tool_type": "curl",
                "description": "List items on a shelf. Use when the caller wants the current rows.",
                "curl_config": {"value": "curl http://127.0.0.1:9/shelf"},
            }
        )
        tools = await composer.list_tools()
        names = sorted(tool.name for tool in tools if tool.name == "list_shelf_items")
        print(message)
        print("tools: " + ", ".join(names))


if __name__ == "__main__":
    asyncio.run(main())
