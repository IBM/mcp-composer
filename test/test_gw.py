import os
import sys
import asyncio
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
from mcp_gateway import MCPGateway
gw = MCPGateway("gateway")



async def main():
    await gw.setup_member_servers()
    await gw.run_http_async(host="0.0.0.0", port=9000, log_level="debug", path="/mcp")

if __name__ == "__main__":
   asyncio.run(main())