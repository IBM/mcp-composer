"""Unit tests for AgentManager backed by CatalogInMemoryDatabase."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from mcp_composer.core.catalog import CatalogResourceNotFoundError, CatalogVersionCapError
from mcp_composer.core.catalog.agent_manager import AgentManager
from mcp_composer.core.catalog.catalog_manager import CatalogResourceListFilter
from mcp_composer.core.models.catalog_agent import AgentJSON
from mcp_composer.core.models.catalog_constants import RegistryResourceKind
from mcp_composer.store.catalog_in_memory_database import CatalogInMemoryDatabase


def _agent(
    name: str = "MyAgent",
    version: str = "1.0.0",
    description: str = "does things",
) -> AgentJSON:
    return AgentJSON(
        name=name,
        description=description,
        version=version,
    )


@pytest.fixture()
def db() -> CatalogInMemoryDatabase:
    return CatalogInMemoryDatabase()


@pytest.fixture()
def mgr(db: CatalogInMemoryDatabase) -> AgentManager:
    return AgentManager(db)


@pytest.mark.asyncio
async def test_publish_returns_agent_response(mgr):
    resp = await mgr.publish(_agent(), tenant_ids=["t1"])
    assert resp.agent.name == "MyAgent"
    assert resp.agent.version == "1.0.0"
    assert resp.meta.official is not None
    assert resp.meta.official.is_latest is True


@pytest.mark.asyncio
async def test_publish_second_version_demotes_first(mgr, db):
    await mgr.publish(_agent(version="1.0.0"))
    await mgr.publish(_agent(version="2.0.0"))
    old = await db.get_resource("agent", "MyAgent", "1.0.0")
    new = await db.get_resource("agent", "MyAgent", "2.0.0")
    assert old is not None and old["is_latest"] is False
    assert new is not None and new["is_latest"] is True


@pytest.mark.asyncio
async def test_get_latest(mgr):
    await mgr.publish(_agent(version="1.0.0"))
    await mgr.publish(_agent(version="2.0.0"))
    r = await mgr.get_latest("MyAgent")
    assert r.agent.version == "2.0.0"


@pytest.mark.asyncio
async def test_list_active_latest(mgr):
    await mgr.publish(_agent(version="1.0.0"))
    out = await mgr.list(
        CatalogResourceListFilter(
            kind=RegistryResourceKind.AGENT,
            is_latest_only=True,
            status_filter="active",
            start=0,
            limit=50,
        )
    )
    assert len(out.agents) == 1


@pytest.mark.asyncio
async def test_delete_promotes_previous(mgr):
    await mgr.publish(_agent(version="1.0.0"))
    await mgr.publish(_agent(version="2.0.0"))
    await mgr.delete("MyAgent", "2.0.0")
    r = await mgr.get_latest("MyAgent")
    assert r.agent.version == "1.0.0"


@pytest.mark.asyncio
async def test_version_cap(mgr, db):
    # Test with a smaller number to avoid timeout - the actual cap is enforced by the constant
    # We just need to verify the cap mechanism works, not test with the full 10000 versions
    test_cap = 50  # Use a reasonable number for testing

    # Mock the constant where it's used in agent_manager
    with patch("mcp_composer.core.catalog.agent_manager.MAX_VERSIONS_PER_RESOURCE", test_cap):
        for i in range(test_cap):
            await mgr.publish(_agent(name="CapAgent", version=f"{i}.0.0"))
        with pytest.raises(CatalogVersionCapError):
            await mgr.publish(_agent(name="CapAgent", version="99999.0.0"))


@pytest.mark.asyncio
async def test_get_missing_raises(mgr):
    with pytest.raises(CatalogResourceNotFoundError):
        await mgr.get("Nope", "1.0.0")


# ---------------------------------------------------------------------------
# Tests for AgentManager.create() — create-only semantics
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_success(mgr):
    """create() on a new name+version returns a valid AgentResponse."""
    resp = await mgr.create(_agent(), tenant_ids=["t1"])
    assert resp.agent.name == "MyAgent"
    assert resp.agent.version == "1.0.0"
    assert resp.meta.official is not None
    assert resp.meta.official.is_latest is True


@pytest.mark.asyncio
async def test_create_duplicate_raises(mgr):
    """create() with the same name+version raises CatalogResourceAlreadyExistsError."""
    from mcp_composer.core.catalog import CatalogResourceAlreadyExistsError

    await mgr.create(_agent())
    with pytest.raises(CatalogResourceAlreadyExistsError) as exc_info:
        await mgr.create(_agent())
    assert "MyAgent@1.0.0" in str(exc_info.value)


@pytest.mark.asyncio
async def test_create_and_publish_coexist(mgr):
    """create() for a new version succeeds; publish() on the same version afterwards upserts."""
    resp_create = await mgr.create(_agent(version="1.0.0"))
    assert resp_create.agent.version == "1.0.0"

    # publish() is an upsert — should not raise even though the version exists
    resp_publish = await mgr.publish(_agent(version="1.0.0"))
    assert resp_publish.agent.version == "1.0.0"

    # Publishing a second version via publish() should still work
    resp_v2 = await mgr.publish(_agent(version="2.0.0"))
    assert resp_v2.agent.version == "2.0.0"
    assert resp_v2.meta.official is not None
    assert resp_v2.meta.official.is_latest is True


# ---------------------------------------------------------------------------
# Regression test: _list_agents_from_store must exclude deleted agents
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_agents_from_store_excludes_deleted(mgr):
    """AgentManager.list with status_filter=active must not return deleted agents.

    Regression for the bug where CatalogResourceListFilter was built without
    status_filter="active", causing deleted agents to appear in list_agents().
    """
    from mcp_composer.core.catalog.catalog_manager import CatalogResourceListFilter
    from mcp_composer.core.models.catalog_constants import RegistryResourceKind

    await mgr.publish(_agent(name="ActiveAgent", version="1.0.0"))
    await mgr.publish(_agent(name="DeletedAgent", version="1.0.0"))
    await mgr.update_status("DeletedAgent", "1.0.0", "deleted")

    filt = CatalogResourceListFilter(
        kind=RegistryResourceKind.AGENT,
        is_latest_only=True,
        status_filter="active",
        limit=200,
    )
    response = await mgr.list(filt)
    names = [r.agent.name for r in response.agents]
    assert "ActiveAgent" in names, "Active agent must appear in list"
    assert "DeletedAgent" not in names, "Deleted agent must be excluded from list"


# ---------------------------------------------------------------------------
# Regression tests: re-registration of deleted agents
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_deleted_agent_allows_reregistration(mgr):
    """create() on a deleted name+version must succeed and restore status to active."""

    await mgr.create(_agent())
    await mgr.update_status("MyAgent", "1.0.0", "deleted")

    # Re-registration of a deleted agent must not raise.
    resp = await mgr.create(_agent())
    assert resp.agent.name == "MyAgent"
    assert resp.agent.version == "1.0.0"
    # Status must be reset to active.
    assert resp.meta.official is not None
    assert resp.meta.official.status == "active"


@pytest.mark.asyncio
async def test_create_active_agent_still_raises(mgr):
    """create() on an active name+version must still raise CatalogResourceAlreadyExistsError."""
    from mcp_composer.core.catalog import CatalogResourceAlreadyExistsError

    await mgr.create(_agent())
    with pytest.raises(CatalogResourceAlreadyExistsError) as exc_info:
        await mgr.create(_agent())
    assert "MyAgent@1.0.0" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Regression tests: publish() always forces status="active"
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_publish_always_stores_active_status(mgr, db):
    """publish() must always store status='active' regardless of agent_json.status.

    Regression: if an agent card carries status='deleted' (from a well-known endpoint),
    publish() must NOT persist that value — registration always results in an active entry.
    """
    # Attempt to publish an agent whose status field is "deleted" (e.g. from a stale card).
    deleted_agent = AgentJSON(
        name="StatusTestAgent",
        description="should always be active",
        version="1.0.0",
        status="deleted",
    )
    resp = await mgr.publish(deleted_agent)
    # The response must reflect the forced "active" status.
    assert resp.meta.official is not None
    assert resp.meta.official.status == "active"
    # Verify the DB row directly.
    row = await db.get_resource("agent", "StatusTestAgent", "1.0.0")
    assert row is not None
    assert (row.get("official_meta") or {}).get("status") == "active"


@pytest.mark.asyncio
async def test_publish_agent_card_with_deleted_status_registers_as_active(mgr):
    """Even if a re-publish of a previously deleted agent passes status='deleted',
    the resulting entry must be 'active' (publish always resets to active)."""
    await mgr.publish(_agent())
    await mgr.update_status("MyAgent", "1.0.0", "deleted")

    # Simulate re-registration where the card still has status="deleted".
    stale_card = AgentJSON(
        name="MyAgent",
        description="does things",
        version="1.0.0",
        status="deleted",
    )
    resp = await mgr.publish(stale_card)
    assert resp.meta.official is not None
    assert resp.meta.official.status == "active"


# ---------------------------------------------------------------------------
# Regression tests: update_status() recomputes is_latest
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_status_deleted_clears_is_latest(mgr, db):
    """Soft-deleting the only version must result in is_latest=False on that row."""
    await mgr.publish(_agent(version="1.0.0"))
    await mgr.update_status("MyAgent", "1.0.0", "deleted")

    row = await db.get_resource("agent", "MyAgent", "1.0.0")
    assert row is not None
    assert (
        row["is_latest"] is False
    ), "Deleted version must not retain is_latest=True after update_status"


@pytest.mark.asyncio
async def test_update_status_deleted_promotes_previous_version(mgr, db):
    """Soft-deleting the latest version must promote the next-highest to is_latest=True."""
    await mgr.publish(_agent(version="1.0.0"))
    await mgr.publish(_agent(version="2.0.0"))

    # Verify initial state: 2.0.0 is latest.
    v2 = await db.get_resource("agent", "MyAgent", "2.0.0")
    assert v2 is not None and v2["is_latest"] is True

    # Soft-delete 2.0.0 — 1.0.0 should become latest.
    await mgr.update_status("MyAgent", "2.0.0", "deleted")

    v1_after = await db.get_resource("agent", "MyAgent", "1.0.0")
    v2_after = await db.get_resource("agent", "MyAgent", "2.0.0")
    assert (
        v1_after is not None and v1_after["is_latest"] is True
    ), "Previous version must become is_latest after latest is soft-deleted"
    assert (
        v2_after is not None and v2_after["is_latest"] is False
    ), "Soft-deleted version must not be is_latest"
