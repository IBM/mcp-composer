import unittest
import logging
import os
import json
from unittest.mock import MagicMock

from mcp_composer.member_servers.member_server import HealthStatus
from mcp_composer.utils import ValidationError
from mcp_composer import MCPComposer
from mcp_composer.store.database import DatabaseInterface


class TestData:
    SERVER_ID = "mcp-server-fetch"
    TOOL_NAME_1 = "mcp-stock-info_search_news"
    TOOL_NAME_2 = "mcp-server-fetch_fetch_html"
    TOOL_NAME_LIST = ["mcp-server-fetch_fetch_html"]
    TOOL_NAME_WITHOUT_PREFIX = "search_news"
    TOOL_DESCRIPTION = "Test description"


class TestComposer(unittest.IsolatedAsyncioTestCase):
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
        gw = MCPComposer("composer")
        self.assertEqual(gw.name, "composer", "Should be composer")

    async def test_composer_with_config(self):
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG)
        try:
            memebers = self.gw._server_manager.list_member_servers()
            print(f"All members are {memebers}")
            self.assertEqual(len(memebers), 2, "Should have 2 members")
        except ValidationError as e:
            print(f"Actual error message: {e}")
            raise  # re-raise to keep test failing for now

    async def test_get_tools(self):
        tools = await self.gw.get_tools()
        self.assertIsInstance(tools, dict)
        self.assertGreaterEqual(len(tools), 1)

    async def test_member_health(self):
        health_statuses = [item["status"] for item in await self.gw.member_health()]
        self.assertEqual(health_statuses, [HealthStatus.healthy, HealthStatus.healthy])


if __name__ == "__main__":
    unittest.main()
