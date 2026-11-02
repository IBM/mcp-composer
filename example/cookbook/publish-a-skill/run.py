"""Publish a skill, mark it deprecated, then delete it."""

import asyncio

from mcp_composer.core.catalog.catalog_manager import CatalogResourceListFilter
from mcp_composer.core.catalog.skill_manager import SkillManager
from mcp_composer.core.models.catalog_constants import RegistryResourceKind
from mcp_composer.core.models.catalog_skill import SkillJSON
from mcp_composer.store.catalog_in_memory_database import CatalogInMemoryDatabase


async def main() -> None:
    manager = SkillManager(CatalogInMemoryDatabase())
    published = await manager.publish(
        SkillJSON(
            name="count-open-boxes",
            version="1.0.0",
            description=(
                "Count open boxes on a shelf. "
                "Use when the caller asks how many boxes are still open."
            ),
            allowed_tools=["count_open_boxes"],
        )
    )
    listed = await manager.list_summaries(
        CatalogResourceListFilter(kind=RegistryResourceKind.SKILL, is_latest_only=True)
    )
    await manager.update_status("count-open-boxes", "1.0.0", "deprecated")
    current = await manager.get("count-open-boxes", "1.0.0")
    await manager.delete("count-open-boxes", "1.0.0")
    after = await manager.list_summaries(
        CatalogResourceListFilter(kind=RegistryResourceKind.SKILL, is_latest_only=True)
    )
    print(f"published: {published.skill.name} {published.skill.version}")
    print("listed: " + ", ".join(item.name for item in listed.skills))
    print(f"status: {current.skill.status}")
    print(f"after delete: {len(after.skills)}")


if __name__ == "__main__":
    asyncio.run(main())
