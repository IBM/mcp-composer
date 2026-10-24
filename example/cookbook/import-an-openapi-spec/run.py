"""Turn a local OpenAPI file into composer tools and print their names."""

import asyncio
import os
import tempfile
from pathlib import Path

from mcp_composer import MCPComposer

HERE = Path(__file__).resolve().parent
SPEC = HERE / "shelf.openapi.json"


async def main() -> None:
    os.environ["MCP_COMPOSER_MODE"] = "dev"
    with tempfile.TemporaryDirectory() as tmp:
        store = str(Path(tmp) / "servers.json")
        composer = MCPComposer(
            "composer",
            database_config={"type": "local_file", "file_path": store},
        )
        message = await composer.register_mcp_server(
            {
                "id": "shelf-api",
                "type": "openapi",
                "open_api": {
                    "endpoint": "http://127.0.0.1:9",
                    "spec_filepath": str(SPEC),
                },
            }
        )
        tools = await composer.list_tools()
        names = sorted(
            tool.name
            for tool in tools
            if tool.name in {"list_shelf_items", "remove_shelf_item"}
            or tool.name.endswith("list_shelf_items")
            or tool.name.endswith("remove_shelf_item")
        )
        print(message)
        print("openapi tools: " + ", ".join(names))


if __name__ == "__main__":
    asyncio.run(main())
