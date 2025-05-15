from mcp_gateway import MCPGateway
import asyncio

gw = MCPGateway("gateway")



async def main():
    await gw.run_http_async(host="0.0.0.0", port=9000, log_level="debug", path="/mcp")

if __name__ == "__main__":
   asyncio.run(main())