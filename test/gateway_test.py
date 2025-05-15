import unittest
from mcp_gateway import MCPGateway

class TestSum(unittest.TestCase):

    def test_gateway(self):
        gw = MCPGateway("gateway")
        self.assertEqual(gw.name, "gateway", "Should be 6")

    def test_using_config(self):
        

if __name__ == '__main__':
    unittest.main()