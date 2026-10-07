"""
Test for LayeredMCPFactory to verify it correctly creates a layered MCP server
with discovery tools on top of a proxied MCP server.
"""

import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from fastmcp import FastMCP, Client
from fastmcp.exceptions import ToolError
from mcp_composer.core.member_servers.layered_factory_mcp import LayeredMCPFactory


@pytest.mark.asyncio
async def test_layered_mcp_factory_initialization():
    """Test that LayeredMCPFactory initializes correctly."""
    # Create a mock client
    mock_client = MagicMock(spec=Client)
    mock_client.transport = MagicMock()

    # Create the factory
    factory = LayeredMCPFactory(
        client=mock_client,
        server_id="test-server",
        product_id="test-product",
        tool_descriptions={"get_service_info": "Custom description"},
    )

    # Verify factory attributes
    assert factory.client == mock_client
    assert factory.server_id == "test-server"
    assert factory.product_id == "test-product"

    # Verify factory is a FastMCP instance
    assert isinstance(factory, FastMCP)

    # Verify discovery tools are present by checking if they can be called
    # FastMCP stores tools differently, so we check the methods exist
    assert hasattr(factory, "get_service_info")
    assert hasattr(factory, "get_type_info")
    assert hasattr(factory, "make_tool_call")


@pytest.mark.asyncio
async def test_layered_mcp_factory_fetch_tools():
    """Test that _fetch_tools correctly retrieves tools from proxy server."""
    # Create a mock client
    mock_client = MagicMock(spec=Client)
    mock_client.transport = MagicMock()

    # Create a mock proxy server with tools
    with patch(
        "mcp_composer.core.member_servers.layered_factory_mcp.create_proxy"
    ) as mock_create_proxy:
        mock_proxy = MagicMock()
        mock_tool1 = SimpleNamespace(name="tool1", description="Tool 1 description")
        mock_tool2 = SimpleNamespace(name="tool2", description="Tool 2 description")

        # Mock list_tools to return our test tools
        mock_proxy.list_tools = AsyncMock(return_value=[mock_tool1, mock_tool2])
        mock_create_proxy.return_value = mock_proxy

        # Create the factory
        factory = LayeredMCPFactory(client=mock_client, server_id="test-server")

        # Fetch tools
        tools = await factory._fetch_tools()

        # Verify tools were fetched
        assert len(tools) == 2
        assert tools[0]["name"] == "tool1"
        assert tools[0]["description"] == "Tool 1 description"
        assert tools[1]["name"] == "tool2"
        assert tools[1]["description"] == "Tool 2 description"


@pytest.mark.asyncio
async def test_layered_mcp_factory_fetch_tools_with_parameters_schema():
    """Test that _fetch_tools normalizes proxied tool schema from parameters."""
    mock_client = MagicMock(spec=Client)
    mock_client.transport = MagicMock()

    with patch(
        "mcp_composer.core.member_servers.layered_factory_mcp.create_proxy"
    ) as mock_create_proxy:
        mock_proxy = MagicMock()
        mock_tool = SimpleNamespace(
            name="tool_with_parameters",
            description="Tool with parameters schema",
            parameters={
                "type": "object",
                "properties": {"foo": {"type": "string"}},
            },
        )

        mock_proxy.list_tools = AsyncMock(return_value=[mock_tool])
        mock_create_proxy.return_value = mock_proxy

        factory = LayeredMCPFactory(client=mock_client, server_id="test-server")
        tools = await factory._fetch_tools()

        assert len(tools) == 1
        assert tools[0]["name"] == "tool_with_parameters"
        assert tools[0]["inputSchema"] == mock_tool.parameters


@pytest.mark.asyncio
async def test_layered_mcp_factory_get_service_info_with_parameters_schema():
    """List mode is slim — schemas come from get_type_info, not get_service_info."""
    import json

    mock_client = MagicMock(spec=Client)
    mock_client.transport = MagicMock()

    with patch(
        "mcp_composer.core.member_servers.layered_factory_mcp.create_proxy"
    ) as mock_create_proxy:
        mock_proxy = MagicMock()
        mock_tool = SimpleNamespace(
            name="test_tool",
            description="Test tool",
            parameters={
                "type": "object",
                "properties": {"bar": {"type": "number"}},
            },
        )

        mock_proxy.list_tools = AsyncMock(return_value=[mock_tool])
        mock_create_proxy.return_value = mock_proxy

        factory = LayeredMCPFactory(client=mock_client, server_id="test-server")
        result = await factory.get_service_info()
        result_dict = json.loads(result)

        assert result_dict["mode"] == "list"
        assert len(result_dict["matches"]) == 1
        assert result_dict["matches"][0]["name"] == "test_tool"
        assert "inputSchema" not in result_dict["matches"][0]

        detail = json.loads(await factory.get_service_info(service="test_tool"))
        assert detail["name"] == "test_tool"
        assert detail["has_input_schema"] is True


