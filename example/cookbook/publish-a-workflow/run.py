"""Publish a two-step workflow, list it, then mark it deprecated."""

import asyncio

from mcp_composer.core.catalog.catalog_manager import CatalogResourceListFilter
from mcp_composer.core.catalog.workflow_manager import WorkflowManager
from mcp_composer.core.models.catalog_constants import RegistryResourceKind
from mcp_composer.core.models.catalog_workflow import WorkflowJSON, WorkflowStep
from mcp_composer.store.catalog_in_memory_database import CatalogInMemoryDatabase


async def main() -> None:
    manager = WorkflowManager(CatalogInMemoryDatabase())
    published = await manager.publish(
        WorkflowJSON(
            name="count-then-seal",
            version="1.0.0",
            description="Count open boxes, then seal one when the caller asks for both.",
            goal="Report the open count and then seal one box.",
            steps=[
                WorkflowStep(
                    step=1,
                    toolname="count_open_boxes",
                    tool="count_open_boxes",
                    input={"shelf": "corner"},
                ),
                WorkflowStep(
                    step=2,
                    toolname="seal_box",
                    tool="seal_box",
                    input={"shelf": "corner"},
                ),
            ],
        )
    )
    listed = await manager.list(
        CatalogResourceListFilter(
            kind=RegistryResourceKind.WORKFLOW, is_latest_only=True
        )
    )
    await manager.update_status("count-then-seal", "1.0.0", "deprecated")
    current = await manager.get("count-then-seal", "1.0.0")
    steps = ", ".join(step.tool for step in published.workflow.steps)
    print(f"published: {published.workflow.name}")
    print("steps: " + steps)
    print("listed: " + ", ".join(item.workflow.name for item in listed.workflows))
    print(f"status: {current.workflow.status}")


if __name__ == "__main__":
    asyncio.run(main())
