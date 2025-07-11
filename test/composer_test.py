"""MCP Composer unit test"""

import unittest
import logging
import os
import json
from unittest.mock import MagicMock, patch
from fastmcp.tools.tool import Tool

from mcp_composer.member_servers.member_server import HealthStatus
from mcp_composer.utils import ValidationError
from mcp_composer import MCPComposer
from mcp_composer.store.database import DatabaseInterface
from mcp_composer.utils.custom_tool import DynamicToolGenerator, OpenApiTool


class TestData:
    """MCP Composer test data"""

    SERVER_ID = "mcp-server-fetch"
    TOOL_NAME_1 = "mcp-stock-info_search_news"
    TOOL_NAME_2 = "mcp-server-fetch_fetch_html"
    TOOL_NAME_LIST = ["mcp-server-fetch_fetch_html"]
    TOOL_NAME_WITHOUT_PREFIX = "search_news"
    TOOL_DESCRIPTION = "Test description"


class TestComposer(unittest.IsolatedAsyncioTestCase):
    """MCP Composer test cases"""

    async def asyncSetUp(self):
        current_dir = os.path.dirname(__file__)
        path = os.path.join(current_dir, "data/member_servers.json")
        # Assumes file is in the root or test dir
        with open(path, "r") as f:
            config = json.load(f)
        self.fake_db = MagicMock(spec=DatabaseInterface)
        self.fake_db.load_all_servers.return_value = config
        self.gw = MCPComposer("composer", database_config=self.fake_db)
        await self.gw.setup_member_servers()

        data_path = os.path.join(current_dir, "data/tools_data.json")
        with open(data_path, "r") as f:
            self.test_data = json.load(f)

    def test_composer(self):
        """Test mcp composer instance created"""
        gw = MCPComposer("composer")
        self.assertEqual(gw.name, "composer", "Should be composer")

    async def test_composer_with_config(self):
        """Test member servers mounted successfully"""
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG)
        try:
            members = self.gw._server_manager.list_member_servers()
            logger.info(f"All members are {members}")
            self.assertEqual(len(members), 2, "Should have 2 members")
        except ValidationError as e:
            logger.info(f"Actual error message: {e}")
            raise  # re-raise to keep test failing for now

    async def test_get_tools(self):
        """Make sure the composer returns the list of tools"""
        tools = await self.gw.get_tools()
        self.assertIsInstance(tools, dict)
        self.assertGreaterEqual(len(tools), 1)

    async def test_member_health(self):
        """Ensure composer returns the health status of a member server"""
        health_statuses = [item["status"] for item in await self.gw.member_health()]
        self.assertEqual(health_statuses, [HealthStatus.healthy, HealthStatus.healthy])

    @patch.object(DynamicToolGenerator, "_ensure_base_file")
    @patch.object(DynamicToolGenerator, "_write_function_to_file")
    async def test_generate_tool_from_script(
        self, mock_write_function, mock_ensure_base_file
    ):
        """Ensure the tools are created successfully using a cURL command and a Python script."""
        script_input = {
            "name": "sum",
            "tool_type": "script",
            "script_config": {"value": "def sum(a, b): return a + b"},
            "description": "sample sum",
            "permission": {"role 1": "permission 1 "},
        }
        curl_input = {
            "name": "event_test",
            "tool_type": "curl",
            "curl_config": {
                "value": "curl 'https://www.eventbriteapi.com/v3/users/me/organizations/' --header 'Authorization: Bearer <edit-me>'"
            },
            "description": "sample test",
            "permission": {"role 1": "permission 1 "},
        }

        await self.gw.add_tools(script_input)
        mock_ensure_base_file._ensure_base_file()
        mock_write_function.assert_called_with(
            script_input["name"], script_input["script_config"]["value"]
        )

        await self.gw.add_tools(curl_input)
        tools = await self.gw.get_tools()
        self.assertIsInstance(tools.get("sum"), Tool)
        self.assertIsInstance(tools.get("event_test"), Tool)

    @patch.object(OpenApiTool, "_ensure_base_file")
    @patch.object(OpenApiTool, "write_openapi")
    async def test_generate_tool_from_openapi(
        self, mock_write_function, mock_ensure_base_file
    ):
        """Ensure the tools are created successfully using a OpenAPI specification."""
        await self.gw.add_tools_from_openapi(self.test_data["openapi_input"])
        mock_ensure_base_file._ensure_base_file()
        mock_write_function.write_openapi()
        tools = await self.gw.get_tools()
        self.assertIsInstance(tools.get("HelloWorld_API_get_greeting"), Tool)


if __name__ == "__main__":
    unittest.main()
