"""
MCP Composer: A dynamic orchestrator for mounting and managing member MCP servers.
Extends FastMCP with runtime composition, tool management, and database-backed config.
"""

import os
import sys
from typing import Any, Dict, Optional, Union, Literal, Sequence
from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.server.auth.auth import OAuthProvider
from fastmcp.server.auth.providers.jwt import JWTVerifier
from starlette.middleware import Middleware as ASGIMiddleware
from fastmcp.tools.tool import Tool
from fastmcp.resources.resource import Resource
from fastmcp.resources.template import ResourceTemplate
from mcp_composer.core.tools import MCPToolManager
from mcp_composer.core.utils import LoggerFactory
from mcp_composer.core.utils.banner import print_mcp_composer_banner
from mcp_composer.core.member_servers import (
    ServerManager,
    MemberMCPServer,
    MCPServerBuilder,
)
from mcp_composer.core.config.server_configuration_manager import (
    ServerConfigurationManager,
)
from mcp_composer.core.utils.custom_tool import DynamicToolGenerator, OpenApiTool
from mcp_composer.core.utils.utils import get_endpoint_from_config
from mcp_composer.store.database import DatabaseInterface
from mcp_composer.core.utils.tools import (
    tool_from_curl,
    tool_from_open_api,
    tool_from_script,
)
from mcp_composer.core.prompts import MCPPromptManager
from mcp_composer.core.resources import MCPResourceManager
from mcp_composer.a2a_service.a2a_mcp import (
    register_agent,
    list_agents,
    unregister_agent,
    send_message,
    get_task_result,
    cancel_task,
    load_registered_agents,
    get_agent_cards,
    get_agent_card,
)

load_dotenv()

logger = LoggerFactory.get_logger()
# pylint: disable=W0718


