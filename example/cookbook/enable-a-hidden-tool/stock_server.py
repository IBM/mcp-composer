"""A read tool and a write tool for the same shelf."""

from fastmcp import FastMCP

mcp = FastMCP("stock")


@mcp.tool
def count_open_boxes(shelf: str) -> str:
    """Count open boxes on a named shelf. Use when the caller asks how many boxes are still open. Do not use to change stock."""
    return f"{shelf} open: 2"


@mcp.tool
def seal_box(shelf: str) -> str:
    """Seal one open box on a named shelf. Use only when stock should change. Do not use to count boxes."""
    return f"{shelf}: sealed 1"


if __name__ == "__main__":
    mcp.run(transport="stdio")
