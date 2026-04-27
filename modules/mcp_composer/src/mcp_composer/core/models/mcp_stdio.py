"""Pydantic model for MCP using stdio"""

from pydantic import BaseModel, Field


class MCPServerStdio(BaseModel):
    """Model for MCP server using stdio transport"""

    id: str = Field(..., description="Name of the mcp server")
    type: str = Field(..., description="Type of mcp server")
    args: list[str] = Field(..., description="List of arguments, e.g., server.py")
    env: dict[str, str] | None = Field(
        default=None, description="environment variables"
    )
    cwd: str | None = Field(
        default=None, description="Working directory, e.g., /path/to/server"
    )
