"""Print how many member servers an empty composer has."""

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
        await composer.setup_member_servers()
        servers = composer._server_manager.list_servers()
        print(f"member servers: {len(servers)}")


if __name__ == "__main__":
    asyncio.run(main())
