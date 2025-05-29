import asyncio
from typing import Optional, Any
from fastmcp.tools import ToolManager
from fastmcp.tools.tool import Tool
from fastmcp.server.server import MountedServer
from fastmcp.exceptions import NotFoundError
from fastmcp.settings import DuplicateBehavior
from collections.abc import Callable


class MCPToolManager(ToolManager):
    """Manages member servers tools."""

    def __init__(
        self,
        duplicate_behavior: DuplicateBehavior | None = None,
        serializer: Callable[[Any], str] | None = None,
    ):
        super().__init__(duplicate_behavior, serializer)
        self._tools: dict[str, Tool] = {}
        self.remove_tools: list[str] = []

    def tool_config(
        self, server_tools: dict[str, Tool], key: Optional[str] = None
    ) -> list[dict]:
        if key:
            if key not in server_tools:
                raise NotFoundError(f"Unknown tool: {key}")
            tool = server_tools[key]
            return [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                }
            ]

        return [
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            }
            for tool in server_tools.values()
        ]

    async def get_all_tools(
        self,
        mounted_servers: dict[str, MountedServer],
        server_id: Optional[str] = None,
        remove_tools: Optional[list[dict]] = None,
    ) -> dict[str, Tool]:
        """Get all tools by key."""
        tools = {}

        async def fetch_server_tools(
            server: MountedServer, remove: Optional[list[str]] = None
        ) -> dict[str, Tool]:
            server_tools = await server.get_tools()
            if remove:
                server_tools = {
                    k: v for k, v in server_tools.items() if k not in remove
                }
            return server_tools

        # Case: Specific server only
        if server_id:
            print("case 1")
            server = mounted_servers.get(server_id)
            if server:
                tools.update(await fetch_server_tools(server))
            return tools

        # Case: All servers with global removal list
        if remove_tools:
            print("case 2")
            include_gw_tools = False
            for server_cfg in remove_tools:
                tools_to_remove = server_cfg.get("remove_tools")
                server = server_cfg["id"]

                if tools_to_remove and server == "gateway":
                    # Apply removal to gateway tools
                    gateway_tools = {
                        k: v
                        for k, v in self.get_tools().items()
                        if k not in tools_to_remove
                    }
                    tools.update(gateway_tools)
                elif tools_to_remove:
                    include_gw_tools = True
                    server = mounted_servers.get(server)
                    if not server:
                        raise NotFoundError(f"Unknown server: {server_id}")
                    tools.update(await fetch_server_tools(server, tools_to_remove))
                else:
                    # Default case: Get all tools from all servers and gateway
                    include_gw_tools = True
                    print("case 3", server)
                    server = mounted_servers.get(server)
                    print("----", await server.get_tools())
                    await server.get_tools()
                    if not server:
                        raise NotFoundError(f"Unknown server: {server_id}")
                    tools.update(await fetch_server_tools(server))
                    print("tools", tools)

            if include_gw_tools:
                tools.update(self.get_tools())
        else:
            print("----7")
            # Fetch from all servers concurrently
            results = await asyncio.gather(
                *[fetch_server_tools(server) for server in mounted_servers.values()]
            )
            for server_tools in results:
                tools.update(server_tools)
            tools.update(self.get_tools())

        return tools
