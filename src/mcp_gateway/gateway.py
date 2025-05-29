import sys
from dotenv import load_dotenv
from fastmcp import FastMCP
from typing import Any, Dict, Optional, Union
from fastmcp.tools.tool import Tool

from mcp_gateway.tools import MCPToolManager
from mcp_gateway.utils import (
    LoggerFactory,
    AllServersValidator,
    ValidationError,
    ServerConfigValidator,
)
from mcp_gateway.member_servers import ServerManager, MemberMCPServer, MCPServerBuilder
from mcp_gateway.store.database import DatabaseInterface
from mcp_gateway.store.cloudant_adapter import CloudantAdapter
from mcp_gateway.store.local_file_adapter import LocalFileAdapter

load_dotenv()


logger = LoggerFactory.get_logger()


class MCPGateway(FastMCP):
    """
    Extended FastMCP server with dynamic runtime server composition.
    """

    def __init__(
        self,
        name: str = "MCPGateway",
        config: Optional[list[dict]] = None,
        database_config: Optional[Union[Dict[str, Any], DatabaseInterface]] = None,
    ):
        super().__init__(name=name)

        database = None
        if database_config:
            try:
                if isinstance(database_config, DatabaseInterface):
                    database = database_config
                elif database_config.get("type") == "cloudant":
                    required_keys = ["api_key", "service_url"]
                    if not all(k in database_config for k in required_keys):
                        raise ValueError(
                            "Missing required Cloudant config keys: api_key, service_url"
                        )

                    database = CloudantAdapter(
                        api_key=database_config["api_key"],
                        service_url=database_config["service_url"],
                        db_name=database_config.get("db_name", "mcp_servers"),
                    )
                else:
                    logger.warning(
                        f"Unsupported database type: {database_config.get('type')}"
                    )
            except Exception as e:
                logger.error(f"Failed to initialize database: {e}")
                raise
        else:
            database = LocalFileAdapter()
            logger.info("No database config provided, using local file storage")

        self._server_manager = ServerManager(database=database)
        self._tool_manager = MCPToolManager()

        self._db_configs: list[dict] = self._server_manager.load_all_servers_db()
        self._config: list[dict] = []
        if config:
            try:
                AllServersValidator(config).validate_all()
                self._config = config
                logger.info("Merged %d configs supplied at launch", len(config))
            except ValidationError as e:
                logger.error("Validation error: %s", e)
                sys.exit(1)

        self.add_tool(self.register_mcp_server)
        self.add_tool(self.remove_mcp_server)
        self.add_tool(self.get_tool_config_by_name)
        self.add_tool(self.get_tool_config_by_server)
        self.add_tool(self.remove_tools)

    async def setup_member_servers(self):
        """
        Mount multiple servers from a JSON list in self.config.
        This runs at startup or from manual trigger.
        """
        all_configs = self._config + self._db_configs
        seen_ids = set()
        logger.info(
            f"Setting up {len(self._config)} CLI servers and {len(self._db_configs)} DB servers..."
        )

        for cfg in all_configs:
            server_id = cfg.get("id")
            if not server_id:
                logger.error("Skipping corrupt config with no 'id': %s", cfg)
                continue

            if server_id in seen_ids:
                logger.debug(f"Skipping duplicate server '{server_id}'")
                continue

            if self._server_manager.has_member_server(server_id):
                logger.debug(f"Server '{server_id}' already mounted, skipping.")
                seen_ids.add(server_id)
                continue

            await self._safe_mount(cfg)
            seen_ids.add(server_id)

    async def _safe_mount(self, cfg: dict):
        try:
            await self._mount_member_server(cfg)
        except Exception as exc:
            logger.error(
                "Failed to mount server '%s': %s", cfg.get("id", "<missing‑id>"), exc
            )

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
        if "id" not in config:
            logger.error("Invalid server config, missing 'id': %s", config)
            return f"Invalid server config, missing 'id': {config}"

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
            tool_count=None,
        )
        member.set_server(sub_mcp)
        self._server_manager.add_server_db(config)
        self._server_manager.add_member(server_id, member)
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

    async def get_tool_config_by_name(self, name: str) -> list[dict]:
        """
        Get a tool configuration details
        """
        all_tools = await self.get_tools()
        if name not in all_tools:
            return [{"message": f"Unknown tool: {name}"}]

        tool_config = self._tool_manager.tool_config(all_tools, name)
        logger.info(f"Tool configuration details by tool name: {tool_config}")
        return tool_config

    async def get_tool_config_by_server(self, server_id: str) -> list[dict]:
        """
        Get all tool configuration details of a specific member server
        """
        if not self._server_manager.get(server_id):
            return [{"message": f"Server '{server_id}' not mounted."}]

        server_tools = await self.get_tools(server_id)
        tool_config = self._tool_manager.tool_config(server_tools)
        logger.info(f"Tool configuration details by server name: {tool_config}")
        return tool_config

    async def remove_tools(self, tools: list[str], server_id: str) -> str:
        """
        Remove a tool or multiple from the servers and gateway
        """
        all_tools = await self.get_tools()
        for tool_name in tools:
            if tool_name not in all_tools:
                return f"Unknown tool: {tool_name}"
        self._server_manager.add_remove_tools(tools, server_id)
        logger.info(f"Removed {tools} tools from server")
        return f"Removed {tools} tool from server"
