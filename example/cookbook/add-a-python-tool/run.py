"""Create one composer tool from a Python function string."""

import asyncio
import tempfile
from pathlib import Path

from mcp_composer import MCPComposer

SCRIPT = '''
def count_open_boxes(shelf: str) -> str:
    """Count open boxes on a named shelf. Use when the caller asks how many boxes are still open."""
    return f"{shelf} open: 2"
'''


async def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        composer = MCPComposer(
            "composer",
            database_config={
                "type": "local_file",
                "file_path": str(Path(tmp) / "servers.json"),
            },
        )
        message = await composer.add_tools_from_python(
            {
                "name": "count_open_boxes",
                "tool_type": "python",
                "description": "Count open boxes on a named shelf.",
                "script_config": {"value": SCRIPT},
            }
        )
        tools = await composer.list_tools()
        names = sorted(tool.name for tool in tools if tool.name == "count_open_boxes")
        print(message)
        print("tools: " + ", ".join(names))


if __name__ == "__main__":
    asyncio.run(main())