@pytest.mark.asyncio
async def test_layered_mcp_factory_get_type_info_with_parameters_schema():
    """Test get_type_info uses parameters schema when inputSchema is absent."""
    import json

    mock_client = MagicMock(spec=Client)
    mock_client.transport = MagicMock()

    with patch(
        "mcp_composer.core.member_servers.layered_factory_mcp.create_proxy"
    ) as mock_create_proxy:
        mock_proxy = MagicMock()
        mock_tool = SimpleNamespace(
            name="test_tool",
            description="Test tool",
            parameters={
                "type": "object",
                "properties": {"baz": {"type": "string", "description": "Baz value"}},
                "required": ["baz"],
            },
        )

        mock_proxy.list_tools = AsyncMock(return_value=[mock_tool])
        mock_create_proxy.return_value = mock_proxy

        factory = LayeredMCPFactory(client=mock_client, server_id="test-server")
        result = await factory.get_type_info("test_tool")
        result_dict = json.loads(result)

        assert result_dict["name"] == "test_tool"
        assert result_dict["description"] == "Test tool"
        assert result_dict["inputSchema"] == mock_tool.parameters
        assert "parameters" in result_dict
        assert result_dict["parameters"][0]["name"] == "baz"
        assert result_dict["parameters"][0]["required"] is True


@pytest.mark.asyncio
async def test_layered_mcp_factory_get_service_info():
    """Test that get_service_info returns slim query-first JSON."""
    import json

    mock_client = MagicMock(spec=Client)
    mock_client.transport = MagicMock()

    with patch(
        "mcp_composer.core.member_servers.layered_factory_mcp.create_proxy"
    ) as mock_create_proxy:
        mock_proxy = MagicMock()
        mock_tool = SimpleNamespace(name="test_tool", description="Test tool")

        mock_proxy.list_tools = AsyncMock(return_value=[mock_tool])
        mock_create_proxy.return_value = mock_proxy

        factory = LayeredMCPFactory(client=mock_client, server_id="test-server")

        result = await factory.get_service_info()
        result_dict = json.loads(result)

        assert "matches" in result_dict
        assert result_dict["total_services"] == 1
        assert len(result_dict["matches"]) == 1
        assert result_dict["matches"][0]["name"] == "test_tool"

        searched = json.loads(await factory.get_service_info(query="test"))
        assert searched["mode"] == "search"
        assert searched["query"] == "test"
        assert any(m["name"] == "test_tool" for m in searched["matches"])


@pytest.mark.asyncio
async def test_layered_mcp_factory_make_tool_call():
    """Test that make_tool_call calls the proxy correctly."""
    import json

    # Create a mock client
    mock_client = MagicMock(spec=Client)
    mock_client.transport = MagicMock()
    mock_result = MagicMock()
    mock_content = MagicMock()
    mock_content.text = "Tool execution result"
    mock_result.content = [mock_content]

    # Mock the async context manager and call_tool
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.call_tool = AsyncMock(return_value=mock_result)

    # Create a mock proxy server with tools
    with patch(
        "mcp_composer.core.member_servers.layered_factory_mcp.create_proxy"
    ) as mock_create_proxy:
        mock_proxy = MagicMock()
        mock_tool = SimpleNamespace(name="test_tool", description="Test tool")

        # Mock list_tools to return our test tool
        mock_proxy.list_tools = AsyncMock(return_value=[mock_tool])

        # Mock call_tool to return our result
        mock_proxy.call_tool = AsyncMock(return_value=mock_result)

        mock_create_proxy.return_value = mock_proxy

        # Create the factory
        factory = LayeredMCPFactory(client=mock_client, server_id="test-server")

        # Call make_tool_call
        result = await factory.make_tool_call("test_tool", {"arg1": "value1"})


