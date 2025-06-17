import unittest
import os
import json
from unittest.mock import MagicMock

from mcp_composer import MCPComposer
from mcp_composer.store.database import DatabaseInterface
from test.composer_test import TestData


class TestTool(unittest.IsolatedAsyncioTestCase):
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

    async def test_get_tools_with_server_id(self):
        tools = await self.gw.get_tools(server_id=TestData.SERVER_ID)
        self.assertIsInstance(tools, dict)
        self.assertGreaterEqual(len(tools), 1)

    async def test_get_tool_config_by_name(self):
        tool_config = await self.gw._tool_manager.get_tool_config_by_name(
            name=TestData.TOOL_NAME_1
        )
        self.assertEqual(tool_config[0]["name"], TestData.TOOL_NAME_WITHOUT_PREFIX)

    async def test_get_tool_config_by_server(self):
        tool_config = await self.gw._tool_manager.get_tool_config_by_server(
            server_id=TestData.SERVER_ID
        )
        self.assertEqual(len(tool_config), 4)

    async def test_remove_tools(self):
        tool_config = await self.gw._tool_manager.remove_tools(
            tools=TestData.TOOL_NAME_LIST, server_id=TestData.SERVER_ID
        )
        self.fake_db.get_document.return_value = self.test_data[
            "mock_server_config_after_tool_remove"
        ]
        tool_config = await self.gw._tool_manager.get_tool_config_by_server(
            server_id=TestData.SERVER_ID
        )
        self.assertEqual(len(tool_config), 3)

    async def test_update_tool_description(self):
        await self.gw._tool_manager.update_tool_description(
            tool=TestData.TOOL_NAME_2,
            description=TestData.TOOL_DESCRIPTION,
            server_id=TestData.SERVER_ID,
        )
        self.fake_db.load_all_servers.return_value = self.test_data[
            "mock_update_tool_description"
        ]
        tool_config = await self.gw._tool_manager.get_tool_config_by_name(
            name=TestData.TOOL_NAME_2
        )
        self.assertEqual(tool_config[0]["description"], TestData.TOOL_DESCRIPTION)
