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
        monkeypatch.setenv("MCP_COMPOSER_ENV", "local")

        mock_tools = {"tool1": {"name": "tool1", "description": "Filtered Tool 1"}}
        mock_call_next.return_value = mock_tools

        result = await list_filtered_tool.on_list_tools(mock_context, mock_call_next)

        assert mock_call_next.call_count == 1
        assert isinstance(result, dict)
        assert len(result) == 1
        assert result["tool1"]["name"] == "tool1"

    @pytest.mark.asyncio
    async def test_on_list_tools_empty_tools(
        self, list_filtered_tool, mock_context, mock_call_next, monkeypatch
    ):
        """Empty tool list returns empty list."""
        monkeypatch.setenv("MCP_COMPOSER_ENV", "local")
        mock_call_next.return_value = {}

        result = await list_filtered_tool.on_list_tools(mock_context, mock_call_next)

        assert isinstance(result, dict)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_on_list_tools_with_complex_tools(
        self, list_filtered_tool, mock_context, mock_call_next, monkeypatch
    ):
        """Complex tool objects pass through correctly."""
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

        assert isinstance(result, dict)
        assert len(result) == 1
        assert result["complex_tool"]["name"] == "complex_tool"

    # ------------------------------------------------------------------
    # on_list_tools — non-local without ISV (no validated instances)
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_on_list_tools_non_local_without_isv_passes_empty_instances(
        self, list_filtered_tool, mock_context, mock_call_next, monkeypatch
    ):
        """Without isv_validator, non-local env never forwards header-only instances."""
        monkeypatch.setenv("MCP_COMPOSER_ENV", "dev")

        mock_tools = {"mcp-wx-data_get_service_info": Mock()}
        mock_filtered = {
            "mcp-wx-data_get_service_info": mock_tools["mcp-wx-data_get_service_info"]
        }

        mock_call_next.return_value = mock_tools
        list_filtered_tool.gw._tool_manager.filter_tools.return_value = mock_filtered

        await list_filtered_tool.on_list_tools(mock_context, mock_call_next)

        list_filtered_tool.gw._tool_manager.filter_tools.assert_called_once_with(
            mock_tools, user_instances=[]
        )

    # ------------------------------------------------------------------
    # Error handling
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_on_list_tools_tool_filter_error(
        self, list_filtered_tool, mock_context, mock_call_next, monkeypatch
    ):
        """ToolFilterError from filter_tools is re-raised with middleware message."""
        monkeypatch.setenv("MCP_COMPOSER_ENV", "dev")
        mock_call_next.return_value = {"tool1": Mock()}
        list_filtered_tool.gw._tool_manager.filter_tools.side_effect = ToolFilterError(
            "Filter error"
        )

        with pytest.raises(
            ToolFilterError, match="Tools filtering failed in middleware"
        ):
            await list_filtered_tool.on_list_tools(mock_context, mock_call_next)

        mock_call_next.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_list_tools_dev_prod_calls_filter_tools(
        self, list_filtered_tool, mock_context, mock_call_next, monkeypatch
    ):
        """In dev/prod path (env != local), filter_tools is called and filtered list returned."""
        monkeypatch.setenv("MCP_COMPOSER_ENV", "dev")
        mock_tools = {"tool1": Mock()}
        mock_filtered = {"tool1": mock_tools["tool1"]}
        mock_call_next.return_value = mock_tools
        list_filtered_tool.gw._tool_manager.filter_tools.return_value = mock_filtered

        result = await list_filtered_tool.on_list_tools(mock_context, mock_call_next)

        list_filtered_tool.gw._tool_manager.filter_tools.assert_called_once_with(
            mock_tools, user_instances=[]
        )
        assert mock_call_next.call_count == 1
        assert len(result) == 1
        assert result["tool1"] == mock_tools["tool1"]

    @pytest.mark.asyncio
    async def test_on_list_tools_filter_tools_generic_error(
        self, list_filtered_tool, mock_context, mock_call_next, monkeypatch
    ):
        """Generic error from filter_tools propagates unchanged."""
        monkeypatch.setenv("MCP_COMPOSER_ENV", "dev")
        mock_call_next.return_value = {"tool1": Mock()}
        list_filtered_tool.gw._tool_manager.filter_tools.side_effect = Exception(
            "Filter tools error"
        )

        with pytest.raises(Exception, match="Filter tools error"):
            await list_filtered_tool.on_list_tools(mock_context, mock_call_next)

        mock_call_next.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_list_tools_call_next_error(
        self, list_filtered_tool, mock_context, mock_call_next, monkeypatch
    ):
        """Error raised by call_next propagates immediately."""
        monkeypatch.delenv(
            "MCP_COMPOSER_ENV", raising=False
        )  # Ensure not in local mode
        mock_call_next.side_effect = Exception("Call next error")

        with pytest.raises(Exception, match="Call next error"):
            await list_filtered_tool.on_list_tools(mock_context, mock_call_next)

        mock_call_next.assert_called_once_with(mock_context)
        list_filtered_tool.gw._tool_manager.filter_tools.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_local_isv_no_cookie_uses_empty_instances_in_filter_tools(
        self, mock_context, mock_call_next, monkeypatch
    ):
        """With ISV validator, non-local env, and no session cookie — filter_tools gets []."""
        mock_isv = Mock()
        mock_isv.config.cookie_name = "mcsp-glb-iam-test"

        mock_gw = Mock()
        mock_gw._tool_manager = Mock()
        mock_gw._tool_manager.filter_tools = Mock(return_value=[])

        middleware = ListFilteredTool(mock_gw, isv_validator=mock_isv)
        monkeypatch.setenv("MCP_COMPOSER_ENV", "dev")

        req = Mock()
        req.headers = {}  # no Cookie and no mcsp-glb-iam-test header

        monkeypatch.setattr(
            "mcp_composer.middleware.tool.tool_filter.ctx_get",
            lambda _ctx, *_names, **_kw: req,
        )

        tool_mock = Mock()
        tool_mock.name = "mcp-x_foo"
        mock_call_next.return_value = [tool_mock]

        result = await middleware.on_list_tools(mock_context, mock_call_next)

        assert result == []
        mock_gw._tool_manager.filter_tools.assert_called_once_with(
            [tool_mock], user_instances=[]
        )

    @pytest.mark.asyncio
    async def test_non_local_isv_cookie_calls_auth_for_instances(
        self, mock_context, mock_call_next, monkeypatch
    ):
        """ISV + cookie present — user_instances come from _authenticate_and_get_instances."""
        mock_isv = Mock()
        mock_isv.config.cookie_name = "session-cookie"

        mock_gw = Mock()
        mock_gw._tool_manager = Mock()
        mock_gw._tool_manager.filter_tools = Mock(return_value=[])

        middleware = ListFilteredTool(mock_gw, isv_validator=mock_isv)
        monkeypatch.setenv("MCP_COMPOSER_ENV", "dev")

        req = Mock()
        req.headers = {"cookie": "session-cookie=abc123"}

        monkeypatch.setattr(
            "mcp_composer.middleware.tool.tool_filter.ctx_get",
            lambda _ctx, *_names, **_kw: req,
        )

        instances = [{"subscription": {"productId": "lakehouse"}}]
        monkeypatch.setattr(
            middleware,
            "_authenticate_and_get_instances",
            AsyncMock(return_value=instances),
        )

        tool_mock = Mock()
        tool_mock.name = "tool1"
        mock_call_next.return_value = [tool_mock]

        await middleware.on_list_tools(mock_context, mock_call_next)

        mock_gw._tool_manager.filter_tools.assert_called_once_with(
            [tool_mock], user_instances=instances
        )
