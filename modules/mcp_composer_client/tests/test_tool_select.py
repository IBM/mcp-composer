import pytest
from packages.mcp_composer_client.src.mcp_composer_client import tool_select
from unittest.mock import patch, MagicMock
import asyncio


@pytest.mark.asyncio
async def test_select_tool_by_LLM():
    tools_all = [
        MagicMock(name="t1", description="desc1"),
        MagicMock(name="t2", description="desc2"),
    ]
    with patch("mcp_composer_client.tool_select.run_llm", return_value="t1\nt2"):
        result = await tool_select.select_tool_by_LLM("query", tools_all)
        assert "t1" in result and "t2" in result


@pytest.mark.asyncio
@patch("mcp_composer_client.tool_select.auto_filter_tools", return_value=["t1"])
async def test_select_tool(mock_select):
    tools_all = [MagicMock(name="t1"), MagicMock(name="t2")]
    result = await tool_select.auto_filter_tools("query", tools_all, select_method="llm")
    assert result == ["t1"]
