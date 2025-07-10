"""Tool Manager"""

from typing import Optional
import uncurl
from pydantic import ValidationError

from fastmcp.tools import ToolManager
from fastmcp.tools.tool import Tool
from fastmcp.settings import DuplicateBehavior


from mcp_composer.exceptions import ToolGenerateError
from mcp_composer.member_servers.member_server import HealthStatus, MemberMCPServer
from mcp_composer.settings.tool_setting import ToolSettings
from mcp_composer.store.database import DatabaseInterface
from mcp_composer.tools.model import OpenApiToolAuthConfig
from mcp_composer.utils import LoggerFactory, get_server_doc_info
from mcp_composer.member_servers import ServerManager
from mcp_composer.utils.auth_strategy import get_client
from mcp_composer.utils.custom_tool import (
    DynamicToolGenerator,
    OpenApiTool,
)
from mcp_composer.utils.tools import tool_exist, tool_config


logger = LoggerFactory.get_logger()


class MCPToolManager(ToolManager):
    """Manages member servers tools."""

    def __init__(
        self,
        server_manager: ServerManager,
        duplicate_behavior: DuplicateBehavior | None = None,
        database: Optional[DatabaseInterface] = None,
    ):
        super().__init__(duplicate_behavior)
        self.server_manager = server_manager
        self.database = database

    def unmount(self, server_id):
        """Unmount a member server"""
        # Find the matching mounted server and get its tools
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
            server_config = self.server_manager.list()
            if not server_config:
                return tools

            remove_set = set()
            description_updates = {}

            for member in server_config:
                if member.health_status == HealthStatus.unhealthy:
                    continue

                if member.disabled_tools:
                    remove_set.update(member.disabled_tools)
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

    async def generate_tool_from_curl(self):
        """Create tool from curl command"""
        try:
            return DynamicToolGenerator.read_curl_from_file()
        except ToolGenerateError as e:
            logger.exception(
                "Failed to generate tool from saved curl config details: %s", e
            )
            raise ToolGenerateError(
                "Failed to generate tool from saved curl config details"
            ) from e

    async def generate_tool_from_open_api(self):
        """Create tool from OpenAPI specification"""
        try:
            return await OpenApiTool.read_openapi_from_file()
        except Exception as e:
            logger.exception(
                "Failed to generate tool from saved OpenAPI specification: %s", e
            )
            raise ToolGenerateError(
                "Failed to generate tool from saved OpenAPI specification"
            ) from e

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
            server = self.server_manager.get(server_id)
            doc = self.server_manager.get_document(server_id)
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
        self.server_manager.check_server_exist(server_id)
        server_tools = await self.get_all_tools(server_id)
        tool_configs = tool_config(server_tools)
        logger.info("Tool configuration details by server name: %s", tool_configs)
        return tool_configs

    async def disable_tools(self, tools: list[str], server_id: str) -> str:
        """
        disable a tool or multiple tools from the member server
        """
        self.server_manager.check_server_exist(server_id)
        server_tools = await self.get_all_tools(server_id)
        await tool_exist(tools, server_tools)
        self.server_manager.disable_tools(tools, server_id)
        logger.info("Disabled %s tools from server", tools)
        return f"Disabled {tools} tools from server {server_id}"

    async def enable_tools(self, tools: list[str], server_id: str) -> str:
        """
        enable a tool or multiple tools from the member server
        """
        self.server_manager.check_server_exist(server_id)
        self.server_manager.enable_tools(tools, server_id)
        logger.info("Enabled %s tools from server", tools)
        return f"Enabled {tools} tools from server {server_id}"

    async def update_tool_description(
        self, tool: str, description: str, server_id: str
    ) -> str:
        """
        Update tool description of member servers
        """
        self.server_manager.check_server_exist(server_id)
        server_tools = await self.get_all_tools(server_id)
        await tool_exist(tool, server_tools)
        self.server_manager.update_tool_description(tool, description, server_id)
        logger.info(
            "Updated tool '%s' with description '%s' for server '%s'",
            tool,
            description,
            server_id,
        )
        return f"Updated {tool} with description: {description}"

    async def tool_from_script(self, config: dict):
        """Create Tool dynamically from the config script"""
        try:
            # Validate and parse input
            script_model = ToolSettings(**config)
            if script_model.script_config:
                logger.info("Generate tool from python script")
                return DynamicToolGenerator().create_from_script(script_model)

            if script_model.curl_config:
                parsed = uncurl.parse_context(script_model.curl_config["value"])
                tool_data = {
                    "_id": script_model.name,
                    "id": script_model.name,
                    "description": script_model.description,
                    "headers": parsed.headers,
                    "method": parsed.method,
                    "body": parsed.data,
                    "url": parsed.url,
                }
                logger.info(
                    "Generate tool from curl command, parsed details:%s", tool_data
                )
                DynamicToolGenerator.write_curl_to_file(tool_data)
                return DynamicToolGenerator.create_api_request(tool_data)

        except ValidationError as e:
            logger.exception("Invalid input: %s", e.errors())
            raise ToolGenerateError(f"Invalid input: {e.errors()}") from e

        except Exception as e:
            logger.exception("Failed to generate tool from config:%s", e)
            raise ToolGenerateError(str(e)) from e

    async def tool_from_open_api(self, open_api: dict, auth_config: dict | None = None):
        """Create tool from OpenAPI specification"""
        try:
            # for now, considering only one server
            server_url = open_api["servers"][0]["url"]
            server_name = open_api["info"]["title"].replace(" ", "_")
            if auth_config:
                OpenApiToolAuthConfig(**auth_config)
            OpenApiTool(server_name, open_api, auth_config).write_openapi()
            return server_name, await get_client(server_url, auth_config)

        except KeyError as e:
            logger.exception("Failed to generate tool from openapi:%s", e)
            raise ToolGenerateError(
                "Failed to generate tool from openapi: server url or title is missing"
            ) from e

        except Exception as e:
            logger.exception("Failed to generate tool from openapi:%s", e)
            raise ToolGenerateError(f"Failed to generate tool from openapi:{e}") from e
