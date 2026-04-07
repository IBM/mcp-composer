"""Shared Pydantic types for agentregistry-aligned list and _meta payloads.

Only types used by **more than one** resource kind (skill, prompt, agent) live here.
Agent-only supporting models live in catalog_agent.py.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class RegistryOfficialExtensions(BaseModel):
    """`io.modelcontextprotocol.registry/official` extension (skill / agent / prompt)."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    status: str
    published_at: datetime = Field(alias="publishedAt")
    updated_at: datetime = Field(alias="updatedAt")
    is_latest: bool = Field(alias="isLatest")


class RegistryListMetadata(BaseModel):
    """Pagination metadata for skill / agent / prompt list responses."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    next_cursor: Optional[str] = Field(default=None, alias="nextCursor")
    next_start: Optional[int] = Field(default=None, alias="nextStart")
    count: int