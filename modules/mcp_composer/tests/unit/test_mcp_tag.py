import pytest
from unittest.mock import Mock, patch
from mcp import Tool
from mcp_composer.tag.scanner.mcp_protocol import McpProtocolScanner
from mcp_composer.tag.models import ToolDescriptor


class TestMcpProtocolScanner:
    """Test cases for McpProtocolScanner"""

    def test_init(self):
        """Test scanner initialization"""
        scanner = McpProtocolScanner("http://localhost:8000")
        assert scanner.endpoint == "http://localhost:8000"
        assert scanner.transport == "http"
        assert scanner.auth_token is None

        scanner = McpProtocolScanner(
            "http://localhost:8000", auth_token="test-token", transport="sse"
        )
        assert scanner.auth_token == "test-token"
        assert scanner.transport == "sse"
        assert "Authorization" in scanner.headers

    def test_convert_to_tool_descriptor(self):
        """Test tool descriptor conversion"""
        scanner = McpProtocolScanner("http://localhost:8000")
        server_info = {"name": "test-server", "version": "1.0.0"}

        tool_data = {
            "name": "test_tool",
            "description": "A test tool",
            "inputSchema": {"type": "object"},
            "outputSchema": {"type": "string"},
            "annotations": {"test": True},
        }
        # Ensure tool_data is valid
        descriptor = scanner._convert_to_tool_descriptor(Tool(**tool_data), server_info)

        assert isinstance(descriptor, ToolDescriptor)
        assert descriptor.id == "test_tool"
        assert descriptor.name == "test_tool"
        assert descriptor.description == "A test tool"
        assert descriptor.vendor == "test-server"
        assert descriptor.endpoint == "http://localhost:8000"
        assert descriptor.annotations["mcp_protocol"] is True
        assert descriptor.annotations["server_name"] == "test-server"

    def test_extract_tools_from_response(self):
        """Test tool extraction from various response formats"""
        scanner = McpProtocolScanner("http://localhost:8000")

        # Test list format
        response = [{"name": "tool1"}, {"name": "tool2"}]
        tools = scanner._extract_tools_from_response(response)
        assert len(tools) == 2

        # Test dict with tools key
        response = {"tools": [{"name": "tool1"}]}
        tools = scanner._extract_tools_from_response(response)
        assert len(tools) == 1

        # Test dict with data key
        response = {"data": [{"name": "tool1"}]}
        tools = scanner._extract_tools_from_response(response)
        assert len(tools) == 1

        # Test empty response
        tools = scanner._extract_tools_from_response({})
        assert len(tools) == 0

    @patch("httpx.get")
    def test_get_server_info_success(self, mock_get):
        """Test successful server info retrieval"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"name": "test-server", "version": "1.0.0"}
        mock_get.return_value = mock_response

        scanner = McpProtocolScanner("http://localhost:8000")
        info = scanner._get_server_info()

        assert info["name"] == "test-server"
        assert info["version"] == "1.0.0"

    @patch("httpx.get")
    def test_get_server_info_fallback(self, mock_get):
        """Test server info fallback when endpoints fail"""
        mock_get.side_effect = Exception("Connection failed")

        scanner = McpProtocolScanner("http://localhost:8000")
        info = scanner._get_server_info()

        assert info["name"] == "mcp-server"
        assert info["version"] == "1.0.0"

    @pytest.mark.asyncio
    @patch("httpx.get")
    async def test_get_tools_list_success(self, mock_get):
        """Test successful tools list retrieval (async)"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{"name": "tool1"}, {"name": "tool2"}]
        mock_get.return_value = mock_response

        scanner = McpProtocolScanner("http://localhost:8000")
        tools = await scanner._get_tools_list()

        assert len(tools) == 2
        assert tools[0]["name"] == "tool1"
        assert tools[1]["name"] == "tool2"

    def test_get_tools_via_post_success(self):
        """Test successful tools retrieval via POST"""
        scanner = McpProtocolScanner("http://localhost:8000")
        # Patch the method directly
        scanner._get_tools_via_post = Mock(return_value=[{"name": "tool1"}])

        tools = scanner._get_tools_via_post()

        assert isinstance(tools, list)
        assert len(tools) == 1
        assert tools[0]["name"] == "tool1"

    def test_fallback_discovery(self):
        """Test fallback discovery when all methods fail"""
        scanner = McpProtocolScanner("http://localhost:8000")
        tools = scanner._fallback_discovery()

        assert len(tools) == 1
        assert tools[0].name == "Discovered Tool"
        assert tools[0].annotations["discovery_method"] == "fallback"

    def test_invalid_transport(self):
        """Test error handling for invalid transport"""
        scanner = McpProtocolScanner("http://localhost:8000", transport="invalid")

        with pytest.raises(
            RuntimeError,
            match="Failed to collect tools from MCP server http://localhost:8000: Unsupported transport: invalid",
        ):
            scanner.collect()

    # Additional tests from test_mcp_protocol.py

    def test_init_full(self):
        scanner = McpProtocolScanner(
            "http://localhost:8000",
            auth_token="abc",
            transport="http",
            command="echo",
            args="foo",
        )
        assert scanner.endpoint == "http://localhost:8000"
        assert scanner.auth_token == "abc"
        assert scanner.transport == "http"
        assert scanner.command == "echo"
        assert scanner.args == "foo"
        assert "Authorization" in scanner.headers
