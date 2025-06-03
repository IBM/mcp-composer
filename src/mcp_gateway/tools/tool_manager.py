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

    def tool_config(
        self, server_tools: dict[str, Tool], key: Optional[str] = None
    ) -> list[dict]:
        """
        Get tool configuration details by tool name or server
        """

        def format_tool(tool: Tool) -> dict:
            return {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            }

        if key:
            tool = server_tools.get(key)
            if not tool:
                raise NotFoundError(f"Unknown tool: {key}")
            return [format_tool(tool)]

        return [format_tool(tool) for tool in server_tools.values()]

    async def get_all_tools(
        self,
        mounted_servers: dict[str, MountedServer],
        server_manager: ServerManager,
        server_id: Optional[str] = None,
        server_config: Optional[list[dict]] = None,
    ) -> dict[str, Tool]:
        """Get all tools by key."""
        tools: dict[str, Tool] = {}

        async def fetch_server_tools(
            server: MountedServer,
            remove: Optional[list[str]] = None,
            description: Optional[dict[str, str]] = None,
        ) -> dict[str, Tool]:
            server_tools = await server.get_tools()
            tools = {
                k: v for k, v in server_tools.items() if not remove or k not in remove
            }
            # Update tool descriptions if provided
            if description:
                for name, desc in description.items():
                    if name in tools:
                        tools[name].description = desc
            return tools

        # Case 1: Fetch tools from gateway server
        if server_id == "gateway":
            logger.info("Case 1: Fetch tools for gateway server")
            return self.get_tools()

        # Case 2: Fetch tools for a specific server
        if server_id:
            server = mounted_servers.get(server_id)
            if server:
                server_doc = server_manager.get_document(server_id)
                remove = server_doc.get("remove_tools", []) if server_doc else []
                tools_description = (
                    server_doc.get("tools_description", {}) if server_doc else {}
                )
                tools.update(
                    await fetch_server_tools(server, remove, tools_description)
                )
                logger.info(
                    f"Case 2: Fetch tools for server '{server_id}'. Removed tools: {remove}. Tools description: {tools_description}"
                )

            return tools

        # Case 3: Fetch tools based on server configuration
        if server_config:
            include_gateway_tools = False

            for cfg in server_config:
                sid = cfg["id"]
                remove = cfg.get("remove_tools")
                tools_description = cfg.get("tools_description", {})
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
                            f"Case 3: Fetch tools for the mcp gateway server '{sid}' with remove tools: {remove}"
                        )
                    else:
                        tools.update(self.get_tools())
                        logger.info(
                            f"Case 4: Fetch tools for the mcp gateway server: {sid}"
                        )
                else:
                    logger.info(
                        f"Case 5: Fetch tools for the member server: {sid}. Remove tool: {remove}. Tools description: {tools_description}"
                    )
                    include_gateway_tools = True
                    server = mounted_servers.get(sid)
                    if not server:
                        raise NotFoundError(f"Unknown server: {sid}")
                    tools.update(
                        await fetch_server_tools(server, remove, tools_description)
                    )
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
            "Default Case: Fetch all tools from the member servers and gateway server"
        )
        return tools

    def _remove_gateay_tools(self, server_manager: ServerManager):
        # remove the gateway tools
        server_doc = server_manager.get_document("gateway")
        remove = server_doc.get("remove_tools", []) if server_doc else []
        for tool in remove:
            self.remove_tool(tool)
