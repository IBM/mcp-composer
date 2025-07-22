"""Pydantic model for MCP using stdio"""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class MCPServerStdio(BaseModel):
    """Model for MCP server using stdio transport"""

    id: str = Field(..., description="Name of the mcp server")
    type: str = Field(..., description="Type of mcp server")
    args: List[str] = Field(..., description="List of arguments, e.g., server.py")
    env: Optional[Dict[str, str]] = Field(
        default=None, description="environment variables"
    )
    cwd: Optional[str] = Field(
        default=None, description="Working directory, e.g., /path/to/server"
    )
