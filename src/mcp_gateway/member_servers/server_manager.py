from typing import Dict, List, Any, Optional
from collections.abc import Callable

from fastmcp.settings import DuplicateBehavior
from fastmcp.exceptions import NotFoundError

from mcp_gateway.utils import LoggerFactory, get_member_health, check_duplicate_tool
from mcp_gateway.member_servers.member_server import HealthStatus, MemberMCPServer
from mcp_gateway.exceptions import (
    MemberServerError,
    ToolDuplicateError,
    ToolRemoveError,
)
from mcp_gateway.store.database import DatabaseInterface

logger = LoggerFactory.get_logger()


class ServerManager:
    """
    Manages registration and lifecycle of mounted MCP servers,
    with optional serialization for monitoring, or persistence.
    """

    _db_name: str = "mcp_servers"

    def __init__(
        self,
        duplicate_behavior: DuplicateBehavior | None = None,
        serializer: Callable[[str, MemberMCPServer], Any] | None = None,
        database: Optional[DatabaseInterface] = None,
    ):
        self._member_servers: dict[str, MemberMCPServer] = {}
        # Fix here: explicitly declare non-optional type
        self._serializer: Callable[[str, MemberMCPServer], Any] = (
            serializer or self.default_serializer
        )
        self._database = database
        self._mounted_servers = {}

        if duplicate_behavior is None:
            duplicate_behavior = "warn"

        if duplicate_behavior not in DuplicateBehavior.__args__:
            raise ValueError(
                f"Invalid duplicate_behavior: {duplicate_behavior}. "
                f"Must be one of: {', '.join(DuplicateBehavior.__args__)}"
            )

        self.duplicate_behavior = duplicate_behavior

    @staticmethod
    def default_serializer(server_id: str, member: MemberMCPServer):
        return member.to_dict()

    async def member_health(self, config: list[MemberMCPServer]) -> dict:
        server_config = config if config else self.list()
        health_status = await get_member_health(server_config)
        return health_status

    def list_member_servers(self) -> list[dict]:
        """Listing member servers"""
        logger.info("Listing member servers")
        return [{"id": m.id, "server_name": m.get_server().name} for m in self.list()]

    def check_server_exist(self, server_id) -> None:
        if server_id != "gateway" and not self.has_member_server(server_id):
            raise NotFoundError(f"Server '{server_id}' not mounted.")

    def has_member_server(self, key: str) -> bool:
        """Check if a memeber server exists."""
        return key in self._member_servers

    def add_member(self, server_id: str, server: MemberMCPServer):
        if server_id in self._member_servers:
            logger.warning(f"Overwriting existing MCP server: {server_id}")
        self._member_servers[server_id] = server
        logger.info(f"Mounted MCP server: {server_id}")

    def remove_member(self, server_id: str):
        if server_id not in self._member_servers:
            logger.warning(f"MCP server '{server_id}' not found.")
            return
        del self._member_servers[server_id]
        logger.info(f"Unmounted MCP server: {server_id}")

    def get(self, server_id: str) -> MemberMCPServer:
        if server_id not in self._member_servers:
            raise NotFoundError(f"MCP Server '{server_id}' not mounted.")
        if self._member_servers[server_id].health_status == HealthStatus.unhealthy:
            raise MemberServerError(f"MCP Server '{server_id}' is down.")
        return self._member_servers[server_id]

    def list(self) -> list[MemberMCPServer]:
        return list(self._member_servers.values())

    def list_serialized(self) -> Dict[str, Any]:
        return {
            server_id: self._serializer(server_id, member)
            for server_id, member in self._member_servers.items()
        }

    def add_server_db(self, config: dict) -> None:
        if self._database:
            self._database.add_server(config)

    def remove_mcp_server(self, server_id: str) -> None:
        if self._database:
            self._database.remove_server(server_id)

    def load_all_servers_db(self) -> List[dict]:
        if self._database is None:
            return []
        return self._database.load_all_servers()

    def add_remove_tools(self, tools: List[str], server_id: str) -> None:
        try:
            tools = list(set(tools))
            member = self.get(server_id)
            existing_tools = member.remove_tools
            tools_description = member.tools_description
            duplicate_tool = check_duplicate_tool(existing_tools, tools)

            if duplicate_tool:
                raise ToolDuplicateError(f"Tool {duplicate_tool} is already removed")

            existing_tools.extend(tools)
            logger.info(f"Added new remove tool list {tools} for server {server_id}.")

            # Remove tool descriptions if they exist
            if existing_tools and tools_description:
                for tool in existing_tools:
                    tools_description.pop(tool, None)
        except Exception as e:
            raise ToolRemoveError(f"Failed to remove tool: {e}")

        if self._database:
            self._database.add_remove_tools(tools, server_id)

    def update_tool_description(
        self, tool: str, description: str, server_id: str
    ) -> None:
        member = self.get(server_id)
        # if tools description already found, update it
        # if not add the tools description
        member.tools_description.update({tool: description})
        logger.info(
            f"Tool description: {member.tools_description} is added for server: {server_id}"
        )

        if self._database:
            self._database.update_tool_description(tool, description, server_id)

    def get_document(self, server_id: str) -> Dict:
        if self._database is None:
            return {}
        return self._database.get_document(server_id)
