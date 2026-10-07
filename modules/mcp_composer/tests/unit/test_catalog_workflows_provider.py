"""Tests for CatalogWorkflowsProvider FastMCP integration."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from mcp_composer.core.models.catalog_workflow import WorkflowJSON, WorkflowStep
from mcp_composer.store.catalog_workflows_provider import (
    CatalogWorkflowsProvider,
    CatalogWorkflowTool,
)


@pytest.mark.asyncio
async def test_get_tool_accepts_version_argument() -> None:
    """FastMCP passes an optional version to Provider._get_tool; workflow tools ignore it."""
    provider = CatalogWorkflowsProvider()
    workflow = WorkflowJSON(
        name="test-workflow",
        description="Test workflow",
        version="1.0.0",
        goal="Test",
        steps=[
            WorkflowStep(
                step=1,
                toolname="mcp-gurdium",
                tool="list_policy",
                input={},
            )
        ],
    )
    provider._tools_by_name = {"test-workflow": CatalogWorkflowTool(workflow)}

    tool = await provider._get_tool("test-workflow", version=None)
    assert tool is not None
    assert tool.name == "test-workflow"

    missing = await provider._get_tool("missing-workflow", version="1.0.0")
    assert missing is None


@pytest.mark.asyncio
async def test_workflow_tool_run_returns_execution_plan() -> None:
    workflow = WorkflowJSON(
        name="guardium-policy",
        description="Get Guardium policy summary",
        version="1.0.0",
        goal="Get Guardium policy summary",
        steps=[
            WorkflowStep(
                step=1,
                toolname="mcp-gurdium",
                tool="list_policy",
                input={},
            )
        ],
    )
    tool = CatalogWorkflowTool(workflow)
    result = await tool.run({})

    assert result.structured_content is not None
    plan = result.structured_content
    assert plan["workflow_name"] == "guardium-policy"
    assert plan["steps"][0]["mcp_tool_name"] == "mcp-gurdium_list_policy"
    assert plan["steps"][0]["layered_make_tool_call"] == "mcp-gurdium_make_tool_call"
    assert plan["steps"][0]["tool"] == "list_policy"


@pytest.mark.asyncio
async def test_refresh_tools_paginates_catalog_list() -> None:
    provider = CatalogWorkflowsProvider()
    mock_mgr = MagicMock()
    provider._mgr = mock_mgr

    wf = WorkflowJSON(
        name="wf-one",
        description="One",
        version="1.0.0",
        goal="One",
        steps=[
            WorkflowStep(step=1, toolname="mcp-gurdium", tool="list_policy", input={})
        ],
    )
    page1 = MagicMock()
    page1.workflows = [MagicMock(workflow=wf)]
    page1.metadata.next_start = None

    mock_mgr.list = AsyncMock(return_value=page1)

    await provider._refresh_tools()

    assert "wf-one" in provider._tools_by_name
    mock_mgr.list.assert_awaited_once()
