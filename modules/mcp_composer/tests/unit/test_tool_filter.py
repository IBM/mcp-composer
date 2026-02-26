"""Test module for tool_filter.py"""

from unittest.mock import AsyncMock, Mock

import pytest
from fastmcp.server.middleware import MiddlewareContext, Middleware

from mcp_composer.core.utils.exceptions import ToolFilterError
from mcp_composer.middleware.tool.tool_filter import ListFilteredTool

# pylint: disable=protected-access,too-few-public-methods


class TestListFilteredTool:
    """Test cases for ListFilteredTool middleware"""

    @pytest.fixture
    def mock_gw(self):
        """Create a mock gateway"""
        mock = Mock()
        mock.get_tools = AsyncMock()
        mock._tool_manager = Mock()
        return mock

    @pytest.fixture
    def mock_context(self):
        """Create a mock middleware context"""
        return Mock(spec=MiddlewareContext)

    @pytest.fixture
    def mock_call_next(self):
        """Create a mock call_next function"""
        return AsyncMock()

    @pytest.fixture
    def list_filtered_tool(self, mock_gw):
        """Create a ListFilteredTool instance"""
        return ListFilteredTool(mock_gw)

    def test_list_filtered_tool_initialization(self, mock_gw):
        """Test ListFilteredTool initialization"""
        middleware = ListFilteredTool(mock_gw)
        assert middleware.gw == mock_gw

    @pytest.mark.asyncio
    async def test_on_list_tools_success(
        self, list_filtered_tool, mock_context, mock_call_next
    ):
        """Test successful tool filtering"""
        mock_tools = [
            {"name": "tool1", "description": "Tool 1"},
            {"name": "tool2", "description": "Tool 2"},
        ]
        mock_filtered_tools = {
            "tool1": {"name": "tool1", "description": "Filtered Tool 1"}
        }

        list_filtered_tool.gw.get_tools.return_value = mock_tools
        list_filtered_tool.gw._tool_manager.filter_tools.return_value = (
            mock_filtered_tools
        )

        result = await list_filtered_tool.on_list_tools(mock_context, mock_call_next)

        list_filtered_tool.gw.get_tools.assert_called_once()
        list_filtered_tool.gw._tool_manager.filter_tools.assert_called_once_with(
            mock_tools
        )
        mock_call_next.assert_called_once_with(mock_context)

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["name"] == "tool1"

    @pytest.mark.asyncio
    async def test_on_list_tools_tool_filter_error(
        self, list_filtered_tool, mock_context, mock_call_next
    ):
        """Test tool filtering with ToolFilterError"""
        list_filtered_tool.gw.get_tools.side_effect = ToolFilterError("Filter error")

        with pytest.raises(
            ToolFilterError, match="Tools filtering failed in middleware"
        ):
            await list_filtered_tool.on_list_tools(mock_context, mock_call_next)

        list_filtered_tool.gw.get_tools.assert_called_once()
        mock_call_next.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_list_tools_filter_tools_error(
        self, list_filtered_tool, mock_context, mock_call_next
    ):
        """Test tool filtering when filter_tools raises ToolFilterError"""
        mock_tools = [{"name": "tool1", "description": "Tool 1"}]
        list_filtered_tool.gw.get_tools.return_value = mock_tools

        list_filtered_tool.gw._tool_manager.filter_tools.side_effect = ToolFilterError(
            "Filter error"
        )

        with pytest.raises(
            ToolFilterError, match="Tools filtering failed in middleware"
        ):
            await list_filtered_tool.on_list_tools(mock_context, mock_call_next)

        list_filtered_tool.gw.get_tools.assert_called_once()
        list_filtered_tool.gw._tool_manager.filter_tools.assert_called_once_with(
            mock_tools
        )
        mock_call_next.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_list_tools_empty_tools(
        self, list_filtered_tool, mock_context, mock_call_next
    ):
        """Test tool filtering with empty tools list"""
        list_filtered_tool.gw.get_tools.return_value = []
        list_filtered_tool.gw._tool_manager.filter_tools.return_value = {}

        result = await list_filtered_tool.on_list_tools(mock_context, mock_call_next)

        assert isinstance(result, list)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_on_list_tools_call_next_error(
        self, list_filtered_tool, mock_context, mock_call_next
    ):
        """Test tool filtering when call_next raises an error"""
        mock_tools = [{"name": "tool1", "description": "Tool 1"}]
        mock_filtered_tools = {
            "tool1": {"name": "tool1", "description": "Filtered Tool 1"}
        }

        list_filtered_tool.gw.get_tools.return_value = mock_tools
        list_filtered_tool.gw._tool_manager.filter_tools.return_value = (
            mock_filtered_tools
        )
        mock_call_next.side_effect = Exception("Call next error")

        with pytest.raises(Exception, match="Call next error"):
            await list_filtered_tool.on_list_tools(mock_context, mock_call_next)

        list_filtered_tool.gw.get_tools.assert_called_once()
        list_filtered_tool.gw._tool_manager.filter_tools.assert_called_once_with(
            mock_tools
        )
        mock_call_next.assert_called_once_with(mock_context)

    @pytest.mark.asyncio
    async def test_on_list_tools_get_tools_error(
        self, list_filtered_tool, mock_context, mock_call_next
    ):
        """Test tool filtering when get_tools raises an error"""
        list_filtered_tool.gw.get_tools.side_effect = Exception("Get tools error")

        with pytest.raises(Exception, match="Get tools error"):
            await list_filtered_tool.on_list_tools(mock_context, mock_call_next)

        list_filtered_tool.gw.get_tools.assert_called_once()
        mock_call_next.assert_not_called()

    def test_list_filtered_tool_class_inheritance(self, list_filtered_tool):
        """Test that ListFilteredTool inherits from Middleware"""
        assert isinstance(list_filtered_tool, Middleware)

    @pytest.mark.asyncio
    async def test_on_list_tools_with_complex_tools(
        self, list_filtered_tool, mock_context, mock_call_next
    ):
        """Test tool filtering with complex tool objects"""
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
        list_filtered_tool.gw._tool_manager.filter_tools.return_value = (
            mock_filtered_tools
        )

        result = await list_filtered_tool.on_list_tools(mock_context, mock_call_next)

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["name"] == "complex_tool"
