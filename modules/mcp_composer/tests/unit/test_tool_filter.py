"""Test module for tool_filter.py"""

from unittest.mock import AsyncMock, Mock

import pytest
from fastmcp.server.middleware import MiddlewareContext, Middleware

from mcp_composer.core.utils.exceptions import ToolFilterError
from mcp_composer.middleware.tool.tool_filter import ListFilteredTool

# pylint: disable=protected-access,too-few-public-methods

_EXTRACT = "mcp_composer.middleware.tool.tool_filter.extract_user_instances"


class TestListFilteredTool:
    """Test cases for ListFilteredTool middleware"""

    @pytest.fixture
    def mock_gw(self):
        mock = Mock()
        mock.get_tools = AsyncMock()
        mock._tool_manager = Mock()
        mock._tool_manager.disable_tools = AsyncMock()
        mock._tool_manager.enable_tools = AsyncMock()
        mock._tool_manager.filter_tools = Mock()
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
        monkeypatch.setattr(_EXTRACT, lambda req: None)
        monkeypatch.setenv("MCP_COMPOSER_ENV", "local")

        mock_tools = {"tool1": {"name": "tool1", "description": "Filtered Tool 1"}}
        mock_call_next.return_value = mock_tools

        result = await list_filtered_tool.on_list_tools(mock_context, mock_call_next)

        assert mock_call_next.call_count == 2
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["name"] == "tool1"

    @pytest.mark.asyncio
    async def test_on_list_tools_empty_tools(
        self, list_filtered_tool, mock_context, mock_call_next, monkeypatch
    ):
        """Empty tool list returns empty list."""
        monkeypatch.setattr(_EXTRACT, lambda req: None)
        monkeypatch.setenv("MCP_COMPOSER_ENV", "local")
        mock_call_next.return_value = {}

        result = await list_filtered_tool.on_list_tools(mock_context, mock_call_next)

        assert isinstance(result, list)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_on_list_tools_with_complex_tools(
        self, list_filtered_tool, mock_context, mock_call_next, monkeypatch
    ):
        """Complex tool objects pass through correctly."""
        monkeypatch.setattr(_EXTRACT, lambda req: None)
        monkeypatch.setenv("MCP_COMPOSER_ENV", "local")

        mock_tools = {
            "complex_tool": {
                "name": "complex_tool",
                "description": "Complex Tool",
                "parameters": {"type": "object"},
            }
        }

        mock_call_next.return_value = mock_tools

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
        monkeypatch.setattr(_EXTRACT, lambda req: instances)

        mock_tools = {"mcp-wx-data_get_service_info": Mock()}
        mock_filtered = {
            "mcp-wx-data_get_service_info": mock_tools["mcp-wx-data_get_service_info"]
        }

        mock_call_next.return_value = mock_tools
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
        """ToolFilterError from filter_tools is re-raised with middleware message."""
        monkeypatch.setattr(_EXTRACT, lambda req: None)
        mock_call_next.return_value = {"tool1": Mock()}
        list_filtered_tool.gw._tool_manager.filter_tools.side_effect = ToolFilterError(
            "Filter error"
        )

        with pytest.raises(
            ToolFilterError, match="Tools filtering failed in middleware"
        ):
            await list_filtered_tool.on_list_tools(mock_context, mock_call_next)

        mock_call_next.assert_called_once_with(mock_context)

    @pytest.mark.asyncio
    async def test_on_list_tools_dev_prod_calls_filter_tools(
        self, list_filtered_tool, mock_context, mock_call_next, monkeypatch
    ):
        """In dev/prod path (env != local), filter_tools is called and filtered list returned."""
        monkeypatch.setattr(_EXTRACT, lambda req: None)
        mock_tools = {"tool1": Mock()}
        mock_filtered = {"tool1": mock_tools["tool1"]}
        mock_call_next.return_value = mock_tools
        list_filtered_tool.gw._tool_manager.filter_tools.return_value = mock_filtered

        result = await list_filtered_tool.on_list_tools(mock_context, mock_call_next)

        list_filtered_tool.gw._tool_manager.filter_tools.assert_called_once_with(
            mock_tools, user_instances=[]
        )
        assert mock_call_next.call_count == 2
        assert len(result) == 1
        assert result[0] == mock_tools["tool1"]

    @pytest.mark.asyncio
    async def test_on_list_tools_filter_tools_generic_error(
        self, list_filtered_tool, mock_context, mock_call_next, monkeypatch
    ):
        """Generic error from filter_tools propagates unchanged."""
        monkeypatch.setattr(_EXTRACT, lambda req: None)
        mock_call_next.return_value = {"tool1": Mock()}
        list_filtered_tool.gw._tool_manager.filter_tools.side_effect = Exception(
            "Filter tools error"
        )

        with pytest.raises(Exception, match="Filter tools error"):
            await list_filtered_tool.on_list_tools(mock_context, mock_call_next)

        mock_call_next.assert_called_once_with(mock_context)

    @pytest.mark.asyncio
    async def test_on_list_tools_call_next_error(
        self, list_filtered_tool, mock_context, mock_call_next, monkeypatch
    ):
        """Error raised by call_next propagates when initial tool fetch fails."""
        monkeypatch.setattr(_EXTRACT, lambda req: None)
        mock_call_next.side_effect = Exception("Call next error")

        with pytest.raises(Exception, match="Call next error"):
            await list_filtered_tool.on_list_tools(mock_context, mock_call_next)

        list_filtered_tool.gw._tool_manager.filter_tools.assert_not_called()
        mock_call_next.assert_called_once_with(mock_context)
