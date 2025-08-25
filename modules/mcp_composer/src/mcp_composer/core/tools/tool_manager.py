"""Tool Manager"""

from __future__ import annotations
import inspect
from typing import TYPE_CHECKING, Optional

from fastmcp.tools import ToolManager
from fastmcp.tools.tool import Tool
from fastmcp.settings import DuplicateBehavior


from mcp_composer.core.member_servers.member_server import HealthStatus, MemberMCPServer
from mcp_composer.core.utils.exceptions import ToolDuplicateError
from mcp_composer.store.database import DatabaseInterface
from mcp_composer.core.utils import LoggerFactory, get_server_doc_info
from mcp_composer.core.member_servers import ServerManager
from mcp_composer.core.utils.tools import (
    generate_tool_from_curl,
    generate_tool_from_open_api,
    tool_exist,
    tool_config,
    check_duplicate_tool,
)

if TYPE_CHECKING:
    from mcp_composer.core.composer import MCPComposer

try:
    from mcp_composer.core.custom_tool import tools as custom_tools
except ImportError:
    custom_tools = None


logger = LoggerFactory.get_logger()


class MCPToolManager(ToolManager):
    """Manages member servers tools."""

    def __init__(
        self,
        composer: MCPComposer,
        server_manager: ServerManager,
        duplicate_behavior: DuplicateBehavior | None = None,
        database: Optional[DatabaseInterface] = None,
    ):
        super().__init__(duplicate_behavior)
        self._composer = composer
        self._server_manager = server_manager
        self._database = database
        self._disabled_tools: list[str] = []

    def unmount(self, server_id):
        """Unmount a member server"""
        # Find the matching mounted server
        for idx, mounted_server in enumerate(self._mounted_servers):
            if mounted_server.prefix == server_id:
                del self._mounted_servers[idx]

    def filter_tools(self, tools: dict[str, Tool]) -> dict[str, Tool]:
        """Filter tools by performing the following actions for a member server,
        if it exists
        1. Remove tools
        2. Update description
        """
        try:
            if len(self._disabled_tools) == 1 and self._disabled_tools[0] == "all":
                tool = self.add_tool(Tool.from_function(self.enable_all_tools))
                return {tool.name: tool}

            server_config = self._server_manager.list()
            if not server_config:
                return tools

            remove_set = set()
            description_updates = {}

            for member in server_config:
                if member.health_status == HealthStatus.unhealthy:
                    continue

                if member.disabled_tools:
                    remove_set.update(member.disabled_tools)
                if self._disabled_tools:
                    remove_set.update(self._disabled_tools)
                if member.tools_description:
                    description_updates.update(member.tools_description)

            filtered_tools = {}
            for name, tool in tools.items():
                if name in remove_set:
                    continue
                if name in description_updates:
                    tool.description = description_updates[name]
                filtered_tools[name] = tool
            return filtered_tools
        except Exception as e:
            logger.exception("Tools filtering failed: %s", e)
            raise

    async def load_custom_tools(self):
        """Load tools using saved OpenAPI, Curl, and Python script."""

        try:
            if custom_tools:
                for name, func in inspect.getmembers(custom_tools, inspect.isfunction):
                    logger.info("Adding tool from custom tool folder: %s", name)
                    self.add_tool(Tool.from_function(func))

            # Load tools from curl commands
            for tool_fn in await generate_tool_from_curl():
                self.add_tool(Tool.from_function(tool_fn))

            # Load tools from OpenAPI Specifications
            server_data = await generate_tool_from_open_api()
            return server_data
        except Exception as e:
            raise e

    async def fetch_server_tools(
        self,
        server: MemberMCPServer,
        remove: Optional[list[str]] = None,
        description: Optional[dict[str, str]] = None,
    ) -> dict[str, Tool]:
        """Fetch member server tools"""
        result = {}

        # Find the matching mounted server and get its tools
        for mounted_server in self._mounted_servers:
            if mounted_server.prefix == server.id:
                tools = await mounted_server.server.get_tools()
                server_tools = {f"{server.id}_{k}": v for k, v in tools.items()}
                result = {
                    k: v
                    for k, v in server_tools.items()
                    if not remove or k not in remove
                }
                break  # Stop after finding the matching server

        # Update tool descriptions if provided
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

        # Case 1: Specific server
        if server_id:
            server = self._server_manager.get(server_id)
            doc = self._server_manager.get_document(server_id)
            remove, description = get_server_doc_info(doc)
            logger.info(
                """Case 2: Fetch tools for server '%s'.
                Removed: '%s'. Descriptions: '%s'""",
                server_id,
                remove,
                description,
            )
            return await self.fetch_server_tools(server, remove, description)

        # Default Case: All tools
        tools.update(await self.get_tools())
        logger.info("Default Case: Fetch all tools from member servers and composer")
        return tools

    async def get_tool_config_by_name(self, name: str) -> list[dict]:
        """
        Get a tool configuration details
        """
        tools = self.filter_tools(await self.get_tools())
        tool_configs = tool_config(tools, name)
        logger.info("Tool configuration details by tool name:%s", tool_configs)
        return tool_configs

    async def get_tool_config_by_server(self, server_id: str) -> list[dict]:
        """
        Get all tool configuration details of a specific member server
        """
        self._server_manager.check_server_exist(server_id)
        server_tools = await self.get_all_tools(server_id)
        tool_configs = tool_config(server_tools)
        logger.info("Tool configuration details by server name: %s", tool_configs)
        return tool_configs

    async def disable_tools_by_server(self, tools: list[str], server_id: str) -> str:
        """
        disable a tool or multiple tools from the member server
        """
        self._server_manager.check_server_exist(server_id)
        server_tools = await self.get_all_tools(server_id)
        await tool_exist(tools, server_tools)
        self._server_manager.disable_tools(tools, server_id)
        logger.info("Disabled %s tools from server", tools)
        return f"Disabled {tools} tools from server {server_id}"

    async def enable_tools_by_server(self, tools: list[str], server_id: str) -> str:
        """
        enable a tool or multiple tools from the member server
        """
        self._server_manager.check_server_exist(server_id)
        self._server_manager.enable_tools(tools, server_id)
        logger.info("Enabled %s tools from server", tools)
        return f"Enabled {tools} tools from server {server_id}"

    async def disable_tools(self, tools: list[str]) -> str:
        """
        disable a tool or multiple tools
        """
        if tools[0].lower() == "all":
            self._disabled_tools = ["all"]
            logger.info("Disabled all tools")
        else:
            existing_tools = self._disabled_tools
            duplicate_tool = check_duplicate_tool(existing_tools, tools)

            if duplicate_tool:
                raise ToolDuplicateError(f"Tool {duplicate_tool} is already disabled")

            existing_tools.extend(tools)
            logger.info("Added new disabled tool list %s in composer.", tools)
        if self._database:
            self._database.disable_tools(tools, server_id=self._composer.name)
        return f"Successfully disabled tools: {tools}"

    async def enable_tools(self, tools: list[str]) -> str:
        """
        enable a tool or multiple tools
        """
        disabled_tools = self._disabled_tools
        tools_to_remove = [tool for tool in tools if tool in disabled_tools]
        if not tools_to_remove:
            raise ValueError("No tools disabled")
        # Remove matching tools from disabled_tools
        self._disabled_tools = [
            tool for tool in disabled_tools if tool not in tools_to_remove
        ]

        if self._database:
            self._database.enable_tools(
                self._disabled_tools, server_id=self._composer.name
            )

        logger.info("Enabled %s tools from composer", tools)
        return f"Enabled {tools} tools from composer"

    async def enable_all_tools(self) -> str:
        """
        enable all tools
        """
        if len(self._disabled_tools) == 1 and self._disabled_tools[0].lower() == "all":
            self._disabled_tools = []

        if self._database:
            self._database.enable_tools(
                self._disabled_tools, server_id=self._composer.name
            )

        logger.info("Enabled all tools from composer")
        return "Enabled all tools from composer"

    async def update_tool_description(
        self, tool: str, description: str, server_id: str
    ) -> str:
        """
        Update tool description of member servers
        """
        self._server_manager.check_server_exist(server_id)
        server_tools = await self.get_all_tools(server_id)
        await tool_exist(tool, server_tools)
        self._server_manager.update_tool_description(tool, description, server_id)
        logger.info(
            "Updated tool '%s' with description '%s' for server '%s'",
            tool,
            description,
            server_id,
        )
        return f"Updated {tool} with description: {description}"
