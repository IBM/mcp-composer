"""Pydantic models for workflow catalog entries (catalog_resource kind ``workflow``)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from mcp_composer.core.models.catalog_common import (
    RegistryListMetadata,
    RegistryOfficialExtensions,
)
from mcp_composer.core.utils.catalog_validators import (
    require_non_empty_after_strip,
    validate_registry_version,
    validate_skill_or_prompt_name,
)


class WorkflowStep(BaseModel):
    """One ordered step in a workflow (tool invocation and optional expected behaviour)."""

    model_config = ConfigDict(
        extra="forbid", populate_by_name=True, str_strip_whitespace=True
    )

    step: int = Field(ge=1)
    toolname: str
    tool: str
    input: dict[str, Any] = Field(default_factory=dict)
    #: Optional human-readable description of desired output or behaviour for this step.
    expected_behaviour: str | None = None

    @field_validator("toolname", "tool", mode="before")
    @classmethod
    def _non_empty_tool_fields(cls, v: str, info):  # type: ignore[no-untyped-def]
        return require_non_empty_after_strip(str(v), info.field_name)


class WorkflowJSON(BaseModel):
    """Workflow payload published under ``catalog_resources`` with ``kind`` = ``workflow``."""

    model_config = ConfigDict(
        extra="forbid", populate_by_name=True, str_strip_whitespace=True
    )

    name: str
    description: str
    version: str
    goal: str
    steps: list[WorkflowStep]
    status: str | None = None

    @field_validator("name", mode="before")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        return validate_skill_or_prompt_name(str(v))

    @field_validator("description", "goal", mode="before")
    @classmethod
    def _non_empty_strings(cls, v: str, info):  # type: ignore[no-untyped-def]
        return require_non_empty_after_strip(str(v), info.field_name)

    @field_validator("version", mode="before")
    @classmethod
    def _validate_version(cls, v: str) -> str:
        return validate_registry_version(str(v))


class WorkflowResponseMeta(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    official: RegistryOfficialExtensions | None = Field(
        default=None,
        alias="io.modelcontextprotocol.registry/official",
    )
    metadata: dict[str, Any] | None = None


class WorkflowResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    workflow: WorkflowJSON
    meta: WorkflowResponseMeta = Field(..., alias="_meta")


class WorkflowListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    workflows: list[WorkflowResponse]
    metadata: RegistryListMetadata
