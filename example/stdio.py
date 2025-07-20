"""server.py"""

from fastmcp import FastMCP

mcp = FastMCP("Demo 🚀")


@mcp.tool
def hello(name: str) -> str:
    """hello world function"""
    return f"Hello, {name}!"


if __name__ == "__main__":
    mcp.run()  # Default: uses STDIO transport
