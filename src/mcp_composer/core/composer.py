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
from mcp_composer.core.tools import MCPToolManager
from mcp_composer.core.utils import (
    LoggerFactory,
    AllServersValidator,
    ValidationError,
    get_version_adapter,
)
from mcp_composer.core.member_servers import (
    ServerManager,
    MemberMCPServer,
    MCPServerBuilder,
)
from mcp_composer.core.settings.version_control_manager import ConfigManager
from mcp_composer.store.database import DatabaseInterface
from mcp_composer.store.cloudant_adapter import CloudantAdapter
from mcp_composer.store.local_file_adapter import LocalFileAdapter
from mcp_composer.core.utils.tools import tool_from_open_api, tool_from_script
from mcp_composer.core.prompts import MCPPromptManager
from mcp_composer.core.resources import MCPResourceManager

load_dotenv()

logger = LoggerFactory.get_logger()
# pylint: disable=W0718


class MCPComposer(FastMCP):
    """
    Extended FastMCP server with dynamic runtime server composition.
    """

    def __init__(
        self,
        name: str = "MCPComposer",
        config: Optional[list[dict]] = None,
        database_config: Optional[Union[Dict[str, Any], DatabaseInterface]] = None,
        version_adapter_config: Optional[Dict[str, Any]] = None,
        auth: OAuthProvider | None = None,
    ):
        super().__init__(name=name, auth=auth)
        self._config_manager = ConfigManager(
            get_version_adapter(version_adapter_config)
        )

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
                        "Unsupported database type: %s", database_config.get("type")
                    )
            except Exception as e:
                logger.error("Failed to initialize database: %s", e)
                raise
        else:
            database = LocalFileAdapter()
            logger.info("No database config provided, using local file storage")

        self._server_manager = ServerManager(
            database=database, config_manager=self._config_manager
        )
        self._tool_manager = MCPToolManager(
            composer=self, server_manager=self._server_manager, database=database
        )
        self._resource_manager = MCPResourceManager(
            server_manager=self._server_manager, database=database
        )
        self._prompt_manager = MCPPromptManager(
            server_manager=self._server_manager, database=database
        )

        self._db_configs: list[dict] = self._server_manager.load_all_servers_db()
        self._config: list[dict] = []
        if config:
            if not isinstance(config, list):
                raise TypeError("Config must be a list of server configurations")
            try:
                AllServersValidator(config).validate_all()
                self._config = config
                logger.info("Merged %d configs supplied at launch", len(config))
            except ValidationError as e:
                logger.error("Validation error: %s", e)
                sys.exit(1)

        # Server Management Tools
        server_tools = [
            self.register_mcp_server,
            self.update_mcp_server_config,
            self.delete_mcp_server,
            self.member_health,
            self.activate_mcp_server,
            self.deactivate_mcp_server,
            self.add_tools,
            self.add_tools_from_openapi,
            self._server_manager.list_member_servers,
        ]

        # Tool Management Tools
        tool_management_tools = [
            self._tool_manager.get_tool_config_by_name,
            self._tool_manager.get_tool_config_by_server,
            self._tool_manager.disable_tools,
            self._tool_manager.enable_tools,
            # Uncomment if needed:
            # self._tool_manager.disable_tools_by_server,
            # self._tool_manager.enable_tools_by_server,
            self._tool_manager.update_tool_description,
        ]

        # Prompt Management Tools
        prompt_tools = [
            self.add_prompts,
            self.get_all_prompts,
            self.list_prompts_per_server,
            self.filter_prompts,
            self.disable_prompts,
            self.enable_prompts,
        ]

        # Resource Management Tools
        resource_tools = [
            self.create_resource,
            self.create_resource_template,
            self.list_resources,
            self.list_resource_templates,
            self.list_resources_per_server,
            self.filter_resources,
            self.disable_resources,
            self.enable_resources,
        ]

        # Register all tools
        for tool_func in (
            server_tools + tool_management_tools + prompt_tools + resource_tools
        ):
            self.add_tool(Tool.from_function(tool_func))

    async def _load_custom_tools(self):
        """Load tools using saved OpenAPI, Curl, and Python script."""
        server_data = await self._tool_manager.load_custom_tools()
        for name, client in server_data.items():
            await self.import_server(
                self.from_openapi(client[0], client[1]),  # type: ignore
                name,
            )

    async def _mount_member_server(self, config: dict) -> str:
        try:
            if "id" not in config:
                logger.error("Invalid server config, missing 'id': %s", config)
                return f"Invalid server config, missing 'id': {config}"

            server_id = config["id"]
            builder = MCPServerBuilder(config)
            sub_mcp = await builder.build()
            self.mount(sub_mcp, server_id)

            member = MemberMCPServer(
                id=server_id,
                type=config["type"],
                config=config,
                label=config.get("label", ""),
                tags=config.get("tags", []),
                tool_count=None,
                disabled_tools=config.get("disabled_tools", []),
                disabled_prompts=config.get("disabled_prompts", []),
                tools_description=config.get("tools_description", {}),
            )
            member.set_server(sub_mcp)
            self._server_manager.add_server_db(config)
            self._server_manager.add_member(server_id, member)

            return f"Server {server_id} mounted."

        except Exception as exc:
            logger.exception(
                "Failed to mount server '%s': %s",
                str(config.get("id", "<missing-id>")),
                exc,
            )
            return f"Failed to mount server {config.get('id', '<missing‑id>')}"

    async def setup_member_servers(self):
        """
        Mount multiple servers from a JSON list in self.config.
        This runs at startup or from manual trigger.
        """
        all_configs = self._config + self._db_configs
        if not all_configs:
            logger.warning("No server configurations found to mount.")
            return
        logger.info("Setting up %d servers from config", len(all_configs))
        seen_ids = set()
        logger.info(
            "Setting up %d CLI servers and %d DB servers...",
            len(self._config),
            len(self._db_configs),
        )

        for cfg in all_configs:
            server_id = cfg.get("id")
            server_type = cfg.get("type")

            if server_type == "composer":
                self._tool_manager._disabled_tools = cfg.get(
                    "disabled_tools", []
                )  # pylint: disable=W0212
                logger.info("Disabled tool list in composer: %s", cfg)
                continue

            if not server_id:
                logger.error("Skipping corrupt config with no 'id': %s", cfg)
                continue

            if cfg.get("status") == "deactivated":
                logger.info(
                    "Server '%s' is marked deactivated, skipping mount.", server_id
                )
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
        await self._load_custom_tools()

    async def register_mcp_server(self, config: dict) -> str:
        """Register a single server."""
        logger.info("Registering single server: %s", config)
        return await self._server_manager.register_server(
            config=config, mount_callback=self.mount
        )

    async def update_mcp_server_config(self, server_id: str, new_config: dict) -> str:
        """Update the configuration of an existing member server."""
        return await self._server_manager.update_server_config(
            server_id=server_id,
            new_config=new_config,
            unmount_callback=self._tool_manager.unmount,
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
        self._tool_manager.unmount(server_id)
        self._server_manager.remove_mcp_server(server_id)
        self._server_manager.remove_member(server_id)
        logger.info("Server %s unmounted", server_id)
        return f"Server '{server_id}' unmounted."

    async def member_health(self) -> list[dict]:
        """Get status for all member servers."""
        return await self._server_manager.member_health(self._server_manager.list())

    async def activate_mcp_server(self, server_id: str) -> str:
        """Reactivates a previously deactivated member server."""
        return await self._server_manager.activate_server(
            server_id=server_id, mount_callback=self.mount
        )

    async def deactivate_mcp_server(self, server_id: str) -> str:
        """Deactivates a member server by unmounting it and marking it as deactivated."""
        return self._server_manager.deactivate_server(
            server_id=server_id, unmount_callback=self._tool_manager.unmount
        )

    async def add_tools(self, tool_config: dict) -> str:
        """Create a tool from a python script."""
        fn = await tool_from_script(tool_config)
        if fn:
            self.add_tool(Tool.from_function(fn))
        return "Successfully added tools"

    async def add_tools_from_openapi(
        self, openapi_spec: dict, auth_config: dict | None = None
    ) -> str:
        """Create a tool from OpenAPI Specification"""
        server_name, client = await tool_from_open_api(openapi_spec, auth_config)
        await self.import_server(
            self.from_openapi(openapi_spec, client),  # type: ignore
            server_name,
        )
        return "Successfully added tools"

    def add_prompts(self, prompt_config: Union[dict, list[dict]]) -> list[str]:
        """
        Add one or more prompts based on the provided configuration.
        Returns a list of registered prompt names.
        """
        return self._prompt_manager.add_prompts(prompt_config)

    async def get_all_prompts(self) -> list[str]:
        """Get all registered prompts mapped to their textual form from composer and mounted servers."""
        prompts_dict = await self._prompt_manager.get_prompts()
        return [str(prompt) for prompt in prompts_dict.values()]

    async def list_prompts_per_server(self, server_id: str) -> list[dict]:
        """List all prompts from a specific server."""
        return await self._prompt_manager.list_prompts_per_server(server_id)

    async def filter_prompts(self, filter_criteria: dict) -> list[dict]:
        """Filter prompts based on criteria like name, description, tags, etc."""
        return await self._prompt_manager.filter_prompts(filter_criteria)

    async def disable_prompts(self, prompts: list[str], server_id: str) -> str:
        """
        Disable a prompt or multiple prompts from the member server
        """
        return await self._prompt_manager.disable_prompts(prompts, server_id)

    async def enable_prompts(self, prompts: list[str], server_id: str) -> str:
        """
        Enable a prompt or multiple prompts from the member server
        """
        return await self._prompt_manager.enable_prompts(prompts, server_id)

    async def create_resource_template(self, resource_config: dict) -> str:
        """Add a resource template to the composer."""
        return await self._resource_manager.create_resource_template(resource_config)

    async def create_resource(self, resource_config: dict) -> str:
        """Create a resource in the composer."""
        return await self._resource_manager.create_resource(resource_config)

    async def list_resource_templates(self) -> list[dict]:
        """List all available resource templates from composer and mounted servers."""
        templates = await self._resource_manager.list_resource_templates()
        return [
            {
                "name": template.name,
                "description": template.description,
                "uri_template": str(template.uri_template),
                "mime_type": template.mime_type,
                "tags": list(template.tags) if template.tags else [],
            }
            for template in templates
        ]

    async def list_resources(self) -> list[dict]:
        """List all available resources from composer and mounted servers."""
        resources = await self._resource_manager.list_resources()
        return [
            {
                "name": resource.name,
                "description": resource.description,
                "uri": str(resource.uri),
                "mime_type": resource.mime_type,
                "tags": list(resource.tags) if resource.tags else [],
            }
            for resource in resources
        ]

    async def list_resources_per_server(self, server_id: str) -> list[dict]:
        """List all resources from a specific server."""
        return await self._resource_manager.list_resources_per_server(server_id)

    async def filter_resources(self, filter_criteria: dict) -> list[dict]:
        """Filter resources based on criteria like name, description, tags, etc."""
        return await self._resource_manager.filter_resources(filter_criteria)

    async def disable_resources(self, resources: list[str], server_id: str) -> str:
        """
        Disable a resource or multiple resources from the member server
        """
        return await self._resource_manager.disable_resources(resources, server_id)

    async def enable_resources(self, resources: list[str], server_id: str) -> str:
        """
        Enable a resource or multiple resources from the member server
        """
        return await self._resource_manager.enable_resources(resources, server_id)
