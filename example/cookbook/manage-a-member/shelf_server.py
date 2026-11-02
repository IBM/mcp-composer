"""A one-tool member used to show pause, resume, and removal."""

from fastmcp import FastMCP

mcp = FastMCP("shelf")


@mcp.tool
def count_open_boxes(shelf: str) -> str:
    """Count open boxes on a named shelf. Use when the caller asks how many boxes are still open. Do not use to change stock."""
    return f"{shelf} open: 2"


if __name__ == "__main__":
    mcp.run(transport="stdio")
