"""Test module for tool_filter.py"""

from unittest.mock import AsyncMock, Mock

import pytest
from fastmcp.server.middleware import MiddlewareContext, Middleware

from mcp_composer.core.utils.exceptions import ToolFilterError
from mcp_composer.middleware.tool.tool_filter import ListFilteredTool

# pylint: disable=protected-access,too-few-public-methods

_EXTRACT = "mcp_composer.middleware.tool.tool_filter._extract_user_instances"


class TestListFilteredTool:
    """Test cases for ListFilteredTool middleware"""

    @pytest.fixture
    def mock_gw(self):
        mock = Mock()
        mock.get_tools = AsyncMock()
        mock._tool_manager = Mock()
        return mock

    @pytest.fixture
    def mock_context(self):
        return Mock(spec=MiddlewareContext)

    @pytest.fixture
    def mock_call_next(self):
        return AsyncMock()

    @pytest.fixture
    def list_filtered_tool(self, mock_gw):
        return ListFilteredTool(mock_gw)

    def test_list_filtered_tool_initialization(self, mock_gw):
        middleware = ListFilteredTool(mock_gw)
        assert middleware.gw == mock_gw

    def test_list_filtered_tool_class_inheritance(self, list_filtered_tool):
        assert isinstance(list_filtered_tool, Middleware)

    # ------------------------------------------------------------------
    # on_list_tools — no user instances (header absent)
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_on_list_tools_success_no_instances(
        self, list_filtered_tool, mock_context, mock_call_next, monkeypatch
    ):
        """Successful filtering when x-user-instances header is absent."""
        monkeypatch.setattr(_EXTRACT, lambda ctx: None)

        mock_tools = [
            {"name": "tool1", "description": "Tool 1"},
            {"name": "tool2", "description": "Tool 2"},
        ]
        mock_filtered_tools = {
            "tool1": {"name": "tool1", "description": "Filtered Tool 1"}
        }

        list_filtered_tool.gw.get_tools.return_value = mock_tools
        list_filtered_tool.gw._tool_manager.filter_tools.return_value = mock_filtered_tools

        result = await list_filtered_tool.on_list_tools(mock_context, mock_call_next)

        list_filtered_tool.gw.get_tools.assert_called_once()
        list_filtered_tool.gw._tool_manager.filter_tools.assert_called_once_with(
            mock_tools, user_instances=None
        )
        mock_call_next.assert_called_once_with(mock_context)
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["name"] == "tool1"

    @pytest.mark.asyncio
    async def test_on_list_tools_empty_tools(
        self, list_filtered_tool, mock_context, mock_call_next, monkeypatch
    ):
        """Empty tool list returns empty list."""
        monkeypatch.setattr(_EXTRACT, lambda ctx: None)

        list_filtered_tool.gw.get_tools.return_value = []
        list_filtered_tool.gw._tool_manager.filter_tools.return_value = {}

        result = await list_filtered_tool.on_list_tools(mock_context, mock_call_next)

        assert isinstance(result, list)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_on_list_tools_with_complex_tools(
        self, list_filtered_tool, mock_context, mock_call_next, monkeypatch
    ):
        """Complex tool objects pass through correctly."""
        monkeypatch.setattr(_EXTRACT, lambda ctx: None)

        mock_tools = [
            {
                "name": "complex_tool",
                "description": "Complex Tool",
                "parameters": {"type": "object"},
            }
        ]
        mock_filtered_tools = {
            "complex_tool": {
                "name": "complex_tool",
                "description": "Complex Tool",
                "parameters": {"type": "object"},
            }
        }

        list_filtered_tool.gw.get_tools.return_value = mock_tools
        list_filtered_tool.gw._tool_manager.filter_tools.return_value = mock_filtered_tools

        result = await list_filtered_tool.on_list_tools(mock_context, mock_call_next)

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["name"] == "complex_tool"

    # ------------------------------------------------------------------
    # on_list_tools — user instances present in header
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_on_list_tools_passes_user_instances_from_header(
        self, list_filtered_tool, mock_context, mock_call_next, monkeypatch
    ):
        """user instances extracted from x-user-instances header are forwarded to filter_tools."""
        instances = [{"subscription": {"productId": "lakehouse"}}]
        monkeypatch.setattr(_EXTRACT, lambda ctx: instances)

        mock_tools = {"mcp-wx-data_get_service_info": Mock()}
        mock_filtered = {"mcp-wx-data_get_service_info": mock_tools["mcp-wx-data_get_service_info"]}

        list_filtered_tool.gw.get_tools = AsyncMock(return_value=mock_tools)
        list_filtered_tool.gw._tool_manager.filter_tools.return_value = mock_filtered

        await list_filtered_tool.on_list_tools(mock_context, mock_call_next)

        list_filtered_tool.gw._tool_manager.filter_tools.assert_called_once_with(
            mock_tools, user_instances=instances
        )

    # ------------------------------------------------------------------
    # Error handling
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_on_list_tools_tool_filter_error(
        self, list_filtered_tool, mock_context, mock_call_next, monkeypatch
    ):
        """ToolFilterError from get_tools is re-raised with middleware message."""
        monkeypatch.setattr(_EXTRACT, lambda ctx: None)
        list_filtered_tool.gw.get_tools.side_effect = ToolFilterError("Filter error")

        with pytest.raises(ToolFilterError, match="Tools filtering failed in middleware"):
            await list_filtered_tool.on_list_tools(mock_context, mock_call_next)

        list_filtered_tool.gw.get_tools.assert_called_once()
        mock_call_next.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_list_tools_filter_tools_error(
        self, list_filtered_tool, mock_context, mock_call_next, monkeypatch
    ):
        """ToolFilterError from filter_tools is re-raised with middleware message."""
        monkeypatch.setattr(_EXTRACT, lambda ctx: None)
        mock_tools = [{"name": "tool1", "description": "Tool 1"}]
        list_filtered_tool.gw.get_tools.return_value = mock_tools
        list_filtered_tool.gw._tool_manager.filter_tools.side_effect = ToolFilterError(
            "Filter error"
        )

        with pytest.raises(ToolFilterError, match="Tools filtering failed in middleware"):
            await list_filtered_tool.on_list_tools(mock_context, mock_call_next)

        list_filtered_tool.gw._tool_manager.filter_tools.assert_called_once_with(
            mock_tools, user_instances=None
        )
        mock_call_next.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_list_tools_get_tools_generic_error(
        self, list_filtered_tool, mock_context, mock_call_next, monkeypatch
    ):
        """Generic error from get_tools propagates unchanged."""
        monkeypatch.setattr(_EXTRACT, lambda ctx: None)
        list_filtered_tool.gw.get_tools.side_effect = Exception("Get tools error")

        with pytest.raises(Exception, match="Get tools error"):
            await list_filtered_tool.on_list_tools(mock_context, mock_call_next)

        mock_call_next.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_list_tools_call_next_error(
        self, list_filtered_tool, mock_context, mock_call_next, monkeypatch
    ):
        """Error raised by call_next propagates after filter_tools succeeds."""
        monkeypatch.setattr(_EXTRACT, lambda ctx: None)
        mock_tools = [{"name": "tool1", "description": "Tool 1"}]
        mock_filtered_tools = {
            "tool1": {"name": "tool1", "description": "Filtered Tool 1"}
        }
        list_filtered_tool.gw.get_tools.return_value = mock_tools
        list_filtered_tool.gw._tool_manager.filter_tools.return_value = mock_filtered_tools
        mock_call_next.side_effect = Exception("Call next error")

        with pytest.raises(Exception, match="Call next error"):
            await list_filtered_tool.on_list_tools(mock_context, mock_call_next)

        list_filtered_tool.gw._tool_manager.filter_tools.assert_called_once_with(
            mock_tools, user_instances=None
        )
        mock_call_next.assert_called_once_with(mock_context)
