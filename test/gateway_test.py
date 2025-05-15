import unittest
import pytest   
import os
import json
from mcp_gateway.utils import ValidationError, AllServersValidator
from mcp_gateway import MCPGateway
from fastmcp import Client
import logging
class TestGateway(unittest.IsolatedAsyncioTestCase):

    def test_gateway(self):
        gw = MCPGateway("gateway")
        self.assertEqual(gw.name, "gateway", "Should be gateway")

    

    async def test_gateway_with_config(self):
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG)
        print("test_gateway_with_config ========")
        current_dir = os.path.dirname(__file__)
        path = os.path.join(current_dir, "member_servers.json")
        # Assumes file is in the root or test dir

        with open(path, 'r') as f:
            config= json.load(f)

        
        try:
            print(f"sending config {config}")    
            gw = MCPGateway("gateway",config)
            await gw.setup_member_servers()
            memebers = gw.list_member_servers()
            print(f"All members are {memebers}")
            self.assertEqual(len(memebers), 3, "Should have 3 members")
        except ValidationError as e:
                print(f"Actual error message: {e}")
                raise  # re-raise to keep test failing for now

    
    async def test_gateway_tools(self):
        current_dir = os.path.dirname(__file__)
        path = os.path.join(current_dir, "member_servers.json")

        with open(path, 'r') as f:
            config = json.load(f)

        try:
            gw = MCPGateway("gateway", config)
            async with Client(gw) as client:
                tools = await client.list_tools()
                self.assertIsInstance(tools, list)
                self.assertGreaterEqual(len(tools), 1)
        except ValidationError as e:
            self.fail(f"ValidationError raised unexpectedly: {e}")

if __name__ == '__main__':
    unittest.main()