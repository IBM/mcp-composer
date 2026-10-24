"""A shelf member that speaks MCP over local HTTP."""

import sys

from fastmcp import FastMCP

mcp = FastMCP("shelf")


@mcp.tool
def count_open_boxes(shelf: str) -> str:
    """Count open boxes on a named shelf. Use when the caller asks how many boxes are still open. Do not use to change stock."""
    return f"{shelf} open: 2"


if __name__ == "__main__":
    mcp.run(transport="http", host="127.0.0.1", port=int(sys.argv[1]))
