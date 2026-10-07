"""Pydantic models for agent registry JSON (agentregistry pkg/models/agent + manifest)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from mcp_composer.core.models.catalog_common import (
    RegistryListMetadata,
    RegistryOfficialExtensions,
)
from mcp_composer.core.models.catalog_skill import SkillCatalogReference
from mcp_composer.core.utils.catalog_validators import (
    require_non_empty_after_strip,
    validate_registry_version,
)
from pydantic import BaseModel, ConfigDict, Field, field_validator


class AgentRegistryRepository(BaseModel):
    """MCP registry repository object on agent JSON (model.Repository)."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    url: str | None = None
    source: str | None = None
    id: str | None = None
    subfolder: str | None = None


class AgentRegistryTransport(BaseModel):
    """MCP registry transport on agent remotes (model.Transport); headers may be rich objects."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    transport_type: str = Field(..., alias="type")
    url: str | None = None
    headers: list[dict[str, Any]] | None = None


class AgentSemanticMeta(BaseModel):
    """`aregistry.ai/semantic` fragment."""

    model_config = ConfigDict(extra="forbid")

    score: float


class DeploymentSummary(BaseModel):
    """Compact deployment row embedded in catalog _meta."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str
    provider_id: str | None = Field(default=None, alias="providerId")
    status: str
    origin: str
    version: str | None = None
    deployed_at: datetime = Field(alias="deployedAt")
    updated_at: datetime = Field(alias="updatedAt")


class ResourceDeploymentsMeta(BaseModel):
    """`registry.ai/deployments` fragment."""

    model_config = ConfigDict(extra="forbid")

    deployments: list[DeploymentSummary]
    count: int


class SkillRef(BaseModel):
    model_config = ConfigDict(
        extra="forbid", populate_by_name=True, str_strip_whitespace=True
    )

    name: str
    image: str | None = None
    registry_url: str | None = Field(default=None, alias="registryURL")
    registry_skill_name: str | None = Field(default=None, alias="registrySkillName")
    registry_skill_version: str | None = Field(
        default=None, alias="registrySkillVersion"
    )


class PromptRef(BaseModel):
    model_config = ConfigDict(
        extra="forbid", populate_by_name=True, str_strip_whitespace=True
    )

    name: str
    registry_url: str | None = Field(default=None, alias="registryURL")
    registry_prompt_name: str | None = Field(default=None, alias="registryPromptName")
    registry_prompt_version: str | None = Field(
        default=None, alias="registryPromptVersion"
    )


class McpServerType(BaseModel):
    model_config = ConfigDict(
        extra="forbid", populate_by_name=True, str_strip_whitespace=True
    )

    server_type: str = Field(..., alias="type")
    name: str
    image: str | None = None
    build: str | None = None
    command: str | None = None
    args: list[str] | None = None
    env: list[str] | None = None
    url: str | None = None
    headers: dict[str, str] | None = None
    registry_url: str | None = Field(default=None, alias="registryURL")
    registry_server_name: str | None = Field(default=None, alias="registryServerName")
    registry_server_version: str | None = Field(
        default=None, alias="registryServerVersion"
    )
    registry_server_prefer_remote: bool | None = Field(
        default=None, alias="registryServerPreferRemote"
    )


class AgentJSON(BaseModel):
    """Flattened agent payload: manifest fields plus A2A agent card fields.

    Designed for A2A agents whose metadata comes from the well-known agent card
    (``/.well-known/agent-card.json``).  Only ``name``, ``description``, and ``version``
    are required — all are sourced from the agent card at registration time.

    A2A agent card fields (``url``_, ``capabilities``, ``defaultInputModes``, etc.) are
    mapped directly from the well-known response and stored alongside the catalog fields.
    ``extra="ignore"`` allows unknown agent card fields to pass through without error.
    """

    model_config = ConfigDict(
        extra="ignore", populate_by_name=True, str_strip_whitespace=True
    )

    # ── required catalog fields ────────────────────────────────────────────────
    name: str
    description: str
    version: str

    # ── A2A agent card fields (all optional — sourced from well-known endpoint) ─
    url: str | None = None
    capabilities: dict[str, Any] | None = None
    default_input_modes: list[str] | None = Field(
        default=None, alias="defaultInputModes"
    )
    default_output_modes: list[str] | None = Field(
        default=None, alias="defaultOutputModes"
    )
    preferred_transport: str | None = Field(default=None, alias="preferredTransport")
    protocol_version: str | None = Field(default=None, alias="protocolVersion")
    provider: dict[str, Any] | None = None
    # A2A skills — raw dicts from the agent card (distinct from catalog SkillRef cross-links)
    a2a_skills: list[dict[str, Any]] | None = Field(default=None, alias="skills")

    # ── catalog registry fields ────────────────────────────────────────────────
    telemetry_endpoint: str | None = Field(default=None, alias="telemetryEndpoint")
    mcp_servers: list[McpServerType] | None = Field(default=None, alias="mcpServers")
    catalog_skill_refs: list[SkillRef] | None = Field(default=None, alias="skillRefs")
    prompts: list[PromptRef] | None = None
    updated_at: datetime | None = Field(default=None, alias="updatedAt")
    title: str | None = None
    status: str | None = None
    website_url: str | None = Field(default=None, alias="websiteUrl")
    repository: AgentRegistryRepository | None = None
    references: list[SkillCatalogReference] | None = None
    remotes: list[AgentRegistryTransport] | None = None

    @field_validator("name", mode="before")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        # A2A agent names come from external agent cards and may contain spaces,
        # hyphens, or other characters — only require non-empty after strip.
        return require_non_empty_after_strip(str(v), "name")

    @field_validator("description", mode="before")
    @classmethod
    def _validate_description(cls, v: str) -> str:
        return require_non_empty_after_strip(str(v), "description")

    @field_validator("version", mode="before")
    @classmethod
    def _validate_version(cls, v: str) -> str:
        return validate_registry_version(str(v))


class AgentResponseMeta(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    official: RegistryOfficialExtensions | None = Field(
        default=None,
        alias="io.modelcontextprotocol.registry/official",
    )
    semantic: AgentSemanticMeta | None = Field(
        default=None,
        alias="aregistry.ai/semantic",
    )
    deployments: ResourceDeploymentsMeta | None = Field(
        default=None,
        alias="aregistry.ai/deployments",
    )
    #: Private fields from ``catalog_resource_metadata.data`` (not ``remotes_config``).
    metadata: dict[str, Any] | None = None


class AgentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    agent: AgentJSON
    meta: AgentResponseMeta = Field(..., alias="_meta")


class AgentListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    agents: list[AgentResponse]
    metadata: RegistryListMetadata
