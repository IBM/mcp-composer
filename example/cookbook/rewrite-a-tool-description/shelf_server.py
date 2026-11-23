"""A one-tool member whose description the composer will replace."""

from fastmcp import FastMCP

mcp = FastMCP("shelf")


@mcp.tool
def count_open_boxes(shelf: str) -> str:
    """Count open boxes on a named shelf."""
    return f"{shelf} open: 2"


if __name__ == "__main__":
    mcp.run(transport="stdio")
