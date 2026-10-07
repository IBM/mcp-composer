"""Tests for skill catalog MCP ``list_skills`` response shaping."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from mcp_composer.core.catalog.skill_manager import _row_to_list_summary_item
from mcp_composer.core.models.catalog_common import RegistryListMetadata, RegistryOfficialExtensions
from mcp_composer.core.models.catalog_skill import (
    SkillJSON,
    SkillListResponse,
    SkillListSummaryItem,
    SkillListSummaryResponse,
    SkillResponse,
    SkillResponseMeta,
)
from mcp_composer.core.tools.catalog import skill_catalog_mcp as scm


def _official() -> RegistryOfficialExtensions:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return RegistryOfficialExtensions(
        status="active",
        publishedAt=now,
        updatedAt=now,
        isLatest=True,
    )


def _response_with_tags(tags: list[str] | None) -> SkillResponse:
    meta = {"tags": tags} if tags is not None else None
    return SkillResponse(
        skill=SkillJSON(
            name="test-skill",
            description="A test skill for list shaping.",
            version="1.0.0",
            metadata=meta,
        ),
        _meta=SkillResponseMeta(official=_official()),
    )


def test_row_to_list_summary_item_from_db_row() -> None:
    row = {
        "name": "test-skill",
        "payload": {
            "name": "test-skill",
            "description": "A test skill for list shaping.",
            "version": "1.0.0",
            "metadata": {"tags": ["a", "b"], "category": "observability"},
        },
    }
    item = _row_to_list_summary_item(row)
    assert item.name == "test-skill"
    assert item.description == "A test skill for list shaping."
    assert item.tags == ["a", "b"]
    assert item.category == "observability"


def test_row_to_list_summary_item_empty_tags_when_missing() -> None:
    row = {
        "name": "test-skill",
        "payload": {
            "name": "test-skill",
            "description": "d",
            "version": "1.0.0",
        },
    }
    item = _row_to_list_summary_item(row)
    assert item.tags == []
    assert item.category is None


@pytest.mark.asyncio
async def test_list_skills_verbose_false_uses_list_summaries() -> None:
    compact = SkillListSummaryResponse(
        skills=[
            SkillListSummaryItem(
                name="test-skill",
                description="A test skill for list shaping.",
                tags=["x"],
                category=None,
            )
        ],
        metadata=RegistryListMetadata(count=1, nextStart=None),
    )
    with patch.object(scm, "_skill_manager") as mock_mgr:
        mock_mgr.list_summaries = AsyncMock(return_value=compact)
        out = await scm.list_skills(verbose=False)

    mock_mgr.list_summaries.assert_awaited_once()
    mock_mgr.list.assert_not_called()
    assert out["metadata"] == {"count": 1, "next_start": None}
    assert out["skills"] == [
        {
            "name": "test-skill",
            "description": "A test skill for list shaping.",
            "tags": ["x"],
            "category": None,
        }
    ]


@pytest.mark.asyncio
async def test_list_skills_verbose_true_uses_list() -> None:
    listing = SkillListResponse(
        skills=[_response_with_tags(["x"])],
        metadata=RegistryListMetadata(count=1, nextStart=10),
    )
    with patch.object(scm, "_skill_manager") as mock_mgr:
        mock_mgr.list = AsyncMock(return_value=listing)
        out = await scm.list_skills(verbose=True)

    mock_mgr.list.assert_awaited_once()
    mock_mgr.list_summaries.assert_not_called()
    assert out["metadata"]["count"] == 1
    assert out["metadata"]["next_start"] == 10
    assert len(out["skills"]) == 1
    row = out["skills"][0]
    assert "skill" in row and "_meta" in row
    assert row["skill"]["name"] == "test-skill"
    assert row["skill"]["version"] == "1.0.0"


@pytest.mark.asyncio
async def test_list_skills_layered_index_calls_list_skill_categories(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MCP_SKILL_CATALOG_LAYERED", "true")
    with patch.object(scm, "_skill_manager") as mock_mgr:
        mock_mgr.list_skill_categories = AsyncMock(
            return_value=[
                {"name": "alpha", "skill_count": 2},
                {"name": "(uncategorized)", "skill_count": 1},
            ]
        )
        out = await scm.list_skills()

    mock_mgr.list_skill_categories.assert_awaited_once_with(keywords=None, tenant=None)
    mock_mgr.list_summaries.assert_not_called()
    assert out["layered"] is True
    assert out["categories"] == [
        {"name": "alpha", "skill_count": 2},
        {"name": "(uncategorized)", "skill_count": 1},
    ]
    assert out["skills"] == []
    assert out["metadata"] == {"count": 2, "next_start": None}


@pytest.mark.asyncio
async def test_list_skills_layered_second_hop_passes_category_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MCP_SKILL_CATALOG_LAYERED", "true")
    compact = SkillListSummaryResponse(
        skills=[
            SkillListSummaryItem(
                name="s1",
                description="d",
                tags=[],
                category="alpha",
            )
        ],
        metadata=RegistryListMetadata(count=1, nextStart=None),
    )
    with patch.object(scm, "_skill_manager") as mock_mgr:
        mock_mgr.list_summaries = AsyncMock(return_value=compact)
        out = await scm.list_skills(category="alpha")

    mock_mgr.list_skill_categories.assert_not_called()
    fltr = mock_mgr.list_summaries.await_args.args[0]
    assert fltr.category == "alpha"
    assert out["layered"] is True
    assert out["skills"][0]["category"] == "alpha"


def test_skill_catalog_server_instructions_core_flow() -> None:
    """Server instructions stay aligned with list → get_skill → references → act."""
    text = scm.catalog_mcp.instructions or ""
    assert "Main tools:" in text
    assert "1. **list_skills**" in text
    assert "2. **get_skill**" in text
    assert "3. **load_skill_reference**" in text
    assert "Usage workflow:" in text
    assert "MCP_SKILL_CATALOG_LAYERED" in text
    assert "4. **add_skill**" not in text


@pytest.mark.asyncio
async def test_skill_catalog_workflow_guide_flat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MCP_SKILL_CATALOG_LAYERED", raising=False)
    guide = await scm.get_skill_catalog_workflow_guide()
    assert guide["pattern"] == "discover_load_references_apply"
    assert guide["layered_catalog_discovery"] is False
    assert len(guide["steps"]) == 4
    assert guide["steps"][0]["tool"] == "list_skills"
    assert guide["steps"][1]["tool"] == "get_skill"
    assert "Flat:" in guide["steps"][0]["summary"]


@pytest.mark.asyncio
async def test_skill_catalog_workflow_guide_layered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MCP_SKILL_CATALOG_LAYERED", "true")
    guide = await scm.get_skill_catalog_workflow_guide()
    assert guide["layered_catalog_discovery"] is True
    assert "Layered:" in guide["steps"][0]["summary"]
