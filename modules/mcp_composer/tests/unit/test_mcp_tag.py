from unittest.mock import patch

import pytest
from mcp import Tool

from mcp_composer.tag.models import ToolDescriptor
from mcp_composer.tag.scanner.mcp_protocol import McpProtocolScanner

# pylint: disable=protected-access


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
        # pass dict directly (converter handles dicts)
        descriptor = scanner._convert_to_tool_descriptor(Tool(**tool_data), server_info)

        assert isinstance(descriptor, ToolDescriptor)
        assert descriptor.id == "test_tool"
        assert descriptor.name == "test_tool"
        assert descriptor.description == "A test tool"
        assert descriptor.vendor == "test-server"
        assert descriptor.endpoint == "http://localhost:8000"
        assert descriptor.annotations["mcp_protocol"] is True
        assert descriptor.annotations["server_name"] == "test-server"

    @pytest.mark.asyncio
    @patch("httpx.get")
    async def test_get_server_info_fallback(self, mock_get):
        """Test server info fallback when endpoints fail"""
        mock_get.side_effect = Exception("Connection failed")

        scanner = McpProtocolScanner("http://localhost:8000")
        info = await scanner._get_server_info()

        assert info["name"] == "mcp-server"
        assert info["version"] == "1.0.0"

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
