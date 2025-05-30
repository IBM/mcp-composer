import asyncio
from typing import Optional, Any
from fastmcp.tools import ToolManager
from fastmcp.tools.tool import Tool
from fastmcp.server.server import MountedServer
from fastmcp.exceptions import NotFoundError
from fastmcp.settings import DuplicateBehavior
from collections.abc import Callable

from mcp_gateway.utils import LoggerFactory
from mcp_gateway.member_servers import ServerManager

logger = LoggerFactory.get_logger()


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
        server_manager: ServerManager,
        server_id: Optional[str] = None,
        server_config: Optional[list[dict]] = None,
        remove_tools: Optional[list[dict]] = None,
    ) -> dict[str, Tool]:
        """Get all tools by key."""
        tools: dict[str, Tool] = {}

        async def fetch_server_tools(
            server: MountedServer, remove: Optional[list[str]] = None
        ) -> dict[str, Tool]:
            server_tools = await server.get_tools()
            return {
                k: v for k, v in server_tools.items() if not remove or k not in remove
            }

        # Case 1: Fetch tools for a specific server
        if server_id:
            server = mounted_servers.get(server_id)
            if server:
                server_doc = server_manager.get_document(server_id)
                remove = server_doc.get("remove_tools", []) if server_doc else []

                tools.update(await fetch_server_tools(server, remove))
                logger.info(f"Case 1: Fetch tools for a specific server: {server_id}")
            return tools

        # Case 2: Fetch tools based on server configuration
        if server_config:
            include_gateway_tools = False

            for cfg in server_config:
                sid = cfg["id"]
                remove = cfg.get("remove_tools")
                if sid == "gateway":
                    if remove:
                        tools.update(
                            {
                                k: v
                                for k, v in self.get_tools().items()
                                if k not in remove
                            }
                        )
                        logger.info(
                            f"Case 2: Fetch tools for the mcp gateway server with remove tools: {server_id}"
                        )
                    else:
                        tools.update(self.get_tools())
                        logger.info(
                            f"Case 3: Fetch tools for the mcp gateway server: {server_id}"
                        )
                else:
                    logger.info(
                        f"Case 4: Fetch tools for the member server with remove tools: {sid}"
                    )
                    include_gateway_tools = True
                    server = mounted_servers.get(sid)
                    if not server:
                        raise NotFoundError(f"Unknown server: {sid}")
                    tools.update(await fetch_server_tools(server, remove))
            if include_gateway_tools:
                tools.update(self.get_tools())

            return tools

        # Default Case: Fetch from all mounted servers and gateway
        results = await asyncio.gather(
            *[fetch_server_tools(server) for server in mounted_servers.values()]
        )
        for server_tools in results:
            tools.update(server_tools)
        tools.update(self.get_tools())
        logger.info(
            "Case default: Fetch all tools from the member servers and gateway server"
        )
        return tools