@pytest.mark.asyncio
async def test_layered_mcp_factory_authorization_success():
    """Test that make_tool_call succeeds with valid authorization."""
    import json

    # Create a mock client
    mock_client = MagicMock(spec=Client)
    mock_client.transport = MagicMock()
    mock_result = MagicMock()
    mock_content = MagicMock()
    mock_content.text = "Authorized tool execution result"
    mock_result.content = [mock_content]

    # Create a mock proxy server with tools
    with patch(
        "mcp_composer.core.member_servers.layered_factory_mcp.create_proxy"
    ) as mock_create_proxy, patch(
        "mcp_composer.core.member_servers.layered_factory_mcp.get_auth_context"
    ) as mock_get_auth_context, patch(
        "mcp_composer.core.member_servers.layered_factory_mcp.AUTH_CONTEXT_AVAILABLE",
        True,
    ):
        mock_proxy = MagicMock()
        mock_tool = SimpleNamespace(name="test_tool", description="Test tool")

        # Mock list_tools to return our test tool
        mock_proxy.list_tools = AsyncMock(return_value=[mock_tool])

        # Mock call_tool to return our result
        mock_proxy.call_tool = AsyncMock(return_value=mock_result)

        mock_create_proxy.return_value = mock_proxy

        # Mock auth context with matching product_id
        mock_get_auth_context.return_value = {
            "user_instances_full": [
                {
                    "id": "instance-123",
                    "name": "Test Instance",
                    "state": "active",
                    "subscription": {
                        "productId": "test-product",
                        "subscriptionName": "Test Subscription",
                    },
                }
            ]
        }

        # Create the factory with matching product_id
        factory = LayeredMCPFactory(
            client=mock_client, server_id="test-server", product_id="test-product"
        )

        # Call make_tool_call
        result = await factory.make_tool_call("test_tool", {"arg1": "value1"})

        # Verify proxy.call_tool was called (authorization passed)
        mock_proxy.call_tool.assert_called_once_with("test_tool", {"arg1": "value1"})

        # Verify result
        assert result == "Authorized tool execution result"


@pytest.mark.asyncio
async def test_layered_mcp_factory_authorization_failure():
    """Test that make_tool_call fails with invalid authorization."""
    import json

    # Create a mock client
    mock_client = MagicMock(spec=Client)
    mock_client.transport = MagicMock()

    # Create a mock proxy server with tools
    with patch(
        "mcp_composer.core.member_servers.layered_factory_mcp.create_proxy"
    ) as mock_create_proxy, patch(
        "mcp_composer.core.member_servers.layered_factory_mcp.get_auth_context"
    ) as mock_get_auth_context, patch(
        "mcp_composer.core.member_servers.layered_factory_mcp.AUTH_CONTEXT_AVAILABLE",
        True,
    ):
        mock_proxy = MagicMock()
        mock_tool = SimpleNamespace(name="test_tool", description="Test tool")

        # Mock list_tools to return our test tool
        mock_proxy.list_tools = AsyncMock(return_value=[mock_tool])

        mock_create_proxy.return_value = mock_proxy

        # Mock auth context with non-matching product_id
        mock_get_auth_context.return_value = {
            "user_instances_full": [
                {
                    "id": "instance-123",
                    "name": "Test Instance",
                    "state": "active",
                    "subscription": {
                        "productId": "different-product",
                        "subscriptionName": "Test Subscription",
                    },
                }
            ]
        }

        # Create the factory with non-matching product_id
        factory = LayeredMCPFactory(
            client=mock_client, server_id="test-server", product_id="test-product"
        )

        # Call make_tool_call
        result = await factory.make_tool_call("test_tool", {"arg1": "value1"})

        # Parse result
        result_dict = json.loads(result)

        # Verify authorization failed
        assert result_dict["error"] == "Unauthorized"
        assert result_dict["status_code"] == 401
        assert "test-product" in result_dict["message"]
        assert "different-product" in str(result_dict["available_product_ids"])

        # Verify proxy.call_tool was NOT called (authorization failed)
        mock_proxy.call_tool.assert_not_called()


