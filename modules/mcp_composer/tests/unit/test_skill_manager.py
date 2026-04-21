"""Unit tests for SkillManager backed by CatalogInMemoryDatabase."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from mcp_composer.core.catalog import (
    CatalogResourceNotFoundError,
    CatalogVersionCapError,
    InvalidCatalogResourceStatusError,
)
from mcp_composer.core.catalog.catalog_manager import CatalogResourceListFilter
from mcp_composer.core.models.catalog_constants import RegistryResourceKind
from mcp_composer.core.catalog.skill_manager import SkillManager
from mcp_composer.core.models.catalog_constants import (
    RegistryResourceKind,
    VALID_CATALOG_RESOURCE_STATUSES,
)
from mcp_composer.core.models.catalog_skill import (
    SkillJSON,
    SkillListResponse,
    SkillResponse,
)
from mcp_composer.store.catalog_in_memory_database import CatalogInMemoryDatabase


# ── Helpers ───────────────────────────────────────────────────────────────────


def _skill(
    name: str = "my-skill",
    version: str = "1.0.0",
    description: str = "does stuff",
    status: str | None = None,
) -> SkillJSON:
    return SkillJSON(
        name=name,
        description=description,
        version=version,
        status=status,
    )


@pytest.fixture()
def db() -> CatalogInMemoryDatabase:
    """Fresh CatalogInMemoryDatabase instance for each test.

    initialize() and close() are no-ops on the in-memory db, so a synchronous
    fixture is sufficient and avoids pytest-asyncio fixture-mode issues.
    """
    return CatalogInMemoryDatabase()


@pytest.fixture()
def mgr(db: CatalogInMemoryDatabase) -> SkillManager:
    return SkillManager(db)


# ── publish — happy path ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_publish_returns_skill_response(mgr):
    """publish() returns a well-formed SkillResponse."""
    resp = await mgr.publish(_skill(), tenant_ids=["t1"])

    assert isinstance(resp, SkillResponse)
    assert resp.skill.name == "my-skill"
    assert resp.skill.version == "1.0.0"


@pytest.mark.asyncio
async def test_publish_sets_is_latest_true(mgr, db):
    """The row saved by publish() has is_latest=True."""
    await mgr.publish(_skill(version="1.0.0"))

    row = await db.get_resource(RegistryResourceKind.SKILL.value,"my-skill", "1.0.0")
    assert row is not None
    assert row["is_latest"] is True


@pytest.mark.asyncio
async def test_publish_meta_official_is_latest(mgr):
    """The _meta.official.is_latest flag mirrors the DB row."""
    resp = await mgr.publish(_skill(version="1.0.0"))

    assert resp.meta.official is not None
    assert resp.meta.official.is_latest is True


@pytest.mark.asyncio
async def test_publish_demotes_previous_latest(mgr, db):
    """Publishing a new version demotes the previously-latest row."""
    await mgr.publish(_skill(version="1.0.0"))
    await mgr.publish(_skill(version="2.0.0"))

    old_row = await db.get_resource(RegistryResourceKind.SKILL.value,"my-skill", "1.0.0")
    new_row = await db.get_resource(RegistryResourceKind.SKILL.value,"my-skill", "2.0.0")

    assert old_row["is_latest"] is False
    assert new_row["is_latest"] is True


@pytest.mark.asyncio
async def test_publish_older_semver_does_not_become_latest(mgr):
    """Publishing a lower version after a higher one keeps latest on the max version."""
    await mgr.publish(_skill(version="2.0.0"))
    await mgr.publish(_skill(version="1.0.0"))

    latest = await mgr.get_latest("my-skill")
    assert latest.skill.version == "2.0.0"

    row_old = await mgr.get("my-skill", "1.0.0")
    assert row_old.meta.official is not None
    assert row_old.meta.official.is_latest is False


@pytest.mark.asyncio
async def test_publish_only_one_latest_after_multiple_versions(mgr, db):
    """After publishing three versions, exactly one row has is_latest=True."""
    for ver in ("1.0.0", "2.0.0", "3.0.0"):
        await mgr.publish(_skill(version=ver))

    rows, _ = await db.list_resources(
        RegistryResourceKind.SKILL.value,
        name_like=None, is_latest_only=True,
        tenant=None, offset=0, limit=1000,
    )
    latest_for_name = [r for r in rows if r["name"] == "my-skill"]
    assert len(latest_for_name) == 1


@pytest.mark.asyncio
async def test_publish_normalises_tenant_ids(mgr, db):
    """Duplicate and empty tenant IDs are deduplicated and stripped."""
    await mgr.publish(_skill(), tenant_ids=["  t1  ", "t1", "t2", "", "  "])

    row = await db.get_resource(RegistryResourceKind.SKILL.value,"my-skill", "1.0.0")
    assert sorted(row["tenant_ids"]) == ["t1", "t2"]


@pytest.mark.asyncio
async def test_publish_no_tenant_ids(mgr, db):
    """publish() without tenant_ids stores an empty list."""
    await mgr.publish(_skill())

    row = await db.get_resource(RegistryResourceKind.SKILL.value,"my-skill", "1.0.0")
    assert row["tenant_ids"] == []


@pytest.mark.asyncio
async def test_publish_upsert_existing_version(mgr, db):
    """Re-publishing the same version updates it without incrementing the count."""
    await mgr.publish(_skill(description="v1"), tenant_ids=["t1"])
    await mgr.publish(_skill(description="v1-updated"), tenant_ids=["t2"])

    row = await db.get_resource(RegistryResourceKind.SKILL.value,"my-skill", "1.0.0")
    assert row["payload"]["description"] == "v1-updated"
    assert await db.count_resource_versions(RegistryResourceKind.SKILL.value,"my-skill") == 1


@pytest.mark.asyncio
async def test_publish_upsert_preserves_is_latest(mgr, db):
    """Re-publishing the already-latest version keeps it latest."""
    await mgr.publish(_skill(version="1.0.0"))
    await mgr.publish(_skill(version="1.0.0", description="updated"))

    row = await db.get_resource(RegistryResourceKind.SKILL.value,"my-skill", "1.0.0")
    assert row["is_latest"] is True


@pytest.mark.asyncio
async def test_publish_stores_status_in_official_meta(mgr, db):
    """When skill has an explicit status, official_meta.status matches."""
    await mgr.publish(_skill(status="deprecated"))

    row = await db.get_resource(RegistryResourceKind.SKILL.value,"my-skill", "1.0.0")
    assert row["official_meta"]["status"] == "deprecated"


@pytest.mark.asyncio
async def test_publish_default_status_is_active(mgr, db):
    """When no status is specified, official_meta.status defaults to 'active'."""
    await mgr.publish(_skill())

    row = await db.get_resource(RegistryResourceKind.SKILL.value,"my-skill", "1.0.0")
    assert row["official_meta"]["status"] == "active"


# ── publish — version cap ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_publish_raises_version_cap_error(mgr):
    """CatalogVersionCapError is raised when MAX_VERSIONS_PER_RESOURCE is exceeded."""
    cap = 3

    with patch(
        "mcp_composer.core.catalog.skill_manager.MAX_VERSIONS_PER_RESOURCE", cap
    ):
        for i in range(cap):
            await mgr.publish(_skill(version=f"{i}.0.0"))

        with pytest.raises(CatalogVersionCapError) as exc_info:
            await mgr.publish(_skill(version=f"{cap}.0.0"))

    assert exc_info.value.kind == RegistryResourceKind.SKILL.value
    assert exc_info.value.name == "my-skill"
    assert exc_info.value.count == cap


@pytest.mark.asyncio
async def test_publish_upsert_at_cap_does_not_raise(mgr):
    """Re-publishing an already-stored version at the cap does not raise."""
    cap = 2

    with patch(
        "mcp_composer.core.catalog.skill_manager.MAX_VERSIONS_PER_RESOURCE", cap
    ):
        await mgr.publish(_skill(version="1.0.0"))
        await mgr.publish(_skill(version="2.0.0"))

        # Upsert existing version — must not raise
        resp = await mgr.publish(_skill(version="2.0.0", description="updated"))

    assert resp.skill.description == "updated"


# ── get ───────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_returns_skill_response(mgr):
    """get() returns the expected SkillResponse for a stored version."""
    await mgr.publish(_skill(version="1.0.0"))
    resp = await mgr.get("my-skill", "1.0.0")

    assert isinstance(resp, SkillResponse)
    assert resp.skill.name == "my-skill"
    assert resp.skill.version == "1.0.0"


@pytest.mark.asyncio
async def test_get_not_found_raises(mgr):
    """get() raises CatalogResourceNotFoundError when the version does not exist."""
    with pytest.raises(CatalogResourceNotFoundError) as exc_info:
        await mgr.get("ghost", "9.9.9")

    assert exc_info.value.kind == RegistryResourceKind.SKILL.value
    assert exc_info.value.name == "ghost"
    assert exc_info.value.version == "9.9.9"


@pytest.mark.asyncio
async def test_get_specific_version(mgr):
    """get() retrieves the exact version requested, not the latest."""
    await mgr.publish(_skill(version="1.0.0", description="first"))
    await mgr.publish(_skill(version="2.0.0", description="second"))

    resp = await mgr.get("my-skill", "1.0.0")
    assert resp.skill.description == "first"


# ── get_latest ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_latest_returns_latest_version(mgr):
    """get_latest() returns the is_latest=True version."""
    await mgr.publish(_skill(version="1.0.0"))
    await mgr.publish(_skill(version="2.0.0"))

    resp = await mgr.get_latest("my-skill")
    assert resp.skill.version == "2.0.0"
    assert resp.meta.official.is_latest is True


@pytest.mark.asyncio
async def test_get_latest_not_found_raises(mgr):
    """get_latest() raises CatalogResourceNotFoundError when no skill exists."""
    with pytest.raises(CatalogResourceNotFoundError) as exc_info:
        await mgr.get_latest("nonexistent")

    assert exc_info.value.kind == RegistryResourceKind.SKILL.value
    assert exc_info.value.name == "nonexistent"
    assert exc_info.value.version == "latest"


@pytest.mark.asyncio
async def test_get_latest_returns_highest_semantic_version(mgr):
    """get_latest() returns the greatest version (PEP 440), not last publish time."""
    await mgr.publish(_skill(version="1.0.0"))
    await mgr.publish(_skill(version="3.0.0"))
    await mgr.publish(_skill(version="2.0.0"))  # published last, but lower than 3.0.0

    resp = await mgr.get_latest("my-skill")
    assert resp.skill.version == "3.0.0"


# ── list ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_returns_skill_list_response(mgr):
    """list() returns a SkillListResponse."""
    await mgr.publish(_skill(version="1.0.0"))
    result = await mgr.list(CatalogResourceListFilter(kind=RegistryResourceKind.SKILL))

    assert isinstance(result, SkillListResponse)


@pytest.mark.asyncio
async def test_list_empty_store(mgr):
    """list() on an empty store returns zero items and no cursor."""
    result = await mgr.list(CatalogResourceListFilter(kind=RegistryResourceKind.SKILL))

    assert result.skills == []
    assert result.metadata.count == 0
    assert result.metadata.next_cursor is None


@pytest.mark.asyncio
async def test_list_all_versions(mgr):
    """list() with no filters returns every stored version."""
    await mgr.publish(_skill(version="1.0.0"))
    await mgr.publish(_skill(version="2.0.0"))
    await mgr.publish(_skill(name="other-skill", version="1.0.0"))

    result = await mgr.list(CatalogResourceListFilter(kind=RegistryResourceKind.SKILL))
    assert result.metadata.count == 3


@pytest.mark.asyncio
async def test_list_is_latest_only(mgr):
    """is_latest_only=True returns only the latest version per skill name."""
    await mgr.publish(_skill(version="1.0.0"))
    await mgr.publish(_skill(version="2.0.0"))
    await mgr.publish(_skill(name="other-skill", version="1.0.0"))

    result = await mgr.list(CatalogResourceListFilter(kind=RegistryResourceKind.SKILL, is_latest_only=True))
    assert result.metadata.count == 2
    assert all(r.meta.official.is_latest for r in result.skills)


@pytest.mark.asyncio
async def test_list_name_like_filter(mgr):
    """name_like restricts results to skills whose name contains the substring."""
    await mgr.publish(_skill(name="foo-bar", version="1.0.0"))
    await mgr.publish(_skill(name="baz-qux", version="1.0.0"))

    result = await mgr.list(CatalogResourceListFilter(kind=RegistryResourceKind.SKILL, name_like="foo"))
    assert result.metadata.count == 1
    assert result.skills[0].skill.name == "foo-bar"


@pytest.mark.asyncio
async def test_list_tenant_filter(mgr):
    """tenant filter restricts results to skills accessible by that tenant."""
    await mgr.publish(_skill(name="skill-a", version="1.0.0"), tenant_ids=["team-1"])
    await mgr.publish(_skill(name="skill-b", version="1.0.0"), tenant_ids=["team-2"])

    result = await mgr.list(CatalogResourceListFilter(kind=RegistryResourceKind.SKILL, tenant="team-1"))
    assert result.metadata.count == 1
    assert result.skills[0].skill.name == "skill-a"


@pytest.mark.asyncio
async def test_list_pagination(mgr):
    """Cursor-based pagination splits results across two pages."""
    for i in range(5):
        await mgr.publish(_skill(name=f"skill-{i:02d}", version="1.0.0"))

    page1 = await mgr.list(CatalogResourceListFilter(kind=RegistryResourceKind.SKILL, limit=3))
    assert page1.metadata.count == 3
    assert page1.metadata.next_start == 3

    page2 = await mgr.list(CatalogResourceListFilter(
            kind=RegistryResourceKind.SKILL, limit=3, start=page1.metadata.next_start
        ))
    assert page2.metadata.count == 2
    assert page2.metadata.next_start is None


@pytest.mark.asyncio
async def test_list_metadata_count_matches_items(mgr):
    """metadata.count equals the number of items in the skills list."""
    for i in range(4):
        await mgr.publish(_skill(name=f"skill-{i}", version="1.0.0"))

    result = await mgr.list(CatalogResourceListFilter(kind=RegistryResourceKind.SKILL))
    assert result.metadata.count == len(result.skills)


# ── delete ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_removes_skill(mgr, db):
    """delete() removes the row so subsequent get() raises CatalogResourceNotFoundError."""
    await mgr.publish(_skill(version="1.0.0"))
    await mgr.delete("my-skill", "1.0.0")

    with pytest.raises(CatalogResourceNotFoundError):
        await mgr.get("my-skill", "1.0.0")


@pytest.mark.asyncio
async def test_delete_not_found_raises(mgr):
    """delete() raises CatalogResourceNotFoundError when the row does not exist."""
    with pytest.raises(CatalogResourceNotFoundError):
        await mgr.delete("ghost", "9.9.9")


@pytest.mark.asyncio
async def test_delete_latest_promotes_next(mgr, db):
    """Deleting the is_latest version promotes the next-most-recent version."""
    await mgr.publish(_skill(version="1.0.0"))
    await mgr.publish(_skill(version="2.0.0"))

    await mgr.delete("my-skill", "2.0.0")

    row = await db.get_resource(RegistryResourceKind.SKILL.value,"my-skill", "1.0.0")
    assert row is not None
    assert row["is_latest"] is True


@pytest.mark.asyncio
async def test_delete_latest_with_multiple_remaining_promotes_highest_version(mgr, db):
    """After deleting the latest row, the greatest remaining version becomes latest."""
    await mgr.publish(_skill(version="1.0.0"))
    await mgr.publish(_skill(version="2.0.0"))
    await mgr.publish(_skill(version="3.0.0"))

    await mgr.delete("my-skill", "3.0.0")

    latest_resp = await mgr.get_latest("my-skill")
    assert latest_resp.skill.version == "2.0.0"


@pytest.mark.asyncio
async def test_delete_non_latest_no_promotion(mgr, db):
    """Deleting a non-latest version does not change is_latest on other rows."""
    await mgr.publish(_skill(version="1.0.0"))
    await mgr.publish(_skill(version="2.0.0"))

    await mgr.delete("my-skill", "1.0.0")

    latest = await db.get_resource(RegistryResourceKind.SKILL.value,"my-skill", "2.0.0")
    assert latest["is_latest"] is True


@pytest.mark.asyncio
async def test_delete_only_version_leaves_no_latest(mgr, db):
    """Deleting the sole version leaves no remaining rows for that name."""
    await mgr.publish(_skill(version="1.0.0"))
    await mgr.delete("my-skill", "1.0.0")

    rows, _ = await db.list_resources(
        RegistryResourceKind.SKILL.value,
        name_like=None,
        is_latest_only=False,
        tenant=None,
        offset=0,
        limit=100,
    )
    remaining = [r for r in rows if r["name"] == "my-skill"]
    assert remaining == []


@pytest.mark.asyncio
async def test_delete_does_not_affect_other_skills(mgr, db):
    """Deleting a skill version does not touch rows for other skill names."""
    await mgr.publish(_skill(name="skill-a", version="1.0.0"))
    await mgr.publish(_skill(name="skill-b", version="1.0.0"))

    await mgr.delete("skill-a", "1.0.0")

    row = await db.get_resource(RegistryResourceKind.SKILL.value,"skill-b", "1.0.0")
    assert row is not None
    assert row["is_latest"] is True


# ── update_status ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_status_valid(mgr, db):
    """update_status() writes the new status to both payload and official_meta."""
    await mgr.publish(_skill(status="active"))
    await mgr.update_status("my-skill", "1.0.0", "deprecated")

    row = await db.get_resource(RegistryResourceKind.SKILL.value,"my-skill", "1.0.0")
    assert row["payload"]["status"] == "deprecated"
    assert row["official_meta"]["status"] == "deprecated"


@pytest.mark.asyncio
async def test_update_status_all_valid_values(mgr):
    """Every value in VALID_CATALOG_RESOURCE_STATUSES is accepted without raising."""
    for idx, status in enumerate(sorted(VALID_CATALOG_RESOURCE_STATUSES)):
        await mgr.publish(_skill(name=f"skill-{idx}", version="1.0.0"))
        # Should not raise
        await mgr.update_status(f"skill-{idx}", "1.0.0", status)


@pytest.mark.asyncio
async def test_update_status_invalid_raises(mgr):
    """update_status() raises InvalidCatalogResourceStatusError for an unknown status."""
    await mgr.publish(_skill())

    with pytest.raises(InvalidCatalogResourceStatusError) as exc_info:
        await mgr.update_status("my-skill", "1.0.0", "unknown-state")

    assert exc_info.value.kind == RegistryResourceKind.SKILL.value
    assert exc_info.value.status == "unknown-state"


@pytest.mark.asyncio
async def test_update_status_validation_before_db_lookup(mgr):
    """InvalidCatalogResourceStatusError is raised even when the skill does not exist."""
    with pytest.raises(InvalidCatalogResourceStatusError):
        await mgr.update_status("ghost", "9.9.9", "invalid")


@pytest.mark.asyncio
async def test_update_status_not_found_raises(mgr):
    """CatalogResourceNotFoundError is raised when the skill does not exist."""
    with pytest.raises(CatalogResourceNotFoundError):
        await mgr.update_status("ghost", "9.9.9", "active")


@pytest.mark.asyncio
async def test_update_status_reflected_in_get(mgr):
    """The status change is visible through get()."""
    await mgr.publish(_skill(status="draft"))
    await mgr.update_status("my-skill", "1.0.0", "deprecated")

    resp = await mgr.get("my-skill", "1.0.0")
    assert resp.skill.status == "deprecated"


# ── round-trip integrity ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_publish_get_roundtrip(mgr):
    """A published skill can be retrieved with all fields intact."""
    skill_in = _skill(name="round-trip", version="0.9.0", description="round trip test")
    await mgr.publish(skill_in, tenant_ids=["org-a"])

    resp = await mgr.get("round-trip", "0.9.0")
    assert resp.skill.name == "round-trip"
    assert resp.skill.version == "0.9.0"
    assert resp.skill.description == "round trip test"


@pytest.mark.asyncio
async def test_publish_sets_official_timestamps(mgr):
    """The official extension contains non-None published_at and updated_at."""
    resp = await mgr.publish(_skill())

    assert resp.meta.official is not None
    assert resp.meta.official.published_at is not None
    assert resp.meta.official.updated_at is not None


@pytest.mark.asyncio
async def test_list_items_are_valid_skill_responses(mgr):
    """Every item returned by list() is a properly-typed SkillResponse."""
    for i in range(3):
        await mgr.publish(_skill(name=f"s{i}", version="1.0.0"))

    result = await mgr.list(CatalogResourceListFilter(kind=RegistryResourceKind.SKILL))
    for item in result.skills:
        assert isinstance(item, SkillResponse)
        assert item.meta.official is not None