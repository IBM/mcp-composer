"""Register one prompt and print its name."""

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
        names = composer.add_prompts(
            {
                "name": "shelf_summary",
                "description": "Summarize what is on a shelf.",
                "template": "Summarize the shelf called {shelf_name}.",
                "arguments": [
                    {
                        "name": "shelf_name",
                        "description": "Shelf label",
                        "required": True,
                    }
                ],
            }
        )
        print(f"prompts: {', '.join(names)}")


if __name__ == "__main__":
    asyncio.run(main())
