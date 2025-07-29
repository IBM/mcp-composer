import pytest
from mcp_composer_client import tool_select
from unittest.mock import patch, MagicMock


def test_select_tool_by_LLM():
    tools_all = [MagicMock(name="t1", description="desc1"), MagicMock(name="t2", description="desc2")]
    with patch("mcp_composer_client.tool_select.run_llm", return_value="t1\nt2"):
        result = pytest.run(tool_select.select_tool_by_LLM("query", tools_all))
        assert "t1" in result and "t2" in result

@patch("mcp_composer_client.tool_select.select_tool_by_LLM", return_value=["t1"])
def test_select_tool(mock_select):
    tools_all = [MagicMock(name="t1"), MagicMock(name="t2")]
    result = pytest.run(tool_select.select_tool("query", tools_all, select_method="llm"))
    assert result == ["t1"] 