import asyncio
from mcp_composer.composer import MCPComposer

gw = MCPComposer(
    "composer", database_config={"type": "local_file", "file_path": "./mcp_servers.json"}
)


async def main():
    await gw.setup_member_servers()
    await gw.run_http_async(host="0.0.0.0", port=9000, log_level="debug", path="/mcp")


if __name__ == "__main__":
    asyncio.run(main())
