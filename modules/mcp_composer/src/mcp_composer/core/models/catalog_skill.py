"""Pydantic models for skill registry JSON (agentskills.io spec + agentregistry extensions)."""

from __future__ import annotations

from typing import Any

from mcp_composer.core.models.catalog_common import RegistryListMetadata, RegistryOfficialExtensions
from mcp_composer.core.utils.catalog_validators import (
    require_non_empty_after_strip,
    validate_agentskills_compatibility,
    validate_agentskills_description,
    validate_agentskills_instructions,
    validate_agentskills_name,
    validate_registry_version,
)
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SkillRepository(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    #: Optional; e.g. ``git`` when the URL is a repo. Omit when ``url`` is a generic asset location.
    source: str | None = None


class SkillCatalogReference(BaseModel):
    """URL + relative file name for a bundled artifact (same shape as ``_meta.metadata.references``)."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, str_strip_whitespace=True)

    url: str
    file: str

    @field_validator("url", "file", mode="before")
    @classmethod
    def _non_empty_ref_fields(cls, v: str, info):  # type: ignore[no-untyped-def]
        return require_non_empty_after_strip(str(v), info.field_name)


class SkillRemoteInfo(BaseModel):
    """Remote MCP server endpoint for a skill.

    ``url`` is the only field stored in the public payload (agentregistry spec parity).
    ``transport_type`` and ``headers`` are optional; when present they are stored
    in ``catalog_resource_metadata`` (``resource_id`` → ``catalog_resources.id``, JSON in ``data``)
    under ``remotes_config``, merged into ``skill.remotes`` on retrieval.
    ``remotes_config`` is not duplicated in ``SkillResponseMeta.metadata`` (response ``_meta.metadata``).
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    url: str
    transport_type: str | None = Field(default=None, alias="type")
    headers: list[dict[str, Any]] | None = None


class SkillJSON(BaseModel):
    """Skill payload aligned with the agentskills.io specification.

    Required fields (agentskills.io spec)
    --------------------------------------
    - ``name``        Max 64 chars; lowercase letters, numbers, hyphens; no leading/
                      trailing or consecutive hyphens.
    - ``description`` Max 1024 chars; non-empty; should describe what the skill does
                      *and* when to use it (trigger phrases).
    - ``version``     Specific semver string (agentregistry convention).

    Optional spec fields
    --------------------
    - ``license``       License name or reference to a bundled file.
    - ``compatibility`` Max 500 chars; environment requirements (product, packages, network).
    - ``allowed-tools`` Array of pre-approved tool names the skill may invoke.
    - ``metadata``      Arbitrary key-value map for extra properties (title, category,
                        products, tags, author, etc.).

    skill registry operational fields
    ---------------------------------
    - ``status``       One of active / draft / deprecated / deleted.
    - ``websiteUrl``   Documentation or homepage URL.
    - ``repository``   Source repository info.
    - ``references``   Bundled file references (``url`` + ``file``); aligns with ``_meta.metadata.references``.
    - ``remotes``      Remote MCP server endpoints.

    Note: skill instructions / LLM prompt content belong in ``metadata["instructions"]``
    alongside other discovery metadata (title, category, products, tags).
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True, str_strip_whitespace=True)

    # ------------------------------------------------------------------ required
    name: str
    description: str
    version: str

    # -------------------------------------------------------- agentskills.io optional
    license: str | None = None
    compatibility: str | None = None
    allowed_tools: list[str] | None = Field(default=None, alias="allowed-tools")
    metadata: dict[str, Any] | None = None

    # ------------------------------------------ agentregistry operational (optional)
    status: str | None = None
    website_url: str | None = Field(default=None, alias="websiteUrl")
    repository: SkillRepository | None = None
    references: list[SkillCatalogReference] | None = None
    remotes: list[SkillRemoteInfo] | None = None

    # ----------------------------------------------------------------- validators
    @field_validator("name", mode="before")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        return validate_agentskills_name(str(v))

    @field_validator("description", mode="before")
    @classmethod
    def _validate_description(cls, v: str) -> str:
        return validate_agentskills_description(str(v))

    @field_validator("version", mode="before")
    @classmethod
    def _validate_version(cls, v: str) -> str:
        return validate_registry_version(str(v))

    @field_validator("compatibility", mode="before")
    @classmethod
    def _validate_compatibility(cls, v: str) -> str:
        if v is None:
            return v  # type: ignore[return-value]
        return validate_agentskills_compatibility(str(v))

    @model_validator(mode="after")
    def _validate_metadata_instructions(self) -> "SkillJSON":
        """If metadata contains an 'instructions' key, enforce the 2048-char limit."""
        if self.metadata and "instructions" in self.metadata:
            instr = self.metadata["instructions"]
            if isinstance(instr, str):
                self.metadata["instructions"] = validate_agentskills_instructions(instr)
        return self


class SkillResponseMeta(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    official: RegistryOfficialExtensions | None = Field(
        default=None,
        alias="io.modelcontextprotocol.registry/official",
    )
    #: Private COS URLs, how-to-use, references, etc. from DB ``catalog_resource_metadata.data``.
    #: Serialized as ``metadata`` under ``_meta`` (distinct from ``skill.metadata``).
    #: Omitted when absent. ``remotes_config`` is never included (merged into ``skill.remotes``).
    metadata: dict[str, Any] | None = None


class SkillResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    skill: SkillJSON
    meta: SkillResponseMeta = Field(..., alias="_meta")
    # Raw source content (e.g. Markdown).  Excluded from model_dump() / JSON
    # serialisation by default so it never appears in normal API responses.
    # Populated only when the caller explicitly requests it via
    # SkillManager.get_content().
    content: str | None = Field(default=None, exclude=True)


class SkillListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    skills: list[SkillResponse]
    metadata: RegistryListMetadata


class SkillListSummaryItem(BaseModel):
    """Token-light list row: no full ``SkillJSON`` parse (used by ``SkillManager.list_summaries``)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str
    description: str
    tags: list[str] = Field(default_factory=list)
    #: From ``metadata.category`` when present (``None`` if unset).
    category: str | None = None


class SkillListSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    skills: list[SkillListSummaryItem]
    metadata: RegistryListMetadata
