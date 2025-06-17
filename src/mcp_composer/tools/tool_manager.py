import asyncio
from typing import Optional
from fastmcp.tools import ToolManager
from fastmcp.tools.tool import Tool
from mcp_composer.member_servers.member_server import HealthStatus, MemberMCPServer
from fastmcp.exceptions import NotFoundError
from fastmcp.settings import DuplicateBehavior
from fastmcp.exceptions import ToolError

from mcp_composer.utils import LoggerFactory, get_server_doc_info, format_tool
from mcp_composer.member_servers import ServerManager

logger = LoggerFactory.get_logger()


class MCPToolManager(ToolManager):
    """Manages member servers tools."""

    def __init__(
        self,
        server_manager: ServerManager,
        duplicate_behavior: DuplicateBehavior | None = None,
    ):
        super().__init__(duplicate_behavior)
        self.server_manager = server_manager

    def fetch_composer_tools(
        self,
        remove: Optional[list[str]] = None,
        description: Optional[dict[str, str]] = None,
    ) -> dict[str, Tool]:
        result = {
            k: v for k, v in self.get_tools().items() if not remove or k not in remove
        }
        if description:
            for name, desc in description.items():
                if name in result:
                    result[name].description = desc
        return result

    def tool_config(
        self, server_tools: dict[str, Tool], key: Optional[str] = None
    ) -> list[dict]:
        """
        Get tool configuration details by tool name or server
        """
        if key:
            tool = server_tools.get(key)
            if not tool:
                raise NotFoundError(f"Unknown tool: {key}")
            return [format_tool(tool)]

        return [format_tool(tool) for tool in server_tools.values()]

    async def tool_exist(
        self, tools: list[str] | str, all_tools: dict[str, Tool]
    ) -> None:
        tools_to_check = [tools] if isinstance(tools, str) else tools
        unknown_tools = [
            tool for tool in tools_to_check if tool not in all_tools.keys()
        ]

        if unknown_tools:
            raise NotFoundError(f"Unknown tool(s): {', '.join(unknown_tools)}")

    async def fetch_server_tools(
        self,
        server: MemberMCPServer,
        remove: Optional[list[str]] = None,
        description: Optional[dict[str, str]] = None,
    ) -> dict[str, Tool]:
        remote_server = self.server_manager._mounted_servers.get(server.id)
        result = {
            k: v
            for k, v in (await remote_server.get_tools()).items()  # type: ignore
            if not remove or k not in remove
        }
        if description:
            for name, desc in description.items():
                if name in result:
                    result[name].description = desc
        return result

    async def get_all_tools(
        self,
        server_id: Optional[str] = None,
    ) -> dict[str, Tool]:
        """Get all tools by key."""
        tools: dict[str, Tool] = {}

        # Case 2: Specific server
        if server_id:
            server = self.server_manager.get(server_id)
            doc = self.server_manager.get_document(server_id)
            remove, description = get_server_doc_info(doc)
            logger.info(
                f"Case 2: Fetch tools for server '{server_id}'. Removed: {remove}. Descriptions: {description}"
            )
            return await self.fetch_server_tools(server, remove, description)

        server_config = self.server_manager.list()

        # Case 3: Config-driven
        if server_config:
            for member in server_config:
                if member.health_status == HealthStatus.unhealthy:
                    continue
                sid = member.id
                remove = member.remove_tools
                description = member.tools_description
                server = self.server_manager.get(sid)
                logger.info(
                    f"Case 3: Fetch tools for server '{sid}'. Remove: {remove}. Descriptions: {description}"
                )
                tools.update(await self.fetch_server_tools(server, remove, description))
                tools.update(self.get_tools())
            return tools

        # Default Case: All servers + composer
        results = await asyncio.gather(
            *[self.fetch_server_tools(server) for server in server_config]
        )
        for result in results:
            tools.update(result)
        tools.update(self.get_tools())
        logger.info("Default Case: Fetch all tools from member servers and composer")
        return tools

    async def get_tool_config_by_name(self, name: str) -> list[dict]:
        """
        Get a tool configuration details
        """
        all_tools = await self.get_all_tools()
        tool_config = self.tool_config(all_tools, name)
        logger.info(f"Tool configuration details by tool name: {tool_config}")
        return tool_config

    async def get_tool_config_by_server(self, server_id: str) -> list[dict]:
        """
        Get all tool configuration details of a specific member server
        """
        self.server_manager.check_server_exist(server_id)
        server_tools = await self.get_all_tools(server_id)
        tool_config = self.tool_config(server_tools)
        logger.info(f"Tool configuration details by server name: {tool_config}")
        return tool_config

    async def remove_tools(self, tools: list[str], server_id: str) -> str:
        """
        Remove a tool or multiple from the servers and composer
        """
        self.server_manager.check_server_exist(server_id)
        if "remove_tools" in tools:
            raise ToolError("Tool: remove_tools can't be removed")

        server_tools = await self.get_all_tools(server_id)
        await self.tool_exist(tools, server_tools)
        self.server_manager.add_remove_tools(tools, server_id)
        logger.info(f"Removed {tools} tools from server")
        return f"Removed {tools} tool from server"

    async def update_tool_description(
        self, tool: str, description: str, server_id: str
    ) -> str:
        """
        Update tool description of member servers
        """
        self.server_manager.check_server_exist(server_id)
        server_tools = await self.get_all_tools(server_id)
        await self.tool_exist(tool, server_tools)
        self.server_manager.update_tool_description(tool, description, server_id)
        logger.info(
            f"Updated Tool: {tool} with description: {description} for the server: {server_id}"
        )
        return f"Updated {tool} with description: {description}"
