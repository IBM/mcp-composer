"""Pydantic models for prompt registry JSON (agentregistry pkg/models/prompt)."""

from __future__ import annotations

from mcp_composer.core.models.catalog_common import RegistryListMetadata, RegistryOfficialExtensions
from mcp_composer.core.utils.catalog_validators import (
    require_non_empty_after_strip,
    validate_registry_version,
    validate_skill_or_prompt_name,
)
from pydantic import BaseModel, ConfigDict, Field, field_validator


class PromptJSON(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, str_strip_whitespace=True)

    name: str
    description: str | None = None
    version: str
    content: str

    @field_validator("name", mode="before")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        return validate_skill_or_prompt_name(str(v))

    @field_validator("content", mode="before")
    @classmethod
    def _validate_content(cls, v: str) -> str:
        return require_non_empty_after_strip(str(v), "content")

    @field_validator("version", mode="before")
    @classmethod
    def _validate_version(cls, v: str) -> str:
        return validate_registry_version(str(v))


class PromptResponseMeta(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    official: RegistryOfficialExtensions | None = Field(
        default=None,
        alias="io.modelcontextprotocol.registry/official",
    )


class PromptResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    prompt: PromptJSON
    meta: PromptResponseMeta = Field(..., alias="_meta")


class PromptListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    prompts: list[PromptResponse]
    metadata: RegistryListMetadata
