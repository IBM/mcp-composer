"""Publish an agent row that points at one skill, then delete it."""

import asyncio

from mcp_composer.core.catalog.agent_manager import AgentManager
from mcp_composer.core.catalog.catalog_manager import CatalogResourceListFilter
from mcp_composer.core.models.catalog_agent import AgentJSON
from mcp_composer.core.models.catalog_constants import RegistryResourceKind
from mcp_composer.store.catalog_in_memory_database import CatalogInMemoryDatabase


async def main() -> None:
    manager = AgentManager(CatalogInMemoryDatabase())
    published = await manager.publish(
        AgentJSON(
            name="shelf-clerk",
            version="1.0.0",
            description="Answers questions about open boxes on a shelf.",
        )
    )
    listed = await manager.list(
        CatalogResourceListFilter(kind=RegistryResourceKind.AGENT, is_latest_only=True)
    )
    await manager.delete("shelf-clerk", "1.0.0")
    after = await manager.list(
        CatalogResourceListFilter(kind=RegistryResourceKind.AGENT, is_latest_only=True)
    )
    print(f"published: {published.agent.name} {published.agent.version}")
    print("listed: " + ", ".join(item.agent.name for item in listed.agents))
    print(f"after delete: {len(after.agents)}")


if __name__ == "__main__":
    asyncio.run(main())
