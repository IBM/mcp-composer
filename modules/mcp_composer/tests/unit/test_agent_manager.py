"""Unit tests for AgentManager backed by CatalogInMemoryDatabase."""

from __future__ import annotations

import pytest
from unittest.mock import patch

from mcp_composer.core.catalog import CatalogResourceNotFoundError, CatalogVersionCapError
from mcp_composer.core.catalog.agent_manager import AgentManager
from mcp_composer.core.catalog.catalog_manager import CatalogResourceListFilter
from mcp_composer.core.models.catalog_constants import RegistryResourceKind
from mcp_composer.core.models.catalog_agent import AgentJSON
from mcp_composer.store.catalog_in_memory_database import CatalogInMemoryDatabase


def _agent(
    name: str = "MyAgent",
    version: str = "1.0.0",
    description: str = "does things",
) -> AgentJSON:
    return AgentJSON(
        name=name,
        image="docker.io/example/agent:1",
        language="python",
        framework="langchain",
        model_provider="openai",
        model_name="gpt-4",
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
    with patch('mcp_composer.core.catalog.agent_manager.MAX_VERSIONS_PER_RESOURCE', test_cap):
        for i in range(test_cap):
            await mgr.publish(_agent(name="CapAgent", version=f"{i}.0.0"))
        with pytest.raises(CatalogVersionCapError):
            await mgr.publish(_agent(name="CapAgent", version="99999.0.0"))


@pytest.mark.asyncio
async def test_get_missing_raises(mgr):
    with pytest.raises(CatalogResourceNotFoundError):
        await mgr.get("Nope", "1.0.0")
