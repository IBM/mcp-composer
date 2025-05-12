import asyncio
from mcp_gateway import MCPGateway
import json
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
gateway = MCPGateway()

async def main():
    await gateway.run_sse_async(host="0.0.0.0", port=8080)

if __name__ == "__main__":
    asyncio.run(main())