import unittest
import pytest
import os
import json
from typing import Optional
from mcp_gateway.utils import ValidationError, AllServersValidator
from mcp_gateway import MCPGateway
from fastmcp import Client
import logging


class TestGateway(unittest.IsolatedAsyncioTestCase):

    SERVER_ID = "mcp-server-fetch"
    TOOL_NAME = "mcp-stock-info_search_news"
    TOOL_NAME_LIST = ["mcp-server-fetch_fetch_html"]

    async def asyncSetUp(self):
        current_dir = os.path.dirname(__file__)
        path = os.path.join(current_dir, "member_servers.json")
        # Assumes file is in the root or test dir
        with open(path, "r") as f:
            config = json.load(f)
        self.gw = MCPGateway("gateway", config)
        await self.gw.setup_member_servers()

        data_path = os.path.join(current_dir, "tools/test_data.json")
        with open(data_path, "r") as f:
            self.test_data = json.load(f)

    def test_gateway(self):
        gw = MCPGateway("gateway")
        self.assertEqual(gw.name, "gateway", "Should be gateway")

    async def test_gateway_with_config(self):
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG)
        try:
            memebers = self.gw.list_member_servers()
            print(f"All members are {memebers}")
            self.assertEqual(len(memebers), 2, "Should have 2 members")
        except ValidationError as e:
            print(f"Actual error message: {e}")
            raise  # re-raise to keep test failing for now

    async def test_get_tools(self):
        tools = await self.gw.get_tools()
        self.assertIsInstance(tools, dict)
        self.assertGreaterEqual(len(tools), 1)

    async def test_get_tools_with_server_id(self):

        tools = await self.gw.get_tools(server_id=self.SERVER_ID)
        self.assertIsInstance(tools, dict)
        self.assertGreaterEqual(len(tools), 1)

    async def test_get_tool_config_by_name(self):
        tool_config = await self.gw.get_tool_config_by_name(name=self.TOOL_NAME)
        expected_output = self.test_data["test_get_tool_config_by_name"]
        self.assertEqual(tool_config, expected_output)

    async def test_get_tool_config_by_server(self):
        tool_config = await self.gw.get_tool_config_by_server(server_id=self.SERVER_ID)
        expected_output = self.test_data["test_get_tool_config_by_server"]
        self.assertEqual(tool_config, expected_output)

    async def test_remove_tools(self):
        tool_config = await self.gw.remove_tools(name=self.TOOL_NAME_LIST)
        expected_output = self.test_data["test_remove_tools"]
        tool_config = await self.gw.get_tool_config_by_server(server_id=self.SERVER_ID)
        self.assertEqual(tool_config, expected_output)


if __name__ == "__main__":
    unittest.main()
