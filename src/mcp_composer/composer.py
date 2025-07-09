"""
MCP Composer: A dynamic orchestrator for mounting and managing member MCP servers.
Extends FastMCP with runtime composition, tool management, and database-backed config.
"""

import sys

from typing import Any, Dict, Optional, Union

from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.server.auth.auth import OAuthProvider
from fastmcp.tools.tool import Tool

from mcp_composer.tools import MCPToolManager
from mcp_composer.utils import (
    LoggerFactory,
    AllServersValidator,
    ValidationError,
)
from mcp_composer.member_servers import ServerManager, MemberMCPServer, MCPServerBuilder
from mcp_composer.store.database import DatabaseInterface
from mcp_composer.store.cloudant_adapter import CloudantAdapter
from mcp_composer.store.local_file_adapter import LocalFileAdapter


load_dotenv()

logger = LoggerFactory.get_logger()

class MCPComposer(FastMCP):
    """
    Extended FastMCP server with dynamic runtime server composition.
    """

    def __init__(
        self,
        name: str = "MCPComposer",
        config: Optional[list[dict]] = None,
        database_config: Optional[Union[Dict[str, Any], DatabaseInterface]] = None,
        auth: OAuthProvider | None = None,
    ):
        super().__init__(name=name, auth=auth)

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
                    logger.warning("Unsupported database type: %s", database_config.get("type"))
            except Exception as e:
                logger.error("Failed to initialize database: %s", e)
                raise
        else:
            database = LocalFileAdapter()
            logger.info("No database config provided, using local file storage")

        self._server_manager = ServerManager(database=database)
        self._tool_manager = MCPToolManager(server_manager=self._server_manager, database=database)
        self._db_configs: list[dict] = self._server_manager.load_all_servers_db()
        self._config: list[dict] = []
        self._server_manager._mounted_servers = self._mounted_servers

        if config:
            try:
                AllServersValidator(config).validate_all()
                self._config = config
                logger.info("Merged %d configs supplied at launch", len(config))
            except ValidationError as e:
                logger.error("Validation error: %s", e)
                sys.exit(1)


        self.add_tool(Tool.from_function(self.register_mcp_server))
        self.add_tool(Tool.from_function(self.update_mcp_server_config))
        self.add_tool(Tool.from_function(self.delete_mcp_server))
        self.add_tool(Tool.from_function(self.member_health))
        self.add_tool(Tool.from_function(self.activate_mcp_server))
        self.add_tool(Tool.from_function(self.deactivate_mcp_server))
        self.add_tool(Tool.from_function(self.generate_tool_from_script))
        self.add_tool(Tool.from_function(self._server_manager.list_member_servers))
        self.add_tool(Tool.from_function(self._tool_manager.get_tool_config_by_name))
        self.add_tool(Tool.from_function(self._tool_manager.get_tool_config_by_server))
        self.add_tool(Tool.from_function(self._tool_manager.remove_tools))
        self.add_tool(Tool.from_function(self._tool_manager.update_tool_description))


    async def _mount_member_server(self, config: dict) -> str:
        try:
            if "id" not in config:
                logger.error("Invalid server config, missing 'id': %s", config)
                return f"Invalid server config, missing 'id': {config}"

            server_id = config["id"]
            config["_id"] = server_id

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

            return f"Server {server_id} mounted."

        except Exception as exc:
            logger.error("Failed to mount server '%s': %s", str(config.get("id", "<missing‑id>")), exc)
            return f"Failed to mount server {config.get('id', '<missing‑id>')}"

    async def setup_member_servers(self):
        """
        Mount multiple servers from a JSON list in self.config.
        This runs at startup or from manual trigger.
        """
        all_configs = self._config + self._db_configs

        seen_ids = set()
        logger.info(
            "Setting up %d CLI servers and %d DB servers...",
            len(self._config),
            len(self._db_configs)
        )

        for cfg in all_configs:
            server_id = cfg.get("id")
            if not server_id:
                logger.error("Skipping corrupt config with no 'id': %s", cfg)
                continue

            if cfg.get("status") == "deactivated":
                logger.info("Server '%s' is marked deactivated, skipping mount.", server_id)
                continue

            if server_id in seen_ids:
                logger.debug("Skipping duplicate server '%s'", server_id)
                continue

            if self._server_manager.has_member_server(server_id):
                logger.debug("Server '%s' already mounted, skipping.", server_id)
                seen_ids.add(server_id)
                continue

            await self._mount_member_server(cfg)
            seen_ids.add(server_id)

    async def register_mcp_server(self, config: dict) -> str:
        """Register a single server."""
        logger.info("Registering single server: %s", config)
        return await self._server_manager.register_server(config=config, mount_callback=self.mount)

    async def update_mcp_server_config(self, server_id: str, new_config: dict) -> str:
        """Update the configuration of an existing member server."""
        return await self._server_manager.update_server_config(
            server_id=server_id,
            new_config=new_config,
            unmount_callback=self.unmount,
            mount_callback=self.mount,
        )

    async def delete_mcp_server(self, server_id: str) -> str:
        """Delete a single server."""
        try:
            return await self.unmount_server(server_id)
        except Exception as e:
            logger.exception("Failed to delete member server '%s': %s", server_id, e)
            return f"Failed to delete member server '{server_id}'"

    async def unmount_server(self, server_id: str) -> str:
        """Unmount a member server and remove it from the DB."""
        self._server_manager.check_server_exist(server_id)
        self.unmount(server_id)
        self._server_manager.remove_mcp_server(server_id)
        self._server_manager.remove_member(server_id)
        logger.info("Server %s unmounted", server_id)
        return f"Server '{server_id}' unmounted."

    # async def get_tools(self, server_id: str | None = None) -> dict[str, Tool]:
    #     """Return tools for a specific server or all servers."""
    #     if (tools := self._cache.get("tools")) is self._cache.NOT_FOUND:
    #         tools = await self._tool_manager.get_all_tools(server_id=server_id)
    #         self._cache.set("tools", tools)
    #     return tools

    async def member_health(self) -> list[dict]:
        """Get status for all member servers."""
        return await self._server_manager.member_health(self._server_manager.list())

    async def activate_mcp_server(
            self, server_id: str
        ) -> str:
        """Reactivates a previously deactivated member server."""
        return await self._server_manager.activate_server(
            server_id=server_id, mount_callback=self.mount
        )

    async def deactivate_mcp_server(self, server_id: str) -> str:
        """Deactivates a member server by unmounting it and marking it as deactivated."""
        return self._server_manager.deactivate_server(
            server_id=server_id, unmount_callback=self.unmount
        )

    async def generate_tool_from_script(self, tool_config: dict) -> str:
        """Create a tool from a python script."""
        fn = await self._tool_manager.tool_from_script(tool_config)
        if fn:
            self.add_tool(Tool.from_function(fn))
        return "Successfully added tools"
