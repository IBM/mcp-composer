"""Mount a member, pause it, resume it, replace its config, then remove it."""

import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stdio_support import active_ids, allow_stdio, composer_in, stdio_config

HERE = Path(__file__).resolve().parent
SERVER = HERE / "shelf_server.py"


async def main() -> None:
    allow_stdio()
    config = stdio_config("shelf", SERVER)
    with tempfile.TemporaryDirectory() as tmp:
        composer = composer_in(tmp)
        mounted = await composer.register_mcp_server(config)
        print(mounted)
        print("active: " + active_ids(composer))
        paused = await composer.deactivate_mcp_server("shelf")
        print(paused)
        print("active: " + active_ids(composer))
        resumed = await composer.activate_mcp_server("shelf")
        print(resumed)
        print("active: " + active_ids(composer))
        replaced = await composer.update_mcp_server_config("shelf", config)
        print("updated: " + replaced)
        removed = await composer.delete_mcp_server("shelf")
        print(removed)
        print("active: " + active_ids(composer))


if __name__ == "__main__":
    asyncio.run(main())
