import os
import sys
import asyncio

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from mcp_composer import MCPComposer

database_config = {
    "type": "cloudant",
    "api_key": "omU9J_FSMmFzW0ZPsQ42jSLlffBKywwkWNCrai-aHXrA",
    "service_url": "https://83e97bb1-7630-4394-82cc-f212049ba1ae-bluemix.cloudantnosqldb.appdomain.cloud/",
}

gw = MCPComposer("composer", database_config=database_config)


async def main():
    await gw.setup_member_servers()
    await gw.run_http_async(host="0.0.0.0", port=9000, log_level="debug", path="/mcp")


if __name__ == "__main__":
    asyncio.run(main())
