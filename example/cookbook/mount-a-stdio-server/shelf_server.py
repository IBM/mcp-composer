"""A small member server with two shelf tools. Speaks MCP on stdio."""

from fastmcp import FastMCP

mcp = FastMCP("shelf")


@mcp.tool
def count_items(shelf: str) -> str:
    """Count items on a named shelf. Use for an inventory check. Do not use to change stock."""
    return f"{shelf}: 3"


@mcp.tool
def mark_sold(shelf: str) -> str:
    """Mark one item sold on a named shelf. Use only when stock should change."""
    return f"{shelf}: sold 1"


if __name__ == "__main__":
    mcp.run(transport="stdio")
