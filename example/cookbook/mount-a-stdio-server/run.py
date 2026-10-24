"""Mount a local stdio server, list its tools, and call one."""

import asyncio
import os
import sys
import tempfile
from pathlib import Path

from mcp_composer import MCPComposer

HERE = Path(__file__).resolve().parent
SERVER = HERE / "shelf_server.py"
PYTHON = str(Path(sys.executable).resolve())


def _site_packages() -> str:
    for entry in sys.path:
        if entry.endswith("site-packages"):
            return entry
    raise RuntimeError("Could not find site-packages for the member server.")


def _child_env() -> dict[str, str]:
    kept = {}
    for key in ("PATH", "HOME", "LANG", "VIRTUAL_ENV"):
        value = os.environ.get(key)
        if value:
            kept[key] = value
    kept["PYTHONPATH"] = _site_packages()
    return kept


async def main() -> None:
    os.environ["MCP_COMPOSER_STDIO_ALLOWLIST"] = PYTHON
    with tempfile.TemporaryDirectory() as tmp:
        store = str(Path(tmp) / "servers.json")
        composer = MCPComposer(
            "composer",
            database_config={"type": "local_file", "file_path": store},
        )
        message = await composer.register_mcp_server(
            {
                "id": "shelf",
                "type": "stdio",
                "command": PYTHON,
                "args": [str(SERVER)],
                "cwd": str(HERE),
                "env": _child_env(),
            }
        )
        tools = await composer.list_tools()
        names = sorted(
            tool.name
            for tool in tools
            if tool.name.endswith("count_items") or tool.name.endswith("mark_sold")
        )
        print(message)
        print("shelf tools: " + ", ".join(names))
        count_tool = next(name for name in names if name.endswith("count_items"))
        called = await composer.call_tool(count_tool, {"shelf": "corner"})
        text = called.content[0].text if getattr(called, "content", None) else called
        print(f"call: {text}")


if __name__ == "__main__":
    asyncio.run(main())
