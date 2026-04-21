"""Pydantic models for agent registry JSON (agentregistry pkg/models/agent + manifest)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from mcp_composer.core.models.catalog_common import (
    RegistryListMetadata,
    RegistryOfficialExtensions,
)
from mcp_composer.core.models.catalog_skill import SkillCatalogReference
from mcp_composer.core.utils.catalog_validators import (
    require_non_empty_after_strip,
    validate_agent_name,
    validate_registry_version,
)


class AgentRegistryRepository(BaseModel):
    """MCP registry repository object on agent JSON (model.Repository)."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    url: Optional[str] = None
    source: Optional[str] = None
    id: Optional[str] = None
    subfolder: Optional[str] = None


class AgentRegistryTransport(BaseModel):
    """MCP registry transport on agent remotes (model.Transport); headers may be rich objects."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    transport_type: str = Field(..., alias="type")
    url: Optional[str] = None
    headers: Optional[List[Dict[str, Any]]] = None


class AgentSemanticMeta(BaseModel):
    """`aregistry.ai/semantic` fragment."""

    model_config = ConfigDict(extra="forbid")

    score: float


class DeploymentSummary(BaseModel):
    """Compact deployment row embedded in catalog _meta."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str
    provider_id: Optional[str] = Field(default=None, alias="providerId")
    status: str
    origin: str
    version: Optional[str] = None
    deployed_at: datetime = Field(alias="deployedAt")
    updated_at: datetime = Field(alias="updatedAt")


class ResourceDeploymentsMeta(BaseModel):
    """`aregistry.ai/deployments` fragment."""

    model_config = ConfigDict(extra="forbid")

    deployments: List[DeploymentSummary]
    count: int


class SkillRef(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, str_strip_whitespace=True)

    name: str
    image: Optional[str] = None
    registry_url: Optional[str] = Field(default=None, alias="registryURL")
    registry_skill_name: Optional[str] = Field(default=None, alias="registrySkillName")
    registry_skill_version: Optional[str] = Field(default=None, alias="registrySkillVersion")


class PromptRef(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, str_strip_whitespace=True)

    name: str
    registry_url: Optional[str] = Field(default=None, alias="registryURL")
    registry_prompt_name: Optional[str] = Field(default=None, alias="registryPromptName")
    registry_prompt_version: Optional[str] = Field(default=None, alias="registryPromptVersion")


class McpServerType(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, str_strip_whitespace=True)

    server_type: str = Field(..., alias="type")
    name: str
    image: Optional[str] = None
    build: Optional[str] = None
    command: Optional[str] = None
    args: Optional[List[str]] = None
    env: Optional[List[str]] = None
    url: Optional[str] = None
    headers: Optional[dict[str, str]] = None
    registry_url: Optional[str] = Field(default=None, alias="registryURL")
    registry_server_name: Optional[str] = Field(default=None, alias="registryServerName")
    registry_server_version: Optional[str] = Field(default=None, alias="registryServerVersion")
    registry_server_prefer_remote: Optional[bool] = Field(
        default=None, alias="registryServerPreferRemote"
    )


class AgentJSON(BaseModel):
    """Flattened agent payload: manifest fields plus registry-specific fields.

    JSON carries a single ``version`` key (manifest ``version`` and outer ``version`` coincide).
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True, str_strip_whitespace=True)

    name: str
    image: str
    language: str
    framework: str
    model_provider: str = Field(alias="modelProvider")
    model_name: str = Field(alias="modelName")
    description: str
    version: str
    telemetry_endpoint: Optional[str] = Field(default=None, alias="telemetryEndpoint")
    mcp_servers: Optional[List[McpServerType]] = Field(default=None, alias="mcpServers")
    skills: Optional[List[SkillRef]] = None
    prompts: Optional[List[PromptRef]] = None
    updated_at: Optional[datetime] = Field(default=None, alias="updatedAt")
    title: Optional[str] = None
    status: Optional[str] = None
    website_url: Optional[str] = Field(default=None, alias="websiteUrl")
    repository: Optional[AgentRegistryRepository] = None
    references: Optional[List[SkillCatalogReference]] = None
    remotes: Optional[List[AgentRegistryTransport]] = None

    @field_validator("name", mode="before")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        return validate_agent_name(str(v))

    @field_validator(
        "image",
        "language",
        "framework",
        "model_provider",
        "model_name",
        "description",
        mode="before",
    )
    @classmethod
    def _required_manifest_strings(cls, v: str, info):  # type: ignore[no-untyped-def]
        return require_non_empty_after_strip(str(v), info.field_name)

    @field_validator("version", mode="before")
    @classmethod
    def _validate_version(cls, v: str) -> str:
        return validate_registry_version(str(v))


class AgentResponseMeta(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    official: Optional[RegistryOfficialExtensions] = Field(
        default=None,
        alias="io.modelcontextprotocol.registry/official",
    )
    semantic: Optional[AgentSemanticMeta] = Field(
        default=None,
        alias="aregistry.ai/semantic",
    )
    deployments: Optional[ResourceDeploymentsMeta] = Field(
        default=None,
        alias="aregistry.ai/deployments",
    )
    #: Private fields from ``catalog_resource_metadata.data`` (not ``remotes_config``).
    metadata: Optional[Dict[str, Any]] = None


class AgentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    agent: AgentJSON
    meta: AgentResponseMeta = Field(..., alias="_meta")


class AgentListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    agents: List[AgentResponse]
    metadata: RegistryListMetadata