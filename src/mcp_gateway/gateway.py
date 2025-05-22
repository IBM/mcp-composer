from fastmcp import FastMCP
from dotenv import load_dotenv
from typing import Any, Dict, Optional
from mcp_gateway.utils import LoggerFactory, AllServersValidator, ValidationError, ServerConfigValidator
from mcp_gateway.member_servers import ServerManager, MemberMCPServer, MCPServerBuilder
load_dotenv()
import sys

logger = LoggerFactory.get_logger()


class MCPGateway(FastMCP):
    """
    Extended FastMCP server with dynamic runtime server composition.
    """
    def __init__(self, name: str = "MCPGateway", config: Optional[list[dict]] = None):
        super().__init__(name=name)

        self._server_manager = ServerManager()

        db_configs = self._server_manager.load_all_servers_db()
        logger.info("Loaded %d server configs from Cloudant", len(db_configs))

        self.config = db_configs
        if config:
            try:
                AllServersValidator(config).validate_all()
                self.config.extend(config)
                logger.info("Merged %d configs supplied at launch", len(config))
            except ValidationError as e:
                logger.error("Validation error: %s", e)
                sys.exit(1)

        self.add_tool(self.register_mcp_server)
        self.add_tool(self.remove_mcp_server)

    async def setup_member_servers(self):
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
        logger.info(f" Register a single server dynamically from config :{config}")
        
        try:
            ServerConfigValidator(config).validate()
            result = await self._mount_member_server(config)
            return result
        except Exception as e:
            logger.exception(f"Failed to register member server '{config}': {e}")
            return f"Failed to register member server '{config}'"

    async def remove_mcp_server(self, server_id: str) -> str:
        """
        Remove a single server dynamically from config.
        """
        try:
            return await self.unmount_server(server_id)
        except Exception as e:
            logger.exception(f"Failed to remove member server '{server_id}': {e}")
            return f"Failed to remove member server '{server_id}'"

    async def _mount_member_server(self, config: dict) -> str:
        server_id = config["id"]

        if self._server_manager.has_member_server(server_id):
            logger.warning(f"Server '{server_id}' already mounted.")
            return f"Server '{server_id}' already mounted."

        logger.info(f"Building new server with config {config}")
        builder = MCPServerBuilder(config)
        sub_mcp = await builder.build()
        self.mount(server_id, sub_mcp)

        member = MemberMCPServer(
            id=server_id,
            type=config["type"],
            config=config,
            label=config.get("label"),
            tags=config.get("tags", []),
            tool_count=None
        )
        member.set_server(sub_mcp)
        self._server_manager.add_server_db(config)
        self._server_manager.add_member(server_id, member)

        logger.info(f"Mounted MCP server: {server_id}")
        return f"Server '{server_id}' mounted."

    async def unmount_server(self, server_id: str) -> str:
        member = self._server_manager.get(server_id)
        if not member:
            return f"Server '{server_id}' not mounted."
        self.unmount(server_id)
        self._server_manager.remove_mcp_server(server_id)
        self._server_manager.remove_member(server_id)
        return f"Server '{server_id}' unmounted."

    def list_member_servers(self) -> list[dict]:
        logger.info("Listing member servers")
        return [
            {"id": m.id, "server_name": m.get_server().name}
            for m in self._server_manager.list()
        ]
