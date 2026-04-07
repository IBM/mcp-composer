"""
Core models module for MCP Composer.

This module provides Pydantic models for:
- Tool configuration and authentication
- OAuth and authentication strategies
- MCP server configuration
- Strongly-typed configuration models for all system components
"""

from .tool import ToolBuilderConfig, OpenApiToolAuthConfig
from .oauth import BearerAuth, DynamicBearerAuth, BasicAuth, APIkey
from .mcp_stdio import MCPServerStdio
from .config import (
    # Base
    BaseConfig,
    # Enums
    ServerType,
    AuthStrategy,
    DatabaseType,
    MiddlewareMode,
    # Configuration models
    AuthConfig,
    OpenAPIConfig,
    GraphQLConfig,
    ServerConfig,
    DatabaseConfig,
    MiddlewareConfig,
    ToolConfig,
    PromptArgument,
    PromptConfig,
    ResourceConfig,
)

__all__ = [
    # Tool models
    "ToolBuilderConfig",
    "OpenApiToolAuthConfig",
    # Authentication models (legacy)
    "BearerAuth",
    "DynamicBearerAuth",
    "BasicAuth",
    "APIkey",
    # MCP server models
    "MCPServerStdio",
    # Base configuration
    "BaseConfig",
    # Enums
    "ServerType",
    "AuthStrategy",
    "DatabaseType",
    "MiddlewareMode",
    # Strongly-typed configuration models
    "AuthConfig",
    "OpenAPIConfig",
    "GraphQLConfig",
    "ServerConfig",
    "DatabaseConfig",
    "MiddlewareConfig",
    "ToolConfig",
    "PromptArgument",
    "PromptConfig",
    "ResourceConfig",
]
