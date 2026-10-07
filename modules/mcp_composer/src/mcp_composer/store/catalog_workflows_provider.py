"""catalog_workflows_provider.py — Expose each catalog workflow as its own MCP tool."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastmcp.server.providers.base import Provider
from fastmcp.tools import Tool, ToolResult
from fastmcp.utilities.versions import VersionSpec
from mcp.types import TextContent
from mcp_composer.core.catalog.catalog_manager import CatalogResourceListFilter
from mcp_composer.core.catalog.workflow_manager import WorkflowManager
from mcp_composer.core.models.catalog_constants import RegistryResourceKind
from mcp_composer.core.models.catalog_workflow import WorkflowJSON
from mcp_composer.core.utils.logger import LoggerFactory
from mcp_composer.core.workflow_file_loader import build_execution_plan
from mcp_composer.store.catalog_factory import get_catalog_db

logger = LoggerFactory.get_logger()

_WORKFLOW_LIST_PAGE_SIZE = 1000

_WORKFLOW_TOOL_PARAMETERS: dict[str, Any] = {
    "type": "object",
    "properties": {
        "input": {
            "type": "object",
            "description": (
                "Optional runtime values for template placeholders in step inputs "
                "(e.g. values for {{catalog_id_from_step1}})."
            ),
            "additionalProperties": True,
        },
    },
    "additionalProperties": False,
}


class CatalogWorkflowTool(Tool):
    """MCP tool that returns the execution plan for one catalog workflow."""

    def __init__(self, workflow: WorkflowJSON) -> None:
        super().__init__(
            name=workflow.name,
            description=workflow.description,
            parameters=_WORKFLOW_TOOL_PARAMETERS,
        )
        self._workflow = workflow

    async def run(self, arguments: dict[str, Any]) -> ToolResult:
        plan = build_execution_plan(self._workflow)
        runtime_input = arguments.get("input")
        if runtime_input:
            plan["runtime_input"] = runtime_input
        text = json.dumps(plan, indent=2)
        return ToolResult(
            content=[TextContent(type="text", text=text)],
            structured_content=plan,
        )


class CatalogWorkflowsProvider(Provider):
    """Registers one MCP tool per active, latest workflow in the catalog."""

    def __init__(self) -> None:
        super().__init__()
        self._db = get_catalog_db()
        self._mgr: WorkflowManager | None = None
        self._tools_by_name: dict[str, CatalogWorkflowTool] = {}

    @asynccontextmanager
    async def lifespan(self) -> AsyncIterator[None]:
        self._mgr = WorkflowManager(self._db)
        await self._db.initialize()
        try:
            await self._refresh_tools()
            yield
        finally:
            await self._db.close()
            self._mgr = None
            self._tools_by_name = {}

    async def refresh(self) -> None:
        """Reload workflow tools from the catalog (call after file sync)."""
        await self._refresh_tools()

    async def _refresh_tools(self) -> None:
        if self._mgr is None:
            self._mgr = WorkflowManager(self._db)

        tools_by_name: dict[str, CatalogWorkflowTool] = {}
        start = 0
        while True:
            result = await self._mgr.list(
                CatalogResourceListFilter(
                    kind=RegistryResourceKind.WORKFLOW,
                    is_latest_only=True,
                    status_filter="active",
                    start=start,
                    limit=_WORKFLOW_LIST_PAGE_SIZE,
                )
            )
            for item in result.workflows:
                tools_by_name[item.workflow.name] = CatalogWorkflowTool(item.workflow)

            next_start = result.metadata.next_start
            if next_start is None:
                break
            start = next_start

        self._tools_by_name = tools_by_name
        logger.info(
            "CatalogWorkflowsProvider loaded %d workflow tools",
            len(self._tools_by_name),
        )

    async def _list_tools(self) -> list[Tool]:
        return list(self._tools_by_name.values())

    async def _get_tool(self, name: str, version: VersionSpec | None = None) -> Tool | None:
        del version  # workflow tools are not versioned separately from catalog rows
        return self._tools_by_name.get(name)
