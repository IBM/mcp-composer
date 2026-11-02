"""Replace the description stored for one mounted tool."""

import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stdio_support import allow_stdio, composer_in, stdio_config

HERE = Path(__file__).resolve().parent
SERVER = HERE / "shelf_server.py"
NEW = (
    "Count open boxes on a named shelf, for example corner. "
    "Use when the caller needs a number. Do not use to seal a box."
)


async def main() -> None:
    allow_stdio()
    with tempfile.TemporaryDirectory() as tmp:
        composer = composer_in(tmp)
        await composer.register_mcp_server(stdio_config("shelf", SERVER))
        message = await composer._tool_manager.update_tool_description(
            "count_open_boxes", NEW, "shelf"
        )
        stored = composer._server_manager.get("shelf").tools_description
        print(message)
        print("stored: " + stored["count_open_boxes"])


if __name__ == "__main__":
    asyncio.run(main())
