"""MCP Composer tool management test"""
import os
import unittest
import json
from unittest.mock import MagicMock, patch
from .composer_test import TestData
from mcp_composer.core.composer import MCPComposer
from mcp_composer.store.database import DatabaseInterface
from mcp_composer.core.utils.exceptions import MemberServerError
from fastmcp.exceptions import ToolError
class TestTool(unittest.IsolatedAsyncioTestCase):
    """MCP Composer tool management test cases"""
    async def asyncSetUp(self):
        current_dir = os.path.dirname(__file__)
        path = os.path.join(current_dir, "./../data/member_servers.json")
        # Assumes file is in the root or test dir
        with open(path, "r") as f:
            config = json.load(f)
        self.fake_db = MagicMock(spec=DatabaseInterface)
        self.fake_db.load_all_servers.return_value = config
        self.gw = MCPComposer("composer", database_config=self.fake_db)
        await self.gw.setup_member_servers()
        data_path = os.path.join(current_dir, "./../data/tools_data.json")
        with open(data_path, "r") as f:
            self.test_data = json.load(f)
    async def test_get_tools_with_server_id(self):
        """Verify the tools associated with the member server."""
        tools = await self.gw._tool_manager.get_all_tools(server_id=TestData.SERVER_ID)
        self.assertIsInstance(tools, dict)
        self.assertGreaterEqual(len(tools), 1)
    async def test_get_tool_config_by_name(self):
        """Ensure tool config can be retrieved using tool name"""
        tool_config = await self.gw._tool_manager.get_tool_config_by_name(
            name=TestData.TOOL_NAME_1
        )
        self.assertEqual(tool_config[0]["name"], TestData.TOOL_NAME_1)
    async def test_get_tool_config_by_server(self):
        """Ensure tool config can be retrieved using server id"""
        tool_config = await self.gw._tool_manager.get_tool_config_by_server(
            server_id=TestData.SERVER_ID
        )
        self.assertEqual(len(tool_config), 4)
    async def test_disable_tools_by_server(self):
        """Ensure tool disabled for the member server"""
        tool_config = await self.gw._tool_manager.disable_tools_by_server(
            tools=TestData.TOOL_NAME_LIST, server_id=TestData.SERVER_ID
        )
        self.fake_db.get_document.return_value = self.test_data[
            "mock_server_config_after_tool_remove"
        ]
        tool_config = await self.gw._tool_manager.get_tool_config_by_server(
            server_id=TestData.SERVER_ID
        )
        self.assertEqual(len(tool_config), 3)
    async def test_enable_tools_by_server(self):
        """Ensure tool enabled for the member server"""
        tool_config = await self.gw._tool_manager.disable_tools_by_server(
            tools=TestData.TOOL_NAME_LIST, server_id=TestData.SERVER_ID
        )
        tool_config = await self.gw._tool_manager.enable_tools_by_server(
            tools=TestData.TOOL_NAME_LIST, server_id=TestData.SERVER_ID
        )
        tool_config = await self.gw._tool_manager.get_tool_config_by_server(
            server_id=TestData.SERVER_ID
        )
        self.assertEqual(len(tool_config), 4)
    async def test_disable_tools(self):
        """Ensure tool disabled for the member server"""
        tool_config = await self.gw._tool_manager.disable_tools(
            tools=TestData.TOOL_NAME_LIST
        )
        self.fake_db.get_document.return_value = self.test_data[
            "mock_server_config_after_tool_remove"
        ]
        # Mock the server's get_tools method to avoid HTTP calls
        mock_tools = {
            "fetch_html": MagicMock(name="fetch_html"),
            "fetch_markdown": MagicMock(name="fetch_markdown"),
            "fetch_txt": MagicMock(name="fetch_txt"),
            "fetch_json": MagicMock(name="fetch_json")
        }
        # Find the mounted server and mock its get_tools method
        for mounted_server in self.gw._tool_manager._mounted_servers:
            if mounted_server.prefix == TestData.SERVER_ID:
                async def mock_get_tools():
                    return mock_tools
                mounted_server.server.get_tools = mock_get_tools
                break
        tool_config = await self.gw._tool_manager.get_tool_config_by_server(
            server_id=TestData.SERVER_ID
        )
        self.assertEqual(len(tool_config), 3)
    async def test_enable_tools(self):
        """Ensure tool enabled for the member server"""
        tool_config = await self.gw._tool_manager.disable_tools(
            tools=TestData.TOOL_NAME_LIST
        )
        tool_config = await self.gw._tool_manager.enable_tools(
            tools=TestData.TOOL_NAME_LIST
        )
        # Mock the server's get_tools method to avoid HTTP calls
        mock_tools = {
            "fetch_html": MagicMock(name="fetch_html"),
            "fetch_markdown": MagicMock(name="fetch_markdown"),
            "fetch_txt": MagicMock(name="fetch_txt"),
            "fetch_json": MagicMock(name="fetch_json")
        }
        # Find the mounted server and mock its get_tools method
        for mounted_server in self.gw._tool_manager._mounted_servers:
            if mounted_server.prefix == TestData.SERVER_ID:
                async def mock_get_tools():
                    return mock_tools
                mounted_server.server.get_tools = mock_get_tools
                break
        tool_config = await self.gw._tool_manager.get_tool_config_by_server(
            server_id=TestData.SERVER_ID
        )
        self.assertEqual(len(tool_config), 4)
    async def test_update_tool_description(self):
        """Ensure that the tool description for the member server has been updated."""
        await self.gw._tool_manager.update_tool_description(
            tool=TestData.TOOL_NAME_2,
            description=TestData.TOOL_DESCRIPTION,
            server_id=TestData.SERVER_ID,
        )
        # Mock the server's get_tools method to avoid HTTP calls
        mock_tools = {
            "fetch_html": MagicMock(name="fetch_html"),
            "fetch_markdown": MagicMock(name="fetch_markdown"),
            "fetch_txt": MagicMock(name="fetch_txt"),
            "fetch_json": MagicMock(name="fetch_json")
        }
        # Find the mounted server and mock its get_tools method
        for mounted_server in self.gw._tool_manager._mounted_servers:
            if mounted_server.prefix == TestData.SERVER_ID:
                async def mock_get_tools():
                    return mock_tools
                mounted_server.server.get_tools = mock_get_tools
                break
        # Test the fetch_server_tools method directly with description updates
        server = self.gw._server_manager.get(TestData.SERVER_ID)
        description_updates = {TestData.TOOL_NAME_2: TestData.TOOL_DESCRIPTION}
        tools = await self.gw._tool_manager.fetch_server_tools(server, [], description_updates)
        # Verify that the tool description was updated
        self.assertEqual(tools[TestData.TOOL_NAME_2].description, TestData.TOOL_DESCRIPTION)
    async def test_server_registration_with_missing_tool_descriptions(self):
        """Ensure that servers with tools missing descriptions cannot be registered."""
        # Test with server that has missing tool descriptions
        server_config = self.test_data["server_with_missing_descriptions"]
        with self.assertRaises(ToolError) as context:
            await self.gw.register_mcp_server(server_config)
        self.assertIn("Failed to register server: Tools missing descriptions:", str(context.exception))
        self.assertIn("get_ticker_info", str(context.exception))
        self.assertIn("get_ticker_news", str(context.exception))
        self.assertIn("income_statement", str(context.exception))
    async def test_server_registration_with_valid_tool_descriptions(self):
        """Ensure that servers with valid tool descriptions can be registered."""
        # Test with server that has valid tool descriptions but different ID to avoid conflicts
        server_config = self.test_data["server_with_valid_descriptions"].copy()
        server_config["id"] = "mcp-server-fetch-test"  # Use different ID to avoid conflict
        # Mock the server registration to avoid actual network calls
        with patch.object(self.gw._server_manager, '_mount_and_register_server') as mock_register:
            mock_register.return_value = "Server registered successfully"
            result = await self.gw.register_mcp_server(server_config)
            self.assertEqual(result, "Server registered successfully")
            mock_register.assert_called_once()
