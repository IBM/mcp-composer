import asyncio
from mcp_gateway.gateway import MCPGateway

gw = MCPGateway(
    "gateway",
    config=[
        {
            "id": "mcp-server",
            "type": "http",
            "endpoint": "https://dummy.endpoint/mcp",
        }
    ],
)


async def main():
    await gw.setup_member_servers()
    await gw.run_http_async(host="0.0.0.0", port=9000, log_level="debug", path="/mcp")


if __name__ == "__main__":
    asyncio.run(main())
