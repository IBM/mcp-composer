"""Test module for tool_filter.py"""

import json
from unittest.mock import AsyncMock, Mock

import pytest
from fastmcp.server.middleware import MiddlewareContext, Middleware
from mcp.types import CallToolResult

from mcp_composer.core.utils.exceptions import ToolFilterError
from mcp_composer.middleware.auth_context_middleware import HEADER_USER_INSTANCES
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
        # Mock tools
        mock_tools = [
            {"name": "tool1", "description": "Tool 1"},
            {"name": "tool2", "description": "Tool 2"},
        ]

        # Mock filtered tools
        mock_filtered_tools = {
            "tool1": {"name": "tool1", "description": "Filtered Tool 1"}
        }

        mock_call_next.return_value = mock_tools
        list_filtered_tool.gw._tool_manager.filter_tools.return_value = (
            mock_filtered_tools
        )

        # Call the middleware
        result = await list_filtered_tool.on_list_tools(mock_context, mock_call_next)

        # Verify calls
        list_filtered_tool.gw.get_tools.assert_not_called()
        list_filtered_tool.gw._tool_manager.filter_tools.assert_called_once_with(
            mock_tools,
            user_instances=None,
        )
        mock_call_next.assert_called_once_with(mock_context)

        # Verify result
        assert isinstance(result, dict)
        assert len(result) == 1
        assert result["tool1"]["name"] == "tool1"

    @pytest.mark.asyncio
    async def test_on_list_tools_tool_filter_error(
        self, list_filtered_tool, mock_context, mock_call_next
    ):
        """Test tool filtering with ToolFilterError"""
        mock_call_next.return_value = [{"name": "tool1", "description": "Tool 1"}]
        list_filtered_tool.gw._tool_manager.filter_tools.side_effect = ToolFilterError(
            "Filter error"
        )

        # Call the middleware and expect ToolFilterError
        with pytest.raises(
            ToolFilterError, match="Tools filtering failed in middleware"
        ):
            await list_filtered_tool.on_list_tools(mock_context, mock_call_next)

        # Verify get_tools was not used in current middleware flow
        list_filtered_tool.gw.get_tools.assert_not_called()
        list_filtered_tool.gw._tool_manager.filter_tools.assert_called_once()

        # Verify call_next was invoked before filtering failed
        mock_call_next.assert_called_once_with(mock_context)

    @pytest.mark.asyncio
    async def test_on_list_tools_filter_tools_error(
        self, list_filtered_tool, mock_context, mock_call_next
    ):
        """Test tool filtering when filter_tools raises ToolFilterError"""
        # Mock tools
        mock_tools = [{"name": "tool1", "description": "Tool 1"}]
        mock_call_next.return_value = mock_tools

        # Mock filter_tools to raise ToolFilterError
        list_filtered_tool.gw._tool_manager.filter_tools.side_effect = ToolFilterError(
            "Filter error"
        )

        # Call the middleware and expect ToolFilterError
        with pytest.raises(
            ToolFilterError, match="Tools filtering failed in middleware"
        ):
            await list_filtered_tool.on_list_tools(mock_context, mock_call_next)

        # Verify calls
        list_filtered_tool.gw.get_tools.assert_not_called()
        list_filtered_tool.gw._tool_manager.filter_tools.assert_called_once_with(
            mock_tools,
            user_instances=None,
        )

        # Verify call_next was invoked before filtering failed
        mock_call_next.assert_called_once_with(mock_context)

    @pytest.mark.asyncio
    async def test_on_list_tools_empty_tools(
        self, list_filtered_tool, mock_context, mock_call_next
    ):
        """Test tool filtering with empty tools list"""
        # Mock empty tools
        mock_tools = []
        mock_filtered_tools = {}

        list_filtered_tool.gw.get_tools.return_value = mock_tools
        list_filtered_tool.gw._tool_manager.filter_tools.return_value = (
            mock_filtered_tools
        )

        # Call the middleware
        result = await list_filtered_tool.on_list_tools(mock_context, mock_call_next)

        # Verify result
        assert isinstance(result, dict)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_on_list_tools_call_next_error(
        self, list_filtered_tool, mock_context, mock_call_next
    ):
        """Test tool filtering when call_next raises an error"""
        # Mock tools
        mock_tools = [{"name": "tool1", "description": "Tool 1"}]
        mock_filtered_tools = {
            "tool1": {"name": "tool1", "description": "Filtered Tool 1"}
        }

        list_filtered_tool.gw.get_tools.return_value = mock_tools
        list_filtered_tool.gw._tool_manager.filter_tools.return_value = (
            mock_filtered_tools
        )

        # Mock call_next to raise an error
        mock_call_next.side_effect = Exception("Call next error")

        # Call the middleware and expect the error to be propagated
        with pytest.raises(Exception, match="Call next error"):
            await list_filtered_tool.on_list_tools(mock_context, mock_call_next)

        # Verify calls
        list_filtered_tool.gw.get_tools.assert_not_called()
        list_filtered_tool.gw._tool_manager.filter_tools.assert_not_called()

        # Verify call_next was called and raised the error
        mock_call_next.assert_called_once_with(mock_context)

    @pytest.mark.asyncio
    async def test_on_list_tools_get_tools_error(
        self, list_filtered_tool, mock_context, mock_call_next
    ):
        """Test tool filtering when upstream middleware raises an error."""
        mock_call_next.side_effect = Exception("Get tools error")

        # Call the middleware and expect the error to be propagated
        with pytest.raises(Exception, match="Get tools error"):
            await list_filtered_tool.on_list_tools(mock_context, mock_call_next)

        # Verify get_tools was called
        list_filtered_tool.gw.get_tools.assert_not_called()
        list_filtered_tool.gw._tool_manager.filter_tools.assert_not_called()

        # Verify call_next was invoked and propagated the upstream error
        mock_call_next.assert_called_once_with(mock_context)

    def test_list_filtered_tool_class_inheritance(self, list_filtered_tool):
        """Test that ListFilteredTool inherits from Middleware"""
        assert isinstance(list_filtered_tool, Middleware)

    @pytest.mark.asyncio
    async def test_on_list_tools_with_complex_tools(
        self, list_filtered_tool, mock_context, mock_call_next
    ):
        """Test tool filtering with complex tool objects"""
        # Mock complex tools
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

        # Call the middleware
        result = await list_filtered_tool.on_list_tools(mock_context, mock_call_next)

        # Verify result
        assert isinstance(result, dict)
        assert len(result) == 1
        assert result["complex_tool"]["name"] == "complex_tool"

    @pytest.mark.asyncio
    async def test_on_list_tools_with_x_user_instances_header_filters_by_product(
        self, list_filtered_tool, mock_call_next
    ):
        """When x-user-instances header is present, only tools for matching products are returned."""
        mock_tools = {
            "mcp-wx-data_get_service_info": Mock(name="mcp-wx-data_get_service_info"),
            "mcp-gurdium_get_type_info": Mock(name="mcp-gurdium_get_type_info"),
        }
        mock_tools["mcp-wx-data_get_service_info"].name = "mcp-wx-data_get_service_info"
        mock_tools["mcp-gurdium_get_type_info"].name = "mcp-gurdium_get_type_info"

        # Filter returns only lakehouse tool (user has only lakehouse instances)
        filtered = {
            "mcp-wx-data_get_service_info": mock_tools["mcp-wx-data_get_service_info"]
        }

        list_filtered_tool.gw.get_tools = AsyncMock(return_value=mock_tools)
        list_filtered_tool.gw._tool_manager.filter_tools.return_value = filtered

        # Build context with request and x-user-instances header
        mock_request = Mock()
        mock_request.headers = {
            HEADER_USER_INSTANCES: json.dumps(
                [{"id": "inst1", "subscription": {"productId": "lakehouse"}}]
            ),
        }
        mock_context = Mock(spec=MiddlewareContext)
        mock_context.fastmcp_context = Mock()
        mock_context.fastmcp_context.request_context = Mock()
        mock_context.fastmcp_context.request_context.request = mock_request

        result = await list_filtered_tool.on_list_tools(mock_context, mock_call_next)

        list_filtered_tool.gw._tool_manager.filter_tools.assert_called_once()
        call_kw = list_filtered_tool.gw._tool_manager.filter_tools.call_args[1]
        assert call_kw["user_instances"] is not None
        assert len(call_kw["user_instances"]) == 1
        assert call_kw["user_instances"][0]["subscription"]["productId"] == "lakehouse"
        assert len(result) == 1
        assert "mcp-wx-data_get_service_info" in result

    @pytest.mark.asyncio
    async def test_on_call_tool_no_auth_context_allows(
        self, list_filtered_tool, mock_context, mock_call_next, monkeypatch
    ):
        """When there is no auth context, call proceeds (backward compatibility)."""
        mock_context.message = Mock(name="message")
        mock_context.message.name = "mcp-wx-data_get_service_info"

        monkeypatch.setattr(
            "mcp_composer.middleware.tool.tool_filter.get_auth_context",
            lambda: None,
        )
        result = await list_filtered_tool.on_call_tool(mock_context, mock_call_next)

        mock_call_next.assert_called_once_with(mock_context)
        assert result == mock_call_next.return_value

    @pytest.mark.asyncio
    async def test_on_call_tool_no_instances_allows(
        self, list_filtered_tool, mock_context, mock_call_next, monkeypatch
    ):
        """When auth context has no instances, call proceeds."""
        mock_context.message = Mock(name="message")
        mock_context.message.name = "mcp-wx-data_get_service_info"

        monkeypatch.setattr(
            "mcp_composer.middleware.tool.tool_filter.get_auth_context",
            lambda: {"user_instances_full": []},
        )
        result = await list_filtered_tool.on_call_tool(mock_context, mock_call_next)

        mock_call_next.assert_called_once_with(mock_context)

    @pytest.mark.asyncio
    async def test_on_call_tool_instances_no_match_returns_error(
        self, list_filtered_tool, mock_context, mock_call_next, monkeypatch
    ):
        """When user has instances but none match the tool's product_id, return error and do not call_next."""
        mock_context.message = Mock(name="message")
        mock_context.message.name = "mcp-gurdium_get_type_info"

        list_filtered_tool.gw._server_manager.get.return_value = Mock(
            config={"solis_config": {"product_id": "gi"}}
        )

        monkeypatch.setattr(
            "mcp_composer.middleware.tool.tool_filter.get_auth_context",
            lambda: {
                "user_instances_full": [
                    {"subscription": {"productId": "lakehouse"}},
                ],
            },
        )
        result = await list_filtered_tool.on_call_tool(mock_context, mock_call_next)

        mock_call_next.assert_not_called()
        assert isinstance(result, CallToolResult)
        assert result.isError is True
        assert "gi" in result.content[0].text
        assert "lakehouse" in result.content[0].text

    @pytest.mark.asyncio
    async def test_on_call_tool_matching_instance_invokes_call_next(
        self, list_filtered_tool, mock_context, mock_call_next, monkeypatch
    ):
        """When user has an instance matching the tool's product_id, call_next is invoked."""
        mock_context.message = Mock(name="message")
        mock_context.message.name = "mcp-gurdium_get_type_info"

        list_filtered_tool.gw._server_manager.get.return_value = Mock(
            config={"solis_config": {"product_id": "gi"}}
        )
        mock_call_next.return_value = "tool_result"

        monkeypatch.setattr(
            "mcp_composer.middleware.tool.tool_filter.get_auth_context",
            lambda: {
                "user_instances_full": [
                    {"subscription": {"productId": "gi"}},
                ],
            },
        )
        result = await list_filtered_tool.on_call_tool(mock_context, mock_call_next)

        mock_call_next.assert_called_once_with(mock_context)
        assert result == "tool_result"

    @pytest.mark.asyncio
    async def test_on_call_tool_composer_tool_no_prefix_invokes_call_next(
        self, list_filtered_tool, mock_context, mock_call_next
    ):
        """Composer-owned tool (no server_id prefix) always invokes call_next."""
        mock_context.message = Mock(name="message")
        mock_context.message.name = "enable_all_tools"

        mock_call_next.return_value = "ok"

        result = await list_filtered_tool.on_call_tool(mock_context, mock_call_next)

        mock_call_next.assert_called_once_with(mock_context)
        assert result == "ok"
