"""Two stock tools whose descriptions say when not to use the other."""

from fastmcp import FastMCP

mcp = FastMCP("stock")


@mcp.tool
def count_open_boxes(shelf: str) -> str:
    """Count open boxes on a named shelf. Use when the caller asks how many boxes are still open. Do not use for sealed boxes."""
    return f"{shelf} open: 2"


@mcp.tool
def count_sealed_boxes(shelf: str) -> str:
    """Count sealed boxes on a named shelf. Use when the caller asks how many boxes are sealed. Do not use for open boxes."""
    return f"{shelf} sealed: 5"


if __name__ == "__main__":
    mcp.run(transport="stdio")
