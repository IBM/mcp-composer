from typing import Dict, List, Any, Optional
from fastmcp import FastMCP
from fastmcp.settings import DuplicateBehavior
from mcp_gateway.utils import LoggerFactory
from collections.abc import Callable
from mcp_gateway.member_servers.member_server import MemberMCPServer

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
        database: Optional[DatabaseInterface] = None 
    ):
        self._member_servers: dict[str, MemberMCPServer] = {}
        # Fix here: explicitly declare non-optional type
        self._serializer: Callable[[str, MemberMCPServer], Any] = serializer or self.default_serializer
        self._database = database

        if duplicate_behavior is None:
            duplicate_behavior = "warn"

        if duplicate_behavior not in DuplicateBehavior.__args__:
            raise ValueError(
                f"Invalid duplicate_behavior: {duplicate_behavior}. "
                f"Must be one of: {', '.join(DuplicateBehavior.__args__)}"
            )

        self.duplicate_behavior = duplicate_behavior

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
            raise KeyError(f"MCP server '{server_id}' not found.")
        return self._member_servers[server_id]

    def list(self) -> list[MemberMCPServer]:
        return list(self._member_servers.values())

    def list_serialized(self) -> Dict[str, Any]:
        return {
            server_id: self._serializer(server_id, member)
            for server_id, member in self._member_servers.items()
        }

    @staticmethod
    def default_serializer(server_id: str, member: MemberMCPServer):
        return member.to_dict()

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
