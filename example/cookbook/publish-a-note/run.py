"""Store a text resource and print the composer response."""

import asyncio
import tempfile
from pathlib import Path

from mcp_composer import MCPComposer


async def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = str(Path(tmp) / "servers.json")
        composer = MCPComposer(
            "composer",
            database_config={"type": "local_file", "file_path": store},
        )
        message = await composer.create_resource(
            {
                "name": "shelf-note",
                "uri": "resource://shelf-note",
                "description": "A short note a client can read.",
                "text": "The corner shelf holds spare parts.",
            }
        )
        print(message)


if __name__ == "__main__":
    asyncio.run(main())