class MCPComposer(FastMCP):
    """
    Extended FastMCP server with dynamic runtime server composition.
    """

    # pylint: disable=too-many-instance-attributes,too-many-public-methods

    # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals,too-many-branches,too-many-statements
    def __init__(
        self,
        name: str = "",
        config: Optional[Union[list[dict], str]] = None,
        database_config: Optional[Union[Dict[str, Any], DatabaseInterface]] = None,
        version_adapter_config: Optional[Dict[str, Any]] = None,
        auth: OAuthProvider | JWTVerifier | None = None,
    ):
        super().__init__(name=name, auth=auth)

        # Initialize configuration manager
        self._server_config_manager = ServerConfigurationManager(
            version_adapter_config=version_adapter_config
        )

        # Get database from configuration
        logger.info("looking for DB config MCP Composer with name: %s", name)

        env_db_config = self._get_database_config_from_env()
        effective_db_config = env_db_config or database_config

        if effective_db_config:
            logger.info("Database configuration found" )
            try:
                if isinstance(effective_db_config, DatabaseInterface):
                    database = effective_db_config
                    logger.info(
                        "Database configuration loaded successfully (Custom Database Interface)"
                    )
                elif effective_db_config.get("type") == "cloudant":
                    required_keys = ["api_key", "service_url"]
                    if not all(k in effective_db_config for k in required_keys):
                        error_msg = "Missing required Cloudant config keys: api_key, service_url"
                        logger.error("Database configuration error: %s", error_msg)
                        raise ValueError(error_msg)

                    database = CloudantAdapter(
                        api_key=effective_db_config["api_key"],
                        service_url=effective_db_config["service_url"],
                        db_name=effective_db_config.get("db_name", "mcp_server"),
                    )
                    logger.info("Database configuration loaded successfully (Cloudant)")
                elif effective_db_config.get("type") == "local_file":
                    # Only use LocalFileAdapter if explicitly configured
                    database = LocalFileAdapter(
                        file_path=effective_db_config.get("file_path")
                    )
                    logger.info(
                        "Database configuration loaded successfully (Local File)"
                    )
                elif effective_db_config.get("type") == "postgres":
                    # Check if URL is provided (preferred method)
                    if "url" in effective_db_config:
                        database = PostgresAdapter(
                            url=effective_db_config["url"],
                            table_name=effective_db_config.get(
                                "table_name", "mcp_servers"
                            ),
                        )
                        logger.info(
                            "Database configuration loaded successfully (PostgreSQL via URL)"
                        )
                    else:
                        # Use individual parameters
                        required_keys = ["host", "database", "user", "password"]
                        if not all(k in effective_db_config for k in required_keys):
                            error_msg = (
                                "Missing required PostgreSQL config keys: host, "
                                "database, user, password (or provide 'url')"
                            )
                            logger.error("Database configuration error: %s", error_msg)
                            raise ValueError(error_msg)

                        database = PostgresAdapter(
                            host=effective_db_config["host"],
                            port=effective_db_config.get("port", 5432),
                            database=effective_db_config["database"],
                            user=effective_db_config["user"],
                            password=effective_db_config["password"],
                            table_name=effective_db_config.get(
                                "table_name", "mcp_servers"
                            ),
                        )
                        logger.info(
                            "Database configuration loaded successfully (PostgreSQL)"
                        )
                else:
                    error_msg = (
                        f"Unsupported database type: {effective_db_config.get('type')}"
                    )
                    logger.error("Database configuration error: %s", error_msg)
                    raise ValueError(error_msg)
            except Exception as e:
                logger.error("Failed to initialize database: %s", e)
                raise
        else:
            # No database config provided - check if local file storage is enabled via env
            logger.info("No database configuration provided")
            use_local_file = (
                os.getenv("MCP_USE_LOCAL_FILE_STORAGE", "false").strip().lower()
            )
            if use_local_file in ("true", "1", "yes", "on"):
                database = LocalFileAdapter()
                logger.info("Local file storage enabled via environment variable")
            else:
                logger.info(
                    "No database configured - running without persistent storage"
                )


        self._server_manager = ServerManager(
            database=database, config_manager=self._server_config_manager.config_manager
        )
        self._tool_manager = MCPToolManager(
            composer=self, server_manager=self._server_manager, database=database
        )
        self._resource_manager = MCPResourceManager(
            server_manager=self._server_manager, database=database
        )
        self._resource_manager.schedule_persisted_restore()
        self._prompt_manager = MCPPromptManager(
            server_manager=self._server_manager, database=database
        )
        # Load prompts from database on startup
        self._prompt_manager.load_prompts_from_db()

        self._db_configs: list[dict] = self._server_manager.load_all_servers_db()

        # Process server configuration
        self._server_config_manager.process_config(config, composer=self)

        # Define tool categories
        server_tools = [
            self.register_mcp_server,
            self.update_mcp_server_config,
            self.delete_mcp_server,
            self.member_health,
            self.activate_mcp_server,
            self.deactivate_mcp_server,
            self._server_manager.list_servers,
        ]

        # Tools which will add tools dynamically from Python script
        # Curl command and OpenAPI specification
        dynamic_tool_generator = []
        if os.getenv("ENABLE_ADD_TOOLS_USING_PYTHON", "false").lower() == "true":
            dynamic_tool_generator = [
                self.add_tools_from_python,
            ]
        self.add_resource(
            Resource.from_function(
                get_agent_cards,
                uri="resource://agent_cards/list",
                mime_type="application/json",
            )
        )

        self.add_template(
            ResourceTemplate.from_function(
                get_agent_card,
                uri_template="agent://agent_cards/{card_name}",
                mime_type="application/json",
                description="Retrieves a specific agent card by name.",
            )
        )

        load_registered_agents()
        a2a_tools = [
            register_agent,
            list_agents,
            unregister_agent,
            send_message,
            get_task_result,
            cancel_task,
        ]
        tool_management_tools = [
            self._tool_manager.get_tool_config_by_name,
            self._tool_manager.get_tool_config_by_server,
            self._tool_manager.disable_tools,
            self._tool_manager.enable_tools,
            self._tool_manager.update_tool_description,
            self.filter_tool,
            self.add_tools_from_curl,
            self.add_tools_from_openapi,
            self.rollback_openapi_tool_version,
            self.rollback_curl_tool_version,
            # Optional tools:
            # self._tool_manager.disable_tools_by_server,
            # self._tool_manager.enable_tools_by_server,
        ]

        prompt_tools = [
            self.add_prompts,
            self.get_all_prompts,
            self.list_prompts_per_server,
            self.filter_prompts,
            self.disable_prompts,
            self.enable_prompts,
            self.delete_prompts,
        ]

        resource_tools = [
            self.create_resource,
            self.create_resource_template,
            self.list_resources,
            self.list_resource_templates,
            self.list_resources_per_server,
            self.filter_resources,
            self.disable_resources,
            self.enable_resources,
            self.delete_resources,
        ]

        # Combine all tools into a single list
        all_tools = (
            server_tools
            + dynamic_tool_generator
            + tool_management_tools
            + prompt_tools
            + resource_tools
            + a2a_tools
        )

        # Register all tools
        for tool_func in all_tools:
            self.add_tool(Tool.from_function(tool_func))

    @property
    def resource_manager(self) -> MCPResourceManager:
        """Expose the resource manager for tool integration."""
        return self._resource_manager

    async def _load_custom_tools(self):
        """Load tools using saved OpenAPI, Curl, and Python script."""
        server_data = await self._tool_manager.load_custom_tools()
        for name, client in server_data.items():
            self.mount(
                self.from_openapi(client[0], client[1]),  # type: ignore
                namespace=name,
            )

    async def _mount_member_server(self, config: dict) -> str:
        try:
            if "id" not in config:
                logger.error("Invalid server config, missing 'id': %s", config)
                return f"Invalid server config, missing 'id': {config}"

            server_id = config["id"]
            builder = MCPServerBuilder(config)
            external_mcp = await builder.build()
            self.mount(external_mcp, server_id)

            member = MemberMCPServer(
                id=server_id,
                endpoint=get_endpoint_from_config(config),
                type=config["type"],
                config=config,
                label=config.get("label", ""),
                tags=config.get("tags", []),
                tool_count=None,
                disabled_tools=config.get("disabled_tools", []),
                disabled_prompts=config.get("disabled_prompts", []),
                tools_description=config.get("tools_description", {}),
            )
            member.set_server(external_mcp)
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

    # pylint: disable=too-many-branches,too-many-statements
    async def setup_member_servers(self):
        """
        Mount multiple servers from a JSON list in self.config.
        This runs at startup or from manual trigger.
        """
        await self._load_custom_tools()

        # Apply unified configuration if loaded
        if (
            self._server_config_manager.unified_config_applied
            and self._server_config_manager.unified_config
        ):
            await self._server_config_manager.apply_unified_config(self)

        all_configs = self._server_config_manager.config + self._db_configs
        if not all_configs:
            logger.warning("No server configurations found to mount.")
            return
        logger.info("Setting up %d servers from config", len(all_configs))
        seen_ids = set()
        logger.info(
            "Setting up %d CLI servers and %d DB servers...",
            len(self._server_config_manager.config),
            len(self._db_configs),
        )

        for cfg in all_configs:
            server_id = cfg.get("id")
            server_type = cfg.get("type")

            if server_type == "composer":
                new_disabled_tools = cfg.get("disabled_tools", [])
                # pylint: disable=protected-access
                combined_unique_tools = set(self._tool_manager._disabled_tools)
                combined_unique_tools.update(new_disabled_tools)
                self._tool_manager._disabled_tools = list(combined_unique_tools)
                # pylint: enable=protected-access
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

            result = await self._mount_member_server(cfg)
            if result.startswith("Failed to mount server"):
                logger.error("Failed to mount server '%s': %s", server_id, result)
            else:
                logger.info("Successfully mounted server '%s'", server_id)
            seen_ids.add(server_id)

    async def register_mcp_server(self, config: dict) -> str:
        """Register a single server."""
        logger.info("Registering single server: %s", config)
        return await self._server_manager.register_server(
            config=config, mcp_composer=self
        )

    async def update_mcp_server_config(self, server_id: str, new_config: dict) -> str:
        """Update the configuration of an existing member server."""
        return await self._server_manager.update_server_config(
            server_id=server_id,
            new_config=new_config,
            mcp_composer=self,
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
            server_id=server_id, mcp_composer=self
        )

    async def deactivate_mcp_server(self, server_id: str) -> str:
        """Deactivates a member server by unmounting it and marking it as deactivated."""
        return self._server_manager.deactivate_server(
            server_id=server_id, mcp_composer=self
        )

    async def add_tools_from_curl(self, tool_config: dict) -> str:
        """Create a tool from a curl command."""
        fn = await tool_from_curl(tool_config)
        if fn:
            self.add_tool(Tool.from_function(fn))
        return "Successfully added tools"

    async def add_tools_from_python(self, tool_config: dict) -> str:
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
        self.mount(
            FastMCP.from_openapi(openapi_spec, client),
            namespace=server_name,
        )
        return "Successfully added tools"

    async def rollback_openapi_tool_version(self, name: str, version: str) -> str:
        """Rollback to the specific version of OpenAPI"""
        OpenApiTool.set_rollback_version(name, version)
        self._tool_manager.unmount(name)
        await self._load_custom_tools()
        return f"OpenAPI tools successfully roll backed to version: {version}"

    async def rollback_curl_tool_version(self, name: str, version: str) -> str:
        """Rollback to the specific version of OpenAPI"""
        DynamicToolGenerator.set_rollback_version(name, version)
        self.remove_tool(name)
        await self._load_custom_tools()
        return f"Successfully roll backed to version: {version}"

    async def filter_tool(self, keyword: str):
        """Filter tools by keyword"""
        return await self._tool_manager.filter_tool_by_keyword(keyword)

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

    def delete_prompts(self, prompt_names: Union[str, list[str]]) -> dict:
        """
        Delete one or more prompts from the composer and database.

        Args:
            prompt_names: Single prompt name or list of prompt names to delete

        Returns:
            dict: Dictionary with prompt names as keys and status messages as values

        Example:
            # Delete a single prompt
            result = composer.delete_prompts("my_prompt")

            # Delete multiple prompts
            result = composer.delete_prompts(["prompt1", "prompt2"])
        """
        return self._prompt_manager.delete_prompts(prompt_names)

    async def create_resource_template(self, resource_config: dict) -> str:
        """Add a resource template to the composer."""
        return await self._resource_manager.create_resource_template(resource_config)

    async def create_resource(self, resource_config: dict) -> str:
        """Create a resource in the composer."""
        return await self._resource_manager.create_resource(resource_config)

    async def list_resource_templates(  # type: ignore[override]
        self, run_middleware: bool = True
    ) -> Sequence[ResourceTemplate]:
        """List all available resource templates from composer and mounted servers."""
        templates = await self._resource_manager.list_resource_templates()
        result = []
        for template in templates:
            result.append(
                {
                    "name": template.name,
                    "description": template.description,
                    "uri_template": str(template.uri_template),
                    "mime_type": template.mime_type,
                    "parameters": template.parameters or {},
                    "tags": list(template.tags) if template.tags else [],
                }
            )
        return result  # type: ignore[return-value]

    async def list_resources(  # type: ignore[override]
        self, run_middleware: bool = True
    ) -> Sequence[Resource]:
        """List all available resources from composer and mounted servers."""
        resources = await self._resource_manager.list_resources()
        result = []
        for resource in resources:
            result.append(
                {
                    "name": resource.name,
                    "description": resource.description,
                    "uri": str(resource.uri),
                    "mime_type": resource.mime_type,
                    "tags": list(resource.tags) if resource.tags else [],
                }
            )
        return result  # type: ignore[return-value]

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

    async def delete_resources(
        self, resources: list[str], resource_type: str | None = None
    ) -> str:
        """
        Delete one or more stored resources or templates.
        """
        return await self._resource_manager.delete_resources(resources, resource_type)

    async def disable_composer_tool(self, tools: Optional[list[str]] = None) -> str:
        """
        Disable a tool or multiple tools in the composer server
        """
        return await self._tool_manager.disable_composer_tool(tools)

    async def run_stdio_async(
        self,
        show_banner: bool = True,
        log_level: str | None = None,
        stateless: bool = False,
    ) -> None:
        """
        Override the default banner to display MCP Composer branding when using stdio.
        """
        if show_banner:
            print_mcp_composer_banner(
                server_name=self.name or "mcp-composer",
                transport="stdio",
            )
        await super().run_stdio_async(
            show_banner=False, log_level=log_level, stateless=stateless
        )

    async def run_http_async(
        self,
        show_banner: bool = True,
        transport: Literal["http", "streamable-http", "sse"] = "http",
        host: str | None = None,
        port: int | None = None,
        log_level: str | None = None,
        path: str | None = None,
        uvicorn_config: dict[str, Any] | None = None,
        middleware: list[ASGIMiddleware] | None = None,
        json_response: bool | None = None,
        stateless_http: bool | None = None,
        stateless: bool | None = None,
    ) -> None:
        """
        Override the default banner to display MCP Composer branding for HTTP transports.
        """
        if show_banner:
            print_mcp_composer_banner(
                server_name=self.name or "mcp-composer",
                transport=transport,
                host=host,
                port=port,
                path=path,
            )
        await super().run_http_async(
            show_banner=False,
            transport=transport,
            host=host,
            port=port,
            log_level=log_level,
            path=path,
            uvicorn_config=uvicorn_config,
            middleware=middleware,
            json_response=json_response,
            stateless_http=stateless_http,
            stateless=stateless,
        )
