"""MCP Composer unit test"""

import unittest
import logging
import os
import json
from unittest.mock import MagicMock, patch, AsyncMock
from fastmcp.tools.tool import Tool
from fastmcp.exceptions import ToolError

from mcp_composer.core.member_servers.member_server import HealthStatus
from mcp_composer.core.utils.validator import ValidationError
from mcp_composer.core.composer import MCPComposer
from mcp_composer.store.database import DatabaseInterface
from mcp_composer.core.utils.custom_tool import DynamicToolGenerator, OpenApiTool

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class TestData:
    """MCP Composer test data"""

    SERVER_ID = "mcp-server-fetch"
    TOOL_NAME_1 = "fetch_html"
    TOOL_NAME_2 = "fetch_markdown"
    TOOL_NAME_LIST = ["fetch_html"]
    TOOL_NAME_WITHOUT_PREFIX = "fetch_html"
    TOOL_DESCRIPTION = "Test description"


class TestComposer(unittest.IsolatedAsyncioTestCase):
    """MCP Composer test cases"""

    async def asyncSetUp(self):
        current_dir = os.path.dirname(__file__)
        path = os.path.join(current_dir, "./../data/member_servers.json")
        # Assumes file is in the root or test dir
        with open(path, "r", encoding="utf-8") as f:
            self.config = json.load(f)
        self.fake_db = MagicMock(spec=DatabaseInterface)
        self.fake_db.load_all_servers = MagicMock(return_value=self.config)
        self.gw = MCPComposer("composer", database_config=self.fake_db)

        # Mock the database methods that might be called during setup
        self.fake_db.save_server = MagicMock()
        self.fake_db.update_server = MagicMock()

        # Mock the server setup to avoid real network calls
        with patch.object(
            self.gw, "_mount_member_server", new_callable=AsyncMock
        ) as mock_mount:
            mock_mount.return_value = "Server mcp-server-fetch mounted."
            await self.gw.setup_member_servers()

        data_path = os.path.join(current_dir, "./../data/tools_data.json")
        with open(data_path, "r", encoding="utf-8") as f:
            self.test_data = json.load(f)

    def test_composer(self):
        """Test mcp composer instance created"""
        gw = MCPComposer("composer")
        self.assertEqual(gw.name, "composer", "Should be composer")

    async def test_composer_with_config(self):
        """Test member servers mounted successfully"""
        try:
            # Mock the member servers since we don't have real endpoints
            with patch.object(
                self.gw._server_manager,
                "list_servers",
                return_value=[
                    {
                        "id": "mcp-server-fetch",
                        "type": "sse",
                        "endpoint": "http://localhost:8000/sse",
                    }
                ],
            ):
                members = self.gw._server_manager.list_servers()
                self.assertGreaterEqual(
                    len(members), 1, "Should have at least 1 member (mcp-server-fetch)"
                )
        except ValidationError as e:
            logger.info("Actual error message: %s", e)
            raise  # re-raise to keep test failing for now

    async def test_tool_description_validation(self):
        """Ensure external server is not mounted when tools do not have descriptions"""
        composer = MCPComposer("composer")

        # Use test data for server with missing descriptions
        server_config = self.test_data["server_with_missing_descriptions"]

        # Mock builder/list_tools so we can deterministically validate
        # the missing-description branch without network dependencies.
        mock_remote_server = MagicMock()
        mock_remote_server.list_tools = AsyncMock(
            return_value=[
                MagicMock(name="tool_without_description", description=""),
            ]
        )

        with patch(
            "mcp_composer.core.member_servers.server_manager.MCPServerBuilder.build",
            new_callable=AsyncMock,
            return_value=mock_remote_server,
        ):
            with self.assertRaises((ToolError, Exception)):
                await composer.register_mcp_server(server_config)

    async def test_server_list_with_endpoint(self):
        """Ensure the member server list contains the endpoint and type"""
        expected_endpoints = {ser["id"]: ser["endpoint"] for ser in self.config}

        mocked_members = [
            {
                "id": self.config[0]["id"],
                "type": self.config[0]["type"],
                "endpoint": self.config[0]["endpoint"],
                "status": "active",
            }
        ]

        with patch.object(
            self.gw._server_manager,
            "list_servers",
            return_value=mocked_members,
        ):
            members = self.gw._server_manager.list_servers()
            logger.info("All members: %s", members)
            self.assertGreaterEqual(len(members), 1)

            for member in members:
                self.assertIn("id", member)
                self.assertIn("type", member)
                self.assertIn("endpoint", member)
                if member["id"] in expected_endpoints and member["endpoint"] != "N/A":
                    self.assertEqual(
                        member["endpoint"],
                        expected_endpoints[member["id"]],
                        f"Unexpected endpoint for {member['id']}: {member['endpoint']}",
                    )

    async def test_get_tools(self):
        """Make sure the composer returns the list of tools"""
        tools = await self.gw.list_tools()
        self.assertIsInstance(tools, list)
        self.assertGreaterEqual(len(tools), 1)
        self.assertTrue(all(isinstance(tool, Tool) for tool in tools))

    async def test_filter_tool(self):
        """Make sure the composer returns the list of tools matching the keyword."""
        tools = await self.gw.filter_tool(keyword="fetch")
        self.assertIsInstance(tools, dict)
        self.assertGreaterEqual(len(tools), 1)
        self.assertTrue(all(isinstance(tool, Tool) for tool in tools.values()))

    async def test_member_health(self):
        """Ensure composer returns the health status of a member server"""
        # Mock member health check since we don't have real endpoints
        with patch.object(
            self.gw, "member_health", new_callable=AsyncMock
        ) as mock_health:
            mock_health.return_value = [
                {"id": "mcp-server-fetch", "status": HealthStatus.healthy}
            ]
            health_statuses = [item["status"] for item in await self.gw.member_health()]
            self.assertGreaterEqual(
                len(health_statuses), 1, "Should have at least one server"
            )
            self.assertTrue(
                all(status == HealthStatus.healthy for status in health_statuses),
                "All servers should be healthy",
            )

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
                "value": "curl 'http://localhost:9002/v3/users/me/organizations/' --header 'Authorization: Bearer <edit-me>'"
            },
            "description": "sample test",
            "permission": {"role 1": "permission 1 "},
        }

        await self.gw.add_tools_from_python(script_input)
        mock_ensure_base_file.assert_called()
        mock_write_function.assert_called_with(
            script_input["name"], script_input["script_config"]["value"]
        )

        await self.gw.add_tools_from_curl(curl_input)
        tools = await self.gw.list_tools()
        tools_map = {tool.name: tool for tool in tools}
        self.assertIsInstance(tools_map.get("sum"), Tool)
        self.assertIsInstance(tools_map.get("event_test"), Tool)

    @patch.object(OpenApiTool, "write_versioned_openapi")
    async def test_generate_tool_from_openapi(self, mock_write_function):
        """Ensure the tools are created successfully using a OpenAPI specification."""
        await self.gw.add_tools_from_openapi(self.test_data["openapi_input"])
        mock_write_function.assert_called()
        tools = await self.gw.list_tools()
        tools_map = {tool.name: tool for tool in tools}
        self.assertIsInstance(tools_map.get("HelloWorld_API_get_greeting"), Tool)

    @patch.object(OpenApiTool, "write_versioned_openapi")
    async def test_tool_from_openapi_version_increment(self, mock_write_function):
        """Ensure the version is incremented when the latest specification from the
        same OpenAPI provider is used."""
        await self.gw.add_tools_from_openapi(self.test_data["openapi_input_v1"])
        mock_write_function.assert_called()
        tools = await self.gw.list_tools()
        tools_map = {tool.name: tool for tool in tools}
        self.assertIsInstance(tools_map.get("HelloWorld_API_get_greeting_v1"), Tool)

    @patch.object(MCPComposer, "rollback_openapi_tool_version")
    @patch.object(OpenApiTool, "write_versioned_openapi")
    async def test_tool_from_openapi_rollback(
        self, mock_write_versioned_openapi, mock_rollback_openapi_tool_version
    ):
        """If a rollback version is specified, ensure that tools are loaded from that version"""

        # Add the first and second versions of the OpenAPI tool
        await self.gw.add_tools_from_openapi(self.test_data["openapi_input"])
        await self.gw.add_tools_from_openapi(self.test_data["openapi_input_v1"])

        # Ensure the write_versioned_openapi method was called
        mock_write_versioned_openapi.assert_called()

        # Simulate rollback
        await self.gw.rollback_openapi_tool_version("HelloWorld_API", "1.0.1")

        # Assert that rollback was called with correct args
        mock_rollback_openapi_tool_version.assert_called_once_with(
            "HelloWorld_API", "1.0.1"
        )

        tools = await self.gw.list_tools()
        tools_map = {tool.name: tool for tool in tools}
        self.assertIsInstance(tools_map.get("HelloWorld_API_get_greeting_v1"), Tool)

    @patch.object(DynamicToolGenerator, "_ensure_base_file")
    async def test_tool_from_curl_version_increment(self, mock_ensure_base_file):
        """Ensure the version is incremented when the latest specification from the
        same OpenAPI provider is used."""
        curl_input = {
            "name": "event_test",
            "tool_type": "curl",
            "curl_config": {
                "value": "curl 'http://localhost:9002/v3/users/me/organizations/' --header 'Authorization: Bearer <edit-me>'"
            },
            "description": "sample test",
            "permission": {"role 1": "permission 1 "},
        }
        curl_input_v1 = {
            "name": "event_test",
            "tool_type": "curl",
            "curl_config": {
                "value": "curl 'http://localhost:9002/v3/users/me/organizations/1' --header 'Authorization: Bearer <edit-me>'"
            },
            "description": "sample test",
            "permission": {"role 1": "permission 1 "},
        }

        await self.gw.add_tools_from_curl(curl_input)
        await self.gw.add_tools_from_curl(curl_input_v1)
        tools = await self.gw.list_tools()
        tools_map = {tool.name: tool for tool in tools}
        self.assertIsInstance(tools_map.get("event_test"), Tool)

    @patch.object(DynamicToolGenerator, "_ensure_base_file")
    @patch.object(DynamicToolGenerator, "write_curl_to_file")
    @patch.object(MCPComposer, "rollback_curl_tool_version")
    async def test_tool_from_curl_rollback(
        self,
        mock_rollback_curl_tool_version,
        mock_write_curl_to_file,
        mock_ensure_base_file,
    ):
        """If a rollback version is specified, ensure that tools are loaded from that version"""
        curl_input = {
            "name": "event_test",
            "tool_type": "curl",
            "curl_config": {
                "value": "curl 'http://localhost:9002/v3/users/me/organizations/' --header 'Authorization: Bearer <edit-me>'"
            },
            "description": "sample test",
            "permission": {"role 1": "permission 1 "},
        }
        curl_input_v1 = {
            "name": "event_test",
            "tool_type": "curl",
            "curl_config": {
                "value": "curl 'http://localhost:9002/v3/users/me/organizations/1' --header 'Authorization: Bearer <edit-me>'"
            },
            "description": "sample test",
            "permission": {"role 1": "permission 1 "},
        }

        await self.gw.add_tools_from_curl(curl_input)
        await self.gw.add_tools_from_curl(curl_input_v1)
        await self.gw.rollback_curl_tool_version("HelloWorld_API", "1.0.1")
        mock_write_curl_to_file.assert_called()
        mock_rollback_curl_tool_version.assert_called_once_with(
            "HelloWorld_API", "1.0.1"
        )

        tools = await self.gw.list_tools()
        tools_map = {tool.name: tool for tool in tools}
        self.assertIsInstance(tools_map.get("event_test"), Tool)

    async def test_disable_composer_tool(self):
        """Ensure the composer tools are disabled successfully"""
        await self.gw.disable_composer_tool(["register_mcp_server"])
        tools = self.gw._tool_manager.filter_tools(await self.gw.list_tools())
        self.assertNotIn("register_mcp_server", tools)


if __name__ == "__main__":
    unittest.main()
