"""Hide a write tool, then show it again."""

import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stdio_support import allow_stdio, composer_in, stdio_config

HERE = Path(__file__).resolve().parent
SERVER = HERE / "stock_server.py"


def _names(tools) -> str:
    kept = sorted(
        tool.name
        for tool in tools
        if tool.name.endswith("count_open_boxes") or tool.name.endswith("seal_box")
    )
    return ", ".join(kept)


async def main() -> None:
    allow_stdio()
    with tempfile.TemporaryDirectory() as tmp:
        composer = composer_in(tmp)
        await composer.register_mcp_server(stdio_config("stock", SERVER))
        before = _names(await composer.list_tools())
        hidden = await composer._tool_manager.disable_tools_by_server(
            ["seal_box"], "stock"
        )
        disabled = set(composer._server_manager.get("stock").disabled_tools)
        middle = ", ".join(
            name
            for name in before.split(", ")
            if name.removeprefix("stock_") not in disabled
        )
        shown = await composer._tool_manager.enable_tools_by_server(
            ["seal_box"], "stock"
        )
        after = _names(await composer.list_tools())
        print("before: " + before)
        print(hidden)
        print("hidden: " + middle)
        print(shown)
        print("after: " + after)


if __name__ == "__main__":
    asyncio.run(main())
