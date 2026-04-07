"""
Core models module for MCP Composer.

This module provides Pydantic models for:
- Tool configuration and authentication
- OAuth and authentication strategies
- MCP server configuration
- Strongly-typed configuration models for all system components
- Agentregistry-aligned skill / agent / prompt registry payloads

MAX_VERSIONS_PER_RESOURCE is defined in catalog_constants (not re-exported from this package).
"""

from .tool import ToolBuilderConfig, OpenApiToolAuthConfig
from .oauth import BearerAuth, DynamicBearerAuth, BasicAuth, APIkey
from .mcp_stdio import MCPServerStdio
from .catalog_constants import RegistryResourceKind
from .catalog_common import (
    RegistryListMetadata,
    RegistryOfficialExtensions,
)
from .catalog_skill import (
    SkillCatalogReference,
    SkillJSON,
    SkillListResponse,
    SkillRemoteInfo,
    SkillRepository,
    SkillResponse,
    SkillResponseMeta,
)
from .catalog_agent import (
    AgentJSON,
    AgentListResponse,
    AgentRegistryRepository,
    AgentRegistryTransport,
    AgentResponse,
    AgentResponseMeta,
    AgentSemanticMeta,
    DeploymentSummary,
    McpServerType,
    PromptRef,
    ResourceDeploymentsMeta,
    SkillRef,
)
from .catalog_prompt import (
    PromptJSON,
    PromptListResponse,
    PromptResponse,
    PromptResponseMeta,
)
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
    "RegistryResourceKind",
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
    # Catalog models (agentregistry-aligned)
    "RegistryOfficialExtensions",
    "RegistryListMetadata",
    "AgentSemanticMeta",
    "DeploymentSummary",
    "ResourceDeploymentsMeta",
    "AgentRegistryRepository",
    "AgentRegistryTransport",
    "SkillJSON",
    "SkillRepository",
    "SkillCatalogReference",
    "SkillRemoteInfo",
    "SkillResponseMeta",
    "SkillResponse",
    "SkillListResponse",
    "SkillRef",
    "PromptRef",
    "McpServerType",
    "AgentJSON",
    "AgentResponseMeta",
    "AgentResponse",
    "AgentListResponse",
    "PromptJSON",
    "PromptResponseMeta",
    "PromptResponse",
    "PromptListResponse",
]
