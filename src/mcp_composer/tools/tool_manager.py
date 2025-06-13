import asyncio
from typing import Optional, Any
from fastmcp.tools import ToolManager
from fastmcp.tools.tool import Tool
from fastmcp.server.server import MountedServer
from fastmcp.exceptions import NotFoundError
from fastmcp.settings import DuplicateBehavior
from collections.abc import Callable

from mcp_composer.utils import LoggerFactory
from mcp_composer.member_servers import ServerManager

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
            result = {
                k: v
                for k, v in (await server.get_tools()).items()
                if not remove or k not in remove
            }
            if description:
                for name, desc in description.items():
                    if name in result:
                        result[name].description = desc
            return result

        def fetch_composer_tools(
            remove: Optional[list[str]] = None,
            description: Optional[dict[str, str]] = None,
        ) -> dict[str, Tool]:
            result = {
                k: v
                for k, v in self.get_tools().items()
                if not remove or k not in remove
            }
            if description:
                for name, desc in description.items():
                    if name in result:
                        result[name].description = desc
            return result

        def get_server_doc_info(sid: str) -> tuple[list[str], dict[str, str]]:
            doc = server_manager.get_document(sid)
            remove_tools = []
            tools_description = {}
            if doc:
                remove_tools = doc.get("remove_tools", [])
                tools_description = doc.get("tools_description", {})
            return remove_tools, tools_description

        # Case 1: composer server
        if server_id == "composer":
            logger.info("Case 1: Fetch tools for composer server")
            remove, description = get_server_doc_info(server_id)
            return fetch_composer_tools(remove, description)

        # Case 2: Specific server
        if server_id:
            server = mounted_servers.get(server_id)
            if not server:
                return tools
            remove, description = get_server_doc_info(server_id)
            tools.update(await fetch_server_tools(server, remove, description))
            logger.info(
                f"Case 2: Fetch tools for server '{server_id}'. Removed: {remove}. Descriptions: {description}"
            )
            return tools

        # Case 3: Config-driven
        if server_config:
            include_composer_tools = False
            for cfg in server_config:
                sid = cfg["id"]
                remove = cfg.get("remove_tools")
                description = cfg.get("tools_description", {})
                if sid == "composer":
                    logger.info(
                        f"Case 3: Fetch composer tools. Remove: {remove}. Descriptions: {description}"
                    )
                    tools.update(fetch_composer_tools(remove, description))
                else:
                    server = mounted_servers.get(sid)
                    if not server:
                        raise NotFoundError(f"Unknown server: {sid}")
                    logger.info(
                        f"Case 4: Fetch tools for server '{sid}'. Remove: {remove}. Descriptions: {description}"
                    )
                    tools.update(await fetch_server_tools(server, remove, description))
                    include_composer_tools = True
            if include_composer_tools:
                tools.update(self.get_tools())
            return tools

        # Default Case: All servers + composer
        results = await asyncio.gather(
            *[fetch_server_tools(server) for server in mounted_servers.values()]
        )
        for result in results:
            tools.update(result)
        tools.update(self.get_tools())
        logger.info("Default Case: Fetch all tools from member servers and composer")
        return tools

    def _remove_gateay_tools(self, server_manager: ServerManager):
        # remove the composer tools
        server_doc = server_manager.get_document("composer")
        remove = server_doc.get("remove_tools", []) if server_doc else []
        for tool in remove:
            self.remove_tool(tool)
