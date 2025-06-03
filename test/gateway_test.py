import unittest
import logging
import os
import json
from unittest.mock import MagicMock

from mcp_gateway.utils import ValidationError
from mcp_gateway import MCPGateway
from mcp_gateway.store.database import DatabaseInterface


class TestData:
    SERVER_ID = "mcp-server-fetch"
    TOOL_NAME_1 = "mcp-stock-info_search_news"
    TOOL_NAME_2 = "mcp-server-fetch_fetch_html"
    TOOL_NAME_LIST = ["mcp-server-fetch_fetch_html"]
    TOOL_DESCRIPTION = "Test description"


class TestGateway(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        current_dir = os.path.dirname(__file__)
        path = os.path.join(current_dir, "member_servers.json")
        # Assumes file is in the root or test dir
        with open(path, "r") as f:
            config = json.load(f)
        self.fake_db = MagicMock(spec=DatabaseInterface)
        self.fake_db.load_all_servers.return_value = config
        self.gw = MCPGateway("gateway", database_config=self.fake_db)
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
        tools = await self.gw.get_tools(server_id=TestData.SERVER_ID)
        self.assertIsInstance(tools, dict)
        self.assertGreaterEqual(len(tools), 1)

    async def test_get_tool_config_by_name(self):
        tool_config = await self.gw.get_tool_config_by_name(name=TestData.TOOL_NAME_1)
        expected_output = self.test_data["test_get_tool_config_by_name"]
        self.assertEqual(tool_config, expected_output)

    async def test_get_tool_config_by_server(self):
        tool_config = await self.gw.get_tool_config_by_server(
            server_id=TestData.SERVER_ID
        )
        expected_output = self.test_data["test_get_tool_config_by_server"]
        self.assertEqual(tool_config, expected_output)

    async def test_remove_tools(self):
        tool_config = await self.gw.remove_tools(
            tools=TestData.TOOL_NAME_LIST, server_id=TestData.SERVER_ID
        )
        expected_output = self.test_data["test_remove_tools"]
        self.fake_db.get_document.return_value = self.test_data[
            "mock_server_config_after_tool_remove"
        ]
        tool_config = await self.gw.get_tool_config_by_server(
            server_id=TestData.SERVER_ID
        )
        self.assertEqual(tool_config, expected_output)

    async def test_update_tool_description(self):
        await self.gw.update_tool_description(
            tool=TestData.TOOL_NAME_2,
            description=TestData.TOOL_DESCRIPTION,
            server_id=TestData.SERVER_ID,
        )
        self.fake_db.load_all_servers.return_value = self.test_data[
            "mock_update_tool_description"
        ]
        tool_config = await self.gw.get_tool_config_by_name(name=TestData.TOOL_NAME_2)
        self.assertEqual(tool_config[0]["description"], TestData.TOOL_DESCRIPTION)


if __name__ == "__main__":
    unittest.main()