@pytest.mark.asyncio
async def test_layered_mcp_factory_no_instances():
    """Test that make_tool_call fails when no user instances are available."""
    import json

    # Create a mock client
    mock_client = MagicMock(spec=Client)
    mock_client.transport = MagicMock()

    # Create a mock proxy server with tools
    with patch(
        "mcp_composer.core.member_servers.layered_factory_mcp.create_proxy"
    ) as mock_create_proxy, patch(
        "mcp_composer.core.member_servers.layered_factory_mcp.get_auth_context"
    ) as mock_get_auth_context, patch(
        "mcp_composer.core.member_servers.layered_factory_mcp.AUTH_CONTEXT_AVAILABLE",
        True,
    ):
        mock_proxy = MagicMock()
        mock_tool = SimpleNamespace(name="test_tool", description="Test tool")

        # Mock list_tools to return our test tool
        mock_proxy.list_tools = AsyncMock(return_value=[mock_tool])

        mock_create_proxy.return_value = mock_proxy

        # Mock auth context with no instances
        mock_get_auth_context.return_value = {"user_instances_full": []}

        # Create the factory
        factory = LayeredMCPFactory(
            client=mock_client, server_id="test-server", product_id="test-product"
        )

        # Call make_tool_call
        result = await factory.make_tool_call("test_tool", {"arg1": "value1"})

        # Parse result
        result_dict = json.loads(result)

        # Verify authorization failed
        assert result_dict["error"] == "Unauthorized"
        assert result_dict["status_code"] == 401
        assert "No user instances available" in result_dict["message"]

        # Verify proxy.call_tool was NOT called
        mock_proxy.call_tool.assert_not_called()


@pytest.mark.asyncio
async def test_layered_mcp_factory_without_auth_context():
    """Test that make_tool_call works when auth context is not available."""
    # Create a mock client
    mock_client = MagicMock(spec=Client)
    mock_client.transport = MagicMock()
    mock_result = MagicMock()
    mock_content = MagicMock()
    mock_content.text = "Tool execution without auth"
    mock_result.content = [mock_content]

    # Create a mock proxy server with tools
    with patch(
        "mcp_composer.core.member_servers.layered_factory_mcp.create_proxy"
    ) as mock_create_proxy, patch(
        "mcp_composer.core.member_servers.layered_factory_mcp.AUTH_CONTEXT_AVAILABLE",
        False,
    ):
        mock_proxy = MagicMock()
        mock_tool = SimpleNamespace(name="test_tool", description="Test tool")

        # Mock list_tools to return our test tool
        mock_proxy.list_tools = AsyncMock(return_value=[mock_tool])

        # Mock call_tool to return our result
        mock_proxy.call_tool = AsyncMock(return_value=mock_result)

        mock_create_proxy.return_value = mock_proxy

        # Create the factory
        factory = LayeredMCPFactory(client=mock_client, server_id="test-server")

        # Call make_tool_call (should skip auth check)
        result = await factory.make_tool_call("test_tool", {"arg1": "value1"})

        # Verify proxy.call_tool was called (no auth check)
        mock_proxy.call_tool.assert_called_once_with("test_tool", {"arg1": "value1"})

        # Verify result
        assert result == "Tool execution without auth"


@pytest.mark.asyncio
async def test_layered_mcp_factory_make_tool_call_proxied_tool_error():
    """Test that make_tool_call returns a JSON error on proxied ToolError."""
    import json

    mock_client = MagicMock(spec=Client)
    mock_client.transport = MagicMock()

    with patch(
        "mcp_composer.core.member_servers.layered_factory_mcp.create_proxy"
    ) as mock_create_proxy, patch(
        "mcp_composer.core.member_servers.layered_factory_mcp.AUTH_CONTEXT_AVAILABLE",
        False,
    ):
        mock_proxy = MagicMock()
        mock_tool = SimpleNamespace(name="find_jobs_by_status", description="Test tool")

        mock_proxy.list_tools = AsyncMock(return_value=[mock_tool])
        mock_proxy.call_tool = AsyncMock(
            side_effect=ToolError(
                "Tool execution failed. Please check your request and try again."
            )
        )
        mock_create_proxy.return_value = mock_proxy

        factory = LayeredMCPFactory(client=mock_client, server_id="test-server")
        result = await factory.make_tool_call("find_jobs_by_status", {"status": "open"})

        result_dict = json.loads(result)
        assert result_dict["error"] == "Tool execution failed"
        assert result_dict["tool"] == "find_jobs_by_status"
        assert "Tool execution failed" in result_dict["message"]


# Made with Bob
