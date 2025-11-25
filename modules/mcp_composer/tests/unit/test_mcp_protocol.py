from unittest.mock import AsyncMock, Mock, patch

import pytest

from mcp_composer.tag.models import ToolDescriptor
from mcp_composer.tag.scanner.mcp_protocol import MCPTransportMessage, McpProtocolScanner

# pylint: disable=protected-access,too-many-public-methods,too-few-public-methods

# Import the class and other necessary components from the module
# Assuming the code above is saved in a file like 'mcp_scanner.py'
# from .mcp_scanner import McpProtocolScanner, MCPTransportMessage
# Re-define them here for the test file to be runnable in isolation:


class MockTool:
    def __init__(self, name):
        self.name = name


class Tool:
    # A simplified mock class matching the attributes used in the scanner
    def __init__(self, name, description, schema, annotations=None):
        self.name = name
        self.description = description
        self.inputSchema = schema
        self.outputSchema = {"type": "object"}
        self.annotations = annotations or {}
        self.vendor = None
        self.id = name


# --- Test Cases ---


@pytest.mark.asyncio
class TestMcpProtocolScanner:
    def setup_method(self):
        """Initialize a scanner instance for each test."""
        # Use a generic endpoint since it will be mocked anyway
        self.scanner = McpProtocolScanner("http://localhost:8000")
        # Ensure the test uses the correct level map for assertions
        self.CRITICAL_LEVEL = self.scanner.LEVEL_MAP["CRITICAL"]
        self.LOW_LEVEL = self.scanner.LEVEL_MAP["LOW"]
        self.MEDIUM_LEVEL = self.scanner.LEVEL_MAP["MEDIUM"]

    ## ------------------------------------------------------------------
    ## Test Cases for _classify_tool and _determine_risk_level
    ## ------------------------------------------------------------------

    def test_classify_tool_destructive(self):
        """Test classification for a destructive tool."""
        mock_tool = Tool(name="delete_user", description="permanently destroy data.", schema={})
        classification = self.scanner._classify_tool(mock_tool)
        assert classification["Destructive"][0] is True
        assert self.scanner._determine_risk_level(classification) == self.CRITICAL_LEVEL

    def test_classify_tool_private_data_only(self):
        """Test classification for a Private Data source only."""
        mock_tool = Tool(name="get_secrets", description="fetch private user data.", schema={})
        classification = self.scanner._classify_tool(mock_tool)
        assert classification["Private Data"][0] is True
        assert self.scanner._determine_risk_level(classification) == self.MEDIUM_LEVEL

    def test_classify_tool_public_sink_only(self):
        """Test classification for a Public Sink only."""
        mock_tool = Tool(name="upload_file", description="send data to external server.", schema={})
        classification = self.scanner._classify_tool(mock_tool)
        assert classification["Public Sink"][0] is True
        assert self.scanner._determine_risk_level(classification) == self.MEDIUM_LEVEL

    def test_classify_tool_critical_leak(self):
        """Test classification for a tool that is both Private Data and Public Sink (Critical Leak)."""
        mock_tool = Tool(
            name="log_data",
            description="read private logs and send to external http request.",
            schema={},
        )
        classification = self.scanner._classify_tool(mock_tool)
        assert classification["Private Data"][0] is True
        assert classification["Public Sink"][0] is True
        assert self.scanner._determine_risk_level(classification) == self.CRITICAL_LEVEL

    def test_classify_tool_low_risk(self):
        """Test classification for a benign tool."""
        mock_tool = Tool(name="calculate_sum", description="compute two numbers.", schema={})
        classification = self.scanner._classify_tool(mock_tool)
        assert classification["Destructive"][0] is False
        assert self.scanner._determine_risk_level(classification) == self.LOW_LEVEL

    def test_scan_tool_output_format(self):
        """Test the final output format of _scan_tool."""
        mock_tool = Tool(name="calculate_sum", description="compute two numbers.", schema={})
        report = self.scanner._scan_tool(mock_tool)
        assert report["Level"] == self.LOW_LEVEL
        assert report["Private Data"] == "❌ NO (File/DB Read or Secret Access Operation)"
        assert "✅ YES" not in report["Destructive"]

    ## ------------------------------------------------------------------
    ## Test Cases for _get_server_info (Complex Streaming Mock)
    ## ------------------------------------------------------------------

    @pytest.mark.asyncio
    @patch("mcp_composer.tag.scanner.mcp_protocol.Client")
    async def test_get_tools_list_success(self, MockClient):
        """Test successful tools list retrieval by mocking the fastmcp Client."""

        # 1. Define the tools the client should return
        mock_tools_list = [MockTool(name="tool1"), MockTool(name="tool2")]

        # 2. Mock the client instance's list_tools method to be asynchronous
        #    and return the mock tools list.
        mock_client_instance = MockClient.return_value
        mock_client_instance.list_tools = AsyncMock(return_value=mock_tools_list)

        # 3. Instantiate the scanner and manually set the mocked client
        #    (In real code, this would happen in _collect_all, but we mock it here for isolation)
        scanner = McpProtocolScanner("http://localhost:8000")
        scanner.client = mock_client_instance

        # --- Execution ---
        tools = await scanner._get_tools_list()

        # --- Assertions ---
        # 1. Assert the mocked method was called
        mock_client_instance.list_tools.assert_awaited_once()

        # 2. Assert the correct number of tools was returned
        assert len(tools) == 2

        # 3. Assert the tool properties match the mocked data
        assert tools[0].name == "tool1"
        assert tools[1].name == "tool2"

    @patch("httpx.AsyncClient")
    async def test_get_server_info_fallback(self, MockAsyncClient):
        """Test server info retrieval when all endpoints fail."""

        # 1. Mock the client instance
        mock_client_instance = MockAsyncClient.return_value.__aenter__.return_value

        # 2. Configure the stream to raise a generic exception (e.g., Timeout, Connection Refused)
        mock_client_instance.stream.side_effect = Exception("Mocked Network Failure")

        # --- Execution ---
        info = await self.scanner._get_server_info()

        # --- Assertions ---
        # Assert that the function returned the hardcoded fallback value
        assert info["name"] == "mcp-server"
        assert info["version"] == "1.0.0"
        assert info["capabilities"] == {}

        # The loop iterates over all 4 endpoints before hitting the fallback
        assert mock_client_instance.stream.call_count == 4

    ## ------------------------------------------------------------------
    ## Test Cases for _get_tools_list
    ## ------------------------------------------------------------------

    @patch("mcp_composer.tag.scanner.mcp_protocol.Client")  # Adjust patch path as necessary
    async def test_get_tools_list_failure(self, MockClient):
        """Test tool retrieval failure via the Client object."""

        # Mock the session instance
        mock_session_instance = MockClient.return_value
        # Mock the list_tools method to raise an exception
        mock_session_instance.list_tools = AsyncMock(side_effect=Exception("API Error"))

        # Set the mocked session on the scanner (after HTTP fails)
        self.scanner.session = mock_session_instance

        # Mock httpx.get to fail so it falls back to session
        with patch("httpx.get", side_effect=Exception("HTTP Error")):
            # --- Execution ---
            tools = await self.scanner._get_tools_list()

            # --- Assertions ---
            assert tools == []  # Expect empty list on exception

    ## ------------------------------------------------------------------
    ## Test Cases for _convert_to_tool_descriptor
    ## ------------------------------------------------------------------

    def test_convert_to_tool_descriptor_basic(self):
        """Test conversion of a basic Tool object."""
        mock_tool = Tool(name="api_tool", description="a public api.", schema={"type": "object"})
        mock_server_info = {"name": "vendor-server", "version": "2.0"}

        descriptor = self.scanner._convert_to_tool_descriptor(mock_tool, mock_server_info)

        assert isinstance(descriptor, ToolDescriptor)
        assert descriptor.name == "api_tool"
        assert descriptor.vendor == "vendor-server"
        assert descriptor.scan_report["Level"] == self.LOW_LEVEL
        assert descriptor.annotations["server_version"] == "2.0"
        assert descriptor.annotations["mcp_protocol"] is True

    ## ------------------------------------------------------------------
    ## Test Cases for _collect_all (Integration Mock)
    ## ------------------------------------------------------------------

    @patch.object(McpProtocolScanner, "_get_tools_list", new_callable=AsyncMock)
    @patch.object(McpProtocolScanner, "_get_server_info", new_callable=AsyncMock)
    @patch.object(McpProtocolScanner, "_create_mcp_client")
    @patch("asyncio.run")
    def test_collect_entry_point(self, mock_async_run, mock_create_client, mock_server_info, mock_tools_list):
        """Test the main public entry point 'collect'."""

        # Setup: Mock the return value of asyncio.run to avoid actual async execution in this sync test
        mock_async_run.return_value = [Mock(spec=ToolDescriptor)]

        # Execute
        result = self.scanner.collect()

        # Assertions
        mock_create_client.assert_called_once()
        mock_async_run.assert_called_once()
        assert isinstance(result, list)

        # Test endpoint modification for http
        scanner_http = McpProtocolScanner("http://test.com", transport="http")
        scanner_http.collect()
        assert scanner_http.endpoint == "http://test.com/mcp"
