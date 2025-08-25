# composer/member_server.py
from enum import Enum
from typing import Optional, Dict, Any, Annotated
import pydantic_core
from pydantic import BaseModel, Field, BeforeValidator
from fastmcp import FastMCP
from fastmcp.utilities.components import (
    _convert_set_default_none,
)
from mcp_composer.core.utils import LoggerFactory

logger = LoggerFactory.get_logger()


def default_serializer(data: Any) -> str:
    return pydantic_core.to_json(data, fallback=str, indent=2).decode()


class HealthStatus(str, Enum):
    healthy = "OK"
    unhealthy = "Down"


class MemberMCPServer(BaseModel):
    """
    Base Unit that wraps metadata and a reference to a mounted FastMCP server.
    The actual `server` instance is excluded from serialization.
    """

    id: str = Field(..., description="Unique ID of the mounted MCP server")
    type: str = Field(..., description="Server type: openapi, client, fastapi, etc.")
    label: Optional[str] = Field(None, description="Human-friendly label")
    tags: Annotated[set[str], BeforeValidator(_convert_set_default_none)] = Field(
        default_factory=set, description="Tags for the tool"
    )
    config: Dict[str, Any] = Field(
        ..., description="Original config used to build the server"
    )
    tool_count: Optional[int] = Field(None, description="Number of tools registered")
    disabled_tools: list[str] = Field(default_factory=list, description="Removed tools")
    tools_description: dict[str, str] = Field(
        default_factory=dict, description="Removed tools"
    )
    disabled_prompts: list[str] = Field(
        default_factory=list, description="Disabled prompts"
    )
    prompts_description: dict[str, str] = Field(
        default_factory=dict, description="Prompt descriptions"
    )
    disabled_resources: list[str] = Field(
        default_factory=list, description="Disabled resources"
    )
    resources_description: dict[str, str] = Field(
        default_factory=dict, description="Resource descriptions"
    )
    health_status: HealthStatus = Field(
        default=HealthStatus.healthy, description="Server health status"
    )

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
