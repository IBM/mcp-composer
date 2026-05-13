"""
MCP Composer: A dynamic orchestrator for mounting and managing member MCP servers.
Extends FastMCP with runtime composition, tool management, and database-backed config.
"""

import os
from typing import Any, Callable, Literal
from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.server.auth.auth import OAuthProvider
from fastmcp.server.auth.providers.jwt import JWTVerifier
from starlette.middleware import Middleware as ASGIMiddleware
from fastmcp.resources import Resource, ResourceTemplate
from fastmcp.tools import Tool
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
)

load_dotenv()

logger = LoggerFactory.get_logger()


def _json_safe_tool_payload(value: Any) -> Any:
    """Recursively normalize tool payload values to JSON-safe data."""
    if isinstance(value, dict):
        return {
            key: safe_val
            for key, val in value.items()
            if key
            not in {"fn", "serializer", "auth", "task_config", "x-fastmcp-wrap-result"}
            if (safe_val := _json_safe_tool_payload(val)) is not None
        }
    if isinstance(value, set):
        items = sorted(
            safe_item
            for item in value
            if (safe_item := _json_safe_tool_payload(item)) is not None
        )
        return items or None
    if isinstance(value, list | tuple):
        items = [
            safe_item
            for item in value
            if (safe_item := _json_safe_tool_payload(item)) is not None
        ]
        return items or None
    if callable(value):
        return None
    return value


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
        config: list[dict] | str | None = None,
        database_config: dict[str, Any] | DatabaseInterface | None = None,
        version_adapter_config: dict[str, Any] | None = None,
        auth: OAuthProvider | JWTVerifier | None = None,
        isv_validator: Any = None,
    ):
        super().__init__(name=name, auth=auth)
        # Track mounted servers for multi-route HTTP (disabled by default)
        # Enable by setting ENABLE_MULTI_SERVER_HTTP_ROUTING=true in .env
        self._enable_multi_server_routing = (
            os.getenv("ENABLE_MULTI_SERVER_HTTP_ROUTING", "false").lower() == "true"
        )
        self._http_mounted_servers: dict[str, Any] = {}
        # Store ISV validator for multi-server HTTP routing authentication
        self._isv_validator = isv_validator

        logger.info("Initializing MCP Composer with name: %s", name)
        self._server_config_manager = self._initialize_config_manager(
            version_adapter_config
        )
        database = self._initialize_database(name, database_config)
        self._initialize_managers(database)
        self._load_initial_state(config)
        self._register_startup_tools()
        logger.info("MCP Composer initialization completed for name: %s", name)

    def _initialize_config_manager(
        self, version_adapter_config: dict[str, Any] | None
    ) -> ServerConfigurationManager:
        """Initialize the server configuration manager."""
        logger.info("Initializing server configuration manager")
        try:
            return ServerConfigurationManager(
                version_adapter_config=version_adapter_config
            )
        except Exception:
            logger.exception("Failed to initialize server configuration manager")
            raise

    def _initialize_database(
        self,
        name: str,
        database_config: dict[str, Any] | DatabaseInterface | None,
    ) -> DatabaseInterface | None:
        """Resolve the database backend from configuration."""
        logger.info("Looking for DB config for MCP Composer with name: %s", name)
        try:
            database = self._server_config_manager.get_database_from_config(
                database_config
            )
            if database is None:
                logger.info(
                    "No database configured for MCP Composer '%s'; continuing without persistence",
                    name,
                )
            return database
        except Exception:
            logger.exception(
                "Failed to initialize database for MCP Composer '%s'", name
            )
            raise

    def _initialize_managers(self, database: DatabaseInterface | None) -> None:
        """Initialize server, tool, resource, and prompt managers."""
        logger.info("Initializing MCP Composer managers")
        try:
            self._server_manager = ServerManager(
                database=database,
                config_manager=self._server_config_manager.config_manager,
            )
            self._tool_manager = MCPToolManager(
                composer=self, server_manager=self._server_manager, database=database
            )
            self._resource_manager = MCPResourceManager(
                composer=self, server_manager=self._server_manager, database=database
            )
            self._resource_manager.schedule_persisted_restore()
            self._prompt_manager = MCPPromptManager(
                server_manager=self._server_manager, database=database
            )
            self._prompt_manager.load_prompts_from_db()
        except Exception:
            logger.exception("Failed to initialize MCP Composer managers")
            raise

    def _load_initial_state(self, config: list[dict[str, Any]] | str | None) -> None:
        """Load persisted server state and process startup configuration."""
        logger.info("Loading MCP Composer startup state")
        try:
            self._db_configs = self._server_manager.load_all_servers_db()
            self._server_config_manager.process_config(config, composer=self)
        except Exception:
            logger.exception("Failed to load MCP Composer startup state")
            raise

    def _register_startup_tools(self) -> None:
        """Register all built-in startup tools."""
        logger.info("Registering MCP Composer startup tools")
        try:
            for tool_func in self._get_all_startup_tools():
                self.add_tool(Tool.from_function(tool_func))
        except Exception:
            logger.exception("Failed to register MCP Composer startup tools")
            raise

    def _get_all_startup_tools(self) -> list[Any]:
        """Collect all tools that should be registered at startup."""
        load_registered_agents()
        return (
            self._get_server_tools()
            + self._get_dynamic_tool_generators()
            + self._get_tool_management_tools()
            + self._get_prompt_tools()
            + self._get_resource_tools()
            + self._get_a2a_tools()
        )

    def _get_server_tools(self) -> list[Any]:
        """Get server management tools."""
        return [
            self.register_mcp_server,
            self.update_mcp_server_config,
            self.delete_mcp_server,
            self.member_health,
            self.activate_mcp_server,
            self.deactivate_mcp_server,
            self._server_manager.list_servers,
        ]

    def _get_dynamic_tool_generators(self) -> list[Any]:
        """Get optional dynamic tool generators."""
        if os.getenv("ENABLE_ADD_TOOLS_USING_PYTHON", "false").lower() == "true":
            return [self.add_tools_from_python]
        return []

    def _get_tool_management_tools(self) -> list[Any]:
        """Get tool management tools."""
        return [
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
            # self.get_available_tools,
            # Optional tools:
            # self._tool_manager.disable_tools_by_server,
            # self._tool_manager.enable_tools_by_server,
        ]

    def _get_prompt_tools(self) -> list[Any]:
        """Get prompt management tools."""
        return [
            self.add_prompts,
            self.get_all_prompts,
            self.list_prompts_per_server,
            self.filter_prompts,
            self.disable_prompts,
            self.enable_prompts,
            self.delete_prompts,
        ]

    def _get_resource_tools(self) -> list[Any]:
        """Get resource management tools."""
        return [
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

    def _get_a2a_tools(self) -> list[Any]:
        """Get A2A integration tools."""
        return [
            register_agent,
            list_agents,
            unregister_agent,
            send_message,
            get_task_result,
            cancel_task,
        ]

    @property
    def resource_manager(self) -> MCPResourceManager:
        """Expose the resource manager for tool integration."""
        return self._resource_manager

    async def _load_custom_tools(self):
        """Load tools using saved OpenAPI, Curl, and Python script."""
        server_data = await self._tool_manager.load_custom_tools()
        for name, client in server_data.items():
            self.mount(self.from_openapi(client[0], client[1]), name)  # type: ignore[arg-type]

    async def _mount_member_server(self, config: dict[str, Any]) -> str:
        try:
            if "id" not in config:
                logger.error("Invalid server config, missing 'id': %s", config)
                return f"Invalid server config, missing 'id': {config}"

            server_id = config["id"]
            builder = MCPServerBuilder(config)
            external_mcp = await builder.build()
            self.mount(external_mcp, server_id)

            # Store for HTTP routing if enabled
            logger.info(
                "Multi-server routing enabled: %s (ENABLE_MULTI_SERVER_HTTP_ROUTING=%s)",
                self._enable_multi_server_routing,
                os.getenv("ENABLE_MULTI_SERVER_HTTP_ROUTING", "not set"),
            )

            if self._enable_multi_server_routing:
                self._http_mounted_servers[server_id] = external_mcp

                # IMPORTANT: In FastMCP, middleware execution order is REVERSE of addition order
                # Last added middleware executes FIRST
                # Desired execution order: ToolPrefixMiddleware → Composer Middleware → ListFilteredTool
                # So we add in reverse order:

                # Step 1: Add ListFilteredTool FIRST (will execute LAST) if ISV validator is present
                env = (os.getenv("MCP_COMPOSER_ENV") or "").strip().lower()
                if env != "local" and self._isv_validator is not None:
                    from mcp_composer.middleware.tool.tool_filter import (
                        ListFilteredTool,
                    )

                    filter_mw = ListFilteredTool(
                        self, isv_validator=self._isv_validator
                    )
                    external_mcp.add_middleware(filter_mw)
                    logger.info(
                        "✓ Added ListFilteredTool to server '%s' (will execute LAST)",
                        server_id,
                    )

                # Step 2: Propagate composer middleware (from solis_composer.py setup_middleware)
                # FastMCP stores middleware directly in self.middleware attribute
                composer_middleware = getattr(self, "middleware", [])

                if composer_middleware:
                    from mcp_composer.middleware.tool.tool_filter import (
                        ListFilteredTool,
                    )

                    logger.info(
                        "Propagating %d composer middleware to server '%s'",
                        len(composer_middleware),
                        server_id,
                    )
                    for mw in composer_middleware:
                        # Skip ListFilteredTool - already added above with server-specific config
                        # Skip DereferenceRefsMiddleware - it's FastMCP's internal middleware
                        if (
                            not isinstance(mw, ListFilteredTool)
                            and type(mw).__name__ != "DereferenceRefsMiddleware"
                        ):
                            external_mcp.add_middleware(mw)
                            logger.debug(
                                "  ✓ Propagated %s to server '%s'",
                                type(mw).__name__,
                                server_id,
                            )

                # Step 3: Add ToolPrefixMiddleware LAST (will execute FIRST)
                from mcp_composer.middleware.tool.tool_prefix import (
                    ToolPrefixMiddleware,
                )

                prefix_mw = ToolPrefixMiddleware(server_id)
                external_mcp.add_middleware(prefix_mw)
                logger.info(
                    "✓ Added ToolPrefixMiddleware to server '%s' (will execute FIRST)",
                    server_id,
                )

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

    async def register_mcp_server(self, config: dict[str, Any]) -> str:
        """Register a single server."""
        logger.info("Registering single server: %s", config)
        return await self._server_manager.register_server(
            config=config, mcp_composer=self
        )

    async def update_mcp_server_config(
        self, server_id: str, new_config: dict[str, Any]
    ) -> str:
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
        # Remove from HTTP mounted servers tracking
        if server_id in self._http_mounted_servers:
            del self._http_mounted_servers[server_id]
        logger.info("Server %s unmounted", server_id)
        return f"Server '{server_id}' unmounted successfully."

    async def member_health(self) -> list[dict[str, Any]]:
        """Get status for all member servers."""
        return await self._server_manager.member_health(self._server_manager.members())

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

    async def add_tools_from_curl(self, tool_config: dict[str, Any]) -> str:
        """Create a tool from a curl command."""
        fn = await tool_from_curl(tool_config)
        self.add_tool(Tool.from_function(fn))
        return "Successfully added tools"

    async def add_tools_from_python(self, tool_config: dict[str, Any]) -> str:
        """Create a tool from a python script."""
        fn = await tool_from_script(tool_config)
        self.add_tool(Tool.from_function(fn))
        return "Successfully added tools"

    async def add_tools_from_openapi(
        self,
        openapi_spec: dict[str, Any],
        auth_config: dict[str, Any] | None = None,
    ) -> str:
        """Create a tool from OpenAPI Specification"""
        server_name, client = await tool_from_open_api(openapi_spec, auth_config)
        self.mount(FastMCP.from_openapi(openapi_spec, client), server_name)
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

    def add_prompts(self, prompt_config: dict | list[dict]) -> list[str]:
        """
        Add one or more prompts based on the provided configuration.
        Returns a list of registered prompt names.
        """
        return self._prompt_manager.add_prompts(prompt_config)

    async def get_all_prompts(self) -> list[str]:
        """Get all registered prompts mapped to their textual form from composer and mounted servers."""
        prompts_dict = await self._prompt_manager.get_prompts()
        return [str(prompt) for prompt in prompts_dict.values()]

    async def list_prompts(self, run_middleware: bool = True):  # type: ignore[override]
        """List all prompts from composer and mounted servers."""
        # Get prompts from prompt manager which includes database-loaded prompts
        return await self._prompt_manager.list_prompts()

    async def list_prompts_per_server(self, server_id: str) -> list[dict[str, Any]]:
        """List all prompts from a specific server."""
        return await self._prompt_manager.list_prompts_per_server(server_id)

    async def filter_prompts(
        self, filter_criteria: dict[str, Any]
    ) -> list[dict[str, Any]]:
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

    def delete_prompts(self, prompt_names: str | list[str]) -> dict:
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

    async def create_resource_template(self, resource_config: dict[str, Any]) -> str:
        """Add a resource template to the composer."""
        return await self._resource_manager.create_resource_template(resource_config)

    async def create_resource(self, resource_config: dict[str, Any]) -> str:
        """Create a resource in the composer."""
        return await self._resource_manager.create_resource(resource_config)

    async def list_resource_templates(  # type: ignore[override]
        self, run_middleware: bool = True
    ) -> list[ResourceTemplate]:
        """List all available resource templates from composer and mounted servers."""
        # Get templates from resource manager
        templates = await self._resource_manager.list_resource_templates()

        # Filter out any dicts that might have been added incorrectly
        # FastMCP expects ResourceTemplate objects, not dicts
        valid_templates = []
        for template in templates:
            if isinstance(template, dict):
                logger.warning(
                    "Found dict in templates list (expected ResourceTemplate object): %s. Skipping.",
                    template.get("name", "unknown"),
                )
                continue
            valid_templates.append(template)

        return valid_templates

    async def list_resources(  # type: ignore[override]
        self, run_middleware: bool = True
    ) -> list[Resource]:
        """List all available resources from composer and mounted servers."""
        # Get resources from resource manager
        resources = await self._resource_manager.list_resources()

        # Filter out any dicts that might have been added incorrectly
        # FastMCP expects Resource objects, not dicts
        valid_resources = []
        for resource in resources:
            if isinstance(resource, dict):
                logger.warning(
                    "Found dict in resources list (expected Resource object): %s. Skipping.",
                    resource.get("name", "unknown"),
                )
                continue
            valid_resources.append(resource)

        return valid_resources

    async def list_resources_per_server(self, server_id: str) -> list[dict[str, Any]]:
        """List all resources from a specific server."""
        return await self._resource_manager.list_resources_per_server(server_id)

    async def filter_resources(
        self, filter_criteria: dict[str, Any]
    ) -> list[dict[str, Any]]:
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

    async def disable_composer_tool(self, tools: list[str] | None = None) -> str:
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
        super_run_stdio = super().run_stdio_async
        await super_run_stdio(show_banner=False)

    async def get_available_tools(
        self, server_id: str | None = None
    ) -> dict[str, list[dict[str, Any]]]:
        """Get all available tools from the composer."""
        tools = await self._tool_manager.get_all_tools(server_id)
        result: list[dict[str, Any]] = []
        for index, tool in enumerate(tools):
            if hasattr(tool, "model_dump"):
                try:
                    item = tool.model_dump(mode="json")  # type: ignore[call-arg]
                except Exception:
                    item = dict(getattr(tool, "__dict__", {}))
            elif hasattr(tool, "dict"):
                item = tool.dict()  # type: ignore[call-arg]
            elif isinstance(tool, dict):
                item = tool
            else:
                item = {
                    "name": getattr(tool, "name", str(tool)),
                    "description": getattr(tool, "description", None),
                }
            item = _json_safe_tool_payload(item)
            result.append(item)
        return {"tools": result}

    def get_multi_server_http_app(self):
        """
        Create a Starlette app with individual routes for each mounted server plus composer root.

        Note: All middleware (including ToolPrefixMiddleware, ListFilteredTool, and composer middleware
        from solis_composer.py) are added at mount time in _mount_member_server() to ensure correct
        execution order.
        """
        from starlette.applications import Starlette
        from starlette.routing import Mount
        from contextlib import asynccontextmanager

        logger.info(
            "Creating multi-server HTTP app with %d mounted servers",
            len(self._http_mounted_servers),
        )

        # Get the composer's own HTTP app (for root /mcp endpoint)
        composer_app = super().http_app()

        # Collect all member server apps
        server_apps = {}
        for server_id, server in self._http_mounted_servers.items():
            server_apps[server_id] = server.http_app()

        # Create a combined lifespan that manages composer + all server lifespans
        @asynccontextmanager
        async def combined_lifespan(app):
            # Start composer's lifespan first
            lifespan_contexts = []

            # Add composer's lifespan
            if hasattr(composer_app, "router") and hasattr(
                composer_app.router, "lifespan_context"
            ):
                composer_ctx = composer_app.router.lifespan_context(composer_app)
                lifespan_contexts.append(composer_ctx)
                await composer_ctx.__aenter__()

            # Add all member server lifespans
            for server_id, server_app in server_apps.items():
                if hasattr(server_app, "router") and hasattr(
                    server_app.router, "lifespan_context"
                ):
                    ctx = server_app.router.lifespan_context(server_app)
                    lifespan_contexts.append(ctx)
                    await ctx.__aenter__()

            try:
                yield
            finally:
                # Clean up all lifespans in reverse order
                for ctx in reversed(lifespan_contexts):
                    await ctx.__aexit__(None, None, None)

        # Create routes - member servers first, then composer at root
        routes = []

        # Add member server routes
        for server_id, server_app in server_apps.items():
            routes.append(Mount(f"/{server_id}", app=server_app))

        # Add composer's own app at root (must be last to not override member routes)
        routes.append(Mount("/", app=composer_app))

        # Create the main Starlette app with combined lifespan
        app = Starlette(routes=routes, lifespan=combined_lifespan)
        return app

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
        Supports multi-server routing when servers are mounted.
        """
        if show_banner:
            print_mcp_composer_banner(
                server_name=self.name or "mcp-composer",
                transport=transport,
                host=host,
                port=port,
                path=path,
            )

        # Check if we should use multi-server routing (only if enabled)
        if self._enable_multi_server_routing and self._http_mounted_servers:
            import uvicorn

            logger.info("Starting MCP Composer with multi-server HTTP routing")
            app = self.get_multi_server_http_app()

            # Use provided config or defaults
            config_dict = uvicorn_config or {}
            config_dict.update(
                {
                    "app": app,
                    "host": host or "0.0.0.0",
                    "port": port or 8000,
                    "log_level": log_level or "info",
                }
            )

            config = uvicorn.Config(**config_dict)
            server = uvicorn.Server(config)
            await server.serve()
        else:
            # Fall back to default single-server mode
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
