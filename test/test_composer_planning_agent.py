

import os
import sys
import asyncio
import json
from dotenv import load_dotenv; load_dotenv();

file_path = os.getenv("SERVER_CONFIG_FILE_PATH")
config = {}
with open(file_path, 'r') as file: 
    config = json.load(file)


from mcp_composer import MCPComposer
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

gw = MCPComposer("composer", config = config)


async def main():


    """_summary_

    Raises:
        ValueError: _description_
    """
    mode = os.getenv("MCP_MODE", "http").lower()

    await gw.setup_member_servers()

    if mode == "http":
        await gw.run_http_async(host="0.0.0.0", port=9000, log_level="debug", path="/mcp")
    elif mode == "stdio":
        await gw.run_stdio_async()
    else:
        raise ValueError(f"Unsupported MCP_MODE: {mode}")


if __name__ == "__main__":
    asyncio.run(main())