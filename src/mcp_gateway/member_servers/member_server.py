# gateway/member_server.py
import pydantic_core
from pydantic import BaseModel, Field, BeforeValidator, Field
from collections.abc import Callable
from fastmcp import FastMCP
from typing import Optional, List, Dict, Any, Annotated
from fastmcp.utilities.types import (
    _convert_set_defaults,
)
from mcp_gateway.utils import LoggerFactory

logger = LoggerFactory.get_logger()


def default_serializer(data: Any) -> str:
    return pydantic_core.to_json(data, fallback=str, indent=2).decode()


class MemberMCPServer(BaseModel):
    """
    Base Unit that wraps metadata and a reference to a mounted FastMCP server.
    The actual `server` instance is excluded from serialization.
    """

    id: str = Field(..., description="Unique ID of the mounted MCP server")
    type: str = Field(..., description="Server type: openapi, client, fastapi, etc.")
    label: Optional[str] = Field(None, description="Human-friendly label")
    tags: Annotated[set[str], BeforeValidator(_convert_set_defaults)] = Field(
        default_factory=set, description="Tags for the tool"
    )
    config: Dict[str, Any] = Field(
        ..., description="Original config used to build the server"
    )
    tool_count: Optional[int] = Field(None, description="Number of tools registered")

    # Runtime-only field (not serialized)
    server: Optional[FastMCP] = Field(default=None, exclude=True)
    model_config = {"arbitrary_types_allowed": True}

    def set_server(self, mcp: FastMCP):
        self.server = mcp
        # self.tool_count = len(mcp.get_tools()) if hasattr(mcp, "list_tools") else None

    def get_server(self) -> FastMCP:
        if not self.server:
            raise RuntimeError("Server instance has not been set.")
        return self.server

    def to_dict(self) -> Dict[str, Any]:
        return self.dict(exclude={"server"})
