# gateway/mcp_gateway.py

from fastmcp import FastMCP
from typing import Any, Dict, Optional
from .utils import LoggerFactory
from .member_servers import ServerManager
from .member_servers import MemberMCPServer
from .member_servers import MCPServerBuilder
logger = LoggerFactory.get_logger()


class MCPGateway(FastMCP):
    """
    Extended FastMCP server with dynamic runtime server composition.
    """
    def __init__(self, name: str = "MCPGateway", config: Optional[list[dict]] = None):
        super().__init__(name=name)
        self.config = config or []
        self._server_manager = ServerManager()
        self.add_tool(self.register_mcp_server)
        self.add_tool(self.remove_mcp_server)

    async def setup(self):
        """
        Mount multiple servers from a JSON list in self.config.
        This runs at startup or from manual trigger.
        """
        logger.info(f"Setting up {len(self.config)} configured servers...")
        for config in self.config:
            try:
                await self._mount_member_server(config)
            except Exception as e:
                logger.exception(f"Failed to mount server '{config.get('id')}': {e}")


    async def register_mcp_server(self, config: dict) -> str:
        """
        Register a single server dynamically from config.
        """
        try:
            return    await self._mount_member_server(config)
        except Exception as e:
            logger.exception(f"Failed to register memeber server '{config.get('id')}': {e}")
            return f"Failed to register memeber server '{config.get('id')}'"

   
    async def remove_mcp_server(self, server_id:str) -> str:
        """
        Remove a single server dynamically from config.
        """
        try:
            return await self.unmount_server(server_id)
        except Exception as e:
            logger.exception(f"Failed to remove memeber server '{server_id}': {e}")
            return f"Failed to remove memeber server '{server_id}'"


    async def _mount_member_server(self, config: dict) -> str:
        server_id = config["id"]

        if self._server_manager.has_member_server(server_id):
            logger.warning(f"Server '{server_id}' already mounted.")
            return f"Server '{server_id}' already mounted."

        builder = MCPServerBuilder(config)
        sub_mcp = await builder.build()

        member = MemberMCPServer(
            id=server_id,
            type=config["type"],
            config=config,
            label=config.get("label"),
            tags=config.get("tags", []),
            tool_count=None
        )
        member.set_server(sub_mcp)

        self._server_manager.add_member(server_id,member)
        self.mount(server_id, sub_mcp)
        logger.info(f"Mounted MCP server: {server_id}")
        return f"Server '{server_id}' mounted."

    async def unmount_server(self, server_id: str) -> str:
        member = self._server_manager.get(server_id)
        if not member:
            return f"Server '{server_id}' not mounted."
        self._server_manager.remove_member(server_id)
        return f"Server '{server_id}' unmounted."

    def list_member_servers(self) -> list[dict]:
        logger.info("list_member_servers")
        return [
            {"id": m.id, "server_name": m.get_server().name}
            for m in self._server_manager.list()
        ]
