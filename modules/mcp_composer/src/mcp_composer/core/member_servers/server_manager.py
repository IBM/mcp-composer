"""
ServerManager module handles the lifecycle of MCP member servers,
including mounting, registration, persistence, tool management, and health checks.
"""

from __future__ import annotations

import builtins
from typing import Any
from collections.abc import Callable

from fastmcp.exceptions import NotFoundError, ToolError


from mcp_composer.core.member_servers.builder import MCPServerBuilder
from mcp_composer.core.utils import LoggerFactory, get_member_health
from mcp_composer.core.member_servers.member_server import HealthStatus, MemberMCPServer
from mcp_composer.core.utils.exceptions import (
    MemberServerError,
    ToolDuplicateError,
    ToolDisableError,
    ServerConfigurationError,
    ServerMountError,
    ServerBuildError,
    ServerNotFoundError,
    ServerError,
)
from mcp_composer.core.utils.security import sanitize_config
from mcp_composer.core.utils.utils import get_endpoint_from_config
from mcp_composer.store.database import DatabaseInterface
from mcp_composer.core.utils.tools import check_duplicate_tool
from mcp_composer.core.utils.validator import ServerConfigValidator, ValidationError

logger = LoggerFactory.get_logger()

# Server status constants
SERVER_STATUS_DEACTIVATED = "deactivated"
SERVER_STATUS_ACTIVE = "active"
SERVER_STATUS_UNKNOWN = "unknown"


class ServerManager:
    """
    Manages registration and lifecycle of mounted MCP servers,
    with optional serialization for monitoring, or persistence.
    """

    _db_name: str = "mcp_servers"

    def __init__(
        self,
        serializer: Callable[[str, MemberMCPServer], Any] | None = None,
        database: DatabaseInterface | None = None,
        config_manager=None,
        composer=None,
    ) -> None:
        self._member_servers: dict[str, MemberMCPServer] = {}
        # Fix here: explicitly declare non-optional type
        self._serializer: Callable[[str, MemberMCPServer], Any] = (
            serializer or self.default_serializer
        )
        self._database = database
        self._config_manager = config_manager
        self._composer = composer

    @staticmethod
    def default_serializer(
        server_id: str, member: MemberMCPServer
    ) -> dict[str, Any]:  # pylint: disable=W0613
        """serializer convert to dict"""
        return member.to_dict()

    async def _mount_and_register_server(
        self,
        config: dict[str, object],
        mcp_composer,
        save_to_db: bool = True,
    ) -> str:
        server_id = config.get("id")
        if not isinstance(server_id, str) or not server_id:
            raise ServerConfigurationError(
                "Server configuration must include a valid 'id' field",
                context={"config": config}
            )

        config["_id"] = server_id

        try:
            builder = MCPServerBuilder(config)
            sub_mcp = await builder.build()

            # Handle both cases: mcp_composer as object or as callback function
            if hasattr(mcp_composer, "mount"):
                mcp_composer.mount(sub_mcp, server_id)
                # Store for HTTP routing if enabled and composer has the tracking dict
                if (
                    hasattr(mcp_composer, "_enable_multi_server_routing")
                    and mcp_composer._enable_multi_server_routing
                    and hasattr(mcp_composer, "_http_mounted_servers")
                ):
                    mcp_composer._http_mounted_servers[server_id] = sub_mcp
            else:
                mcp_composer(sub_mcp, server_id)
            # get_tools() exists in FastMCP 3.0 and returns a list (per upgrade guide)
            # Type checker doesn't recognize it, but it exists at runtime
            tools = (
                await sub_mcp.list_tools()
            )  # pyright: ignore[reportAttributeAccessIssue]
            missing_description_tools = [
                tool.name if hasattr(tool, "name") else str(tool)
                for tool in tools
                if not tool.description or not tool.description.strip()
            ]

            if missing_description_tools:
                logger.warning(
                    "MCP server '%s' registration failed: The following tools are missing descriptions: %s",
                    server_id,
                    ", ".join(missing_description_tools),
                )
                mcp_composer._tool_manager.unmount(server_id)
                raise ServerConfigurationError(
                    f"Tools missing descriptions for server '{server_id}'",
                    context={
                        "server_id": server_id,
                        "missing_tools": missing_description_tools
                    }
                )

            member = MemberMCPServer(
                id=server_id,
                endpoint=get_endpoint_from_config(config),
                type=str(config.get("type", "")),  # type: ignore[arg-type]
                config=config,
                label=config.get("label"),  # type: ignore[arg-type]
                tags=config.get("tags", []),  # type: ignore[arg-type]
                tool_count=None,
            )
            member.set_server(sub_mcp)

            if save_to_db:
                self.add_server_db(config)

            self.add_member(server_id, member)

            logger.info(
                "MCP server '%s' mounted and registered successfully.", server_id
            )
            return f"Server '{server_id}' mounted successfully."

        except ServerConfigurationError:
            # Re-raise configuration errors as-is to preserve original context
            raise
        except (ValueError, TypeError, KeyError) as e:
            # Configuration parsing/validation errors
            logger.error(
                "Invalid configuration for server '%s': %s",
                server_id,
                e,
                extra={"config": sanitize_config(config)}
            )
            raise ServerConfigurationError(
                f"Invalid configuration for server '{server_id}'",
                context={"server_id": server_id, "config": sanitize_config(config), "error": str(e)}
            ) from e
        except (ConnectionError, TimeoutError) as e:
            # Network/connection errors during mount
            logger.error(
                "Connection failed while mounting server '%s': %s",
                server_id,
                e,
                extra={"config": sanitize_config(config)}
            )
            raise ServerMountError(
                f"Failed to connect to server '{server_id}'",
                context={"server_id": server_id, "endpoint": config.get("endpoint"), "error": str(e)}
            ) from e
        except Exception as e:
            # Unexpected errors during build/mount process
            logger.exception(
                "Unexpected error mounting MCP server '%s'",
                server_id,
                extra={"config": sanitize_config(config)}
            )
            raise ServerBuildError(
                f"Failed to build/mount server '{server_id}'",
                context={"server_id": server_id, "error": str(e)}
            ) from e

    async def register_server(
        self,
        config: dict[str, object],
        mcp_composer,
    ) -> str:
        """Register a new member server."""
        try:
            ServerConfigValidator(config).validate()

            server_id = config.get("id", "")
            if not isinstance(server_id, str):
                server_id = ""
            if self.has_member_server(server_id):
                logger.warning("Server '%s' already mounted.", server_id)
                return f"Server '{server_id}' already mounted."

            return await self._mount_and_register_server(config, mcp_composer)

        except (ServerConfigurationError, ServerMountError, ServerBuildError):
            # Re-raise specific server errors as-is to preserve original context
            # These exceptions already have proper context from _mount_and_register_server
            raise
        except ValidationError as e:
            # Schema validation errors from ServerConfigValidator
            logger.error(
                "Server configuration validation failed: %s",
                e,
                extra={"config": sanitize_config(config)}
            )
            raise ServerConfigurationError(
                "Invalid server configuration",
                context={"config": sanitize_config(config), "validation_error": str(e)}
            ) from e
        except Exception as e:
            # Unexpected errors not caught by more specific handlers
            logger.exception(
                "Unexpected error registering server: %s",
                e,
                extra={"config": sanitize_config(config)}
            )
            raise ServerError(
                "Failed to register server",
                context={"config": sanitize_config(config), "error": str(e)}
            ) from e

    async def update_server_config(
        self,
        server_id: str,
        new_config: dict[str, object],
        mcp_composer,
    ) -> str:
        """Update an existing server's configuration."""
        try:
            logger.info(
                "Updating server '%s' with new config: %s", server_id, new_config
            )

            if new_config.get("id") and new_config["id"] != server_id:
                raise ServerConfigurationError(
                    "Server ID in config does not match the target server ID",
                    context={"server_id": server_id, "config_id": new_config.get("id")}
                )
            new_config["id"] = server_id

            ServerConfigValidator(new_config).validate()

            if not self.has_member_server(server_id):
                raise ServerNotFoundError(
                    f"Server '{server_id}' not found",
                    context={"server_id": server_id}
                )

            mcp_composer._tool_manager.unmount(server_id)
            self.remove_member(server_id)

            if not self._database:
                raise ServerConfigurationError(
                    "Database not available for server update",
                    context={"server_id": server_id}
                )

            existing_config = self._database.get_document(server_id)
            if self._config_manager is not None and existing_config:
                version_id = self._config_manager.save_version(
                    server_id, existing_config
                )
                new_config["version_id"] = version_id
                logger.info(
                    "Saved config version %s for server '%s'", version_id, server_id
                )

            self.update_server_db(new_config)

            return await self._mount_and_register_server(
                new_config, mcp_composer, save_to_db=False
            )

        except (ServerConfigurationError, ServerNotFoundError, ServerMountError, ServerBuildError):
            # Re-raise specific server errors as-is
            raise
        except ValidationError as e:
            logger.error("Server configuration validation failed for '%s': %s", server_id, e)
            raise ServerConfigurationError(
                f"Invalid configuration for server '{server_id}'",
                context={"server_id": server_id, "new_config": new_config, "validation_error": str(e)}
            ) from e
        except Exception as e:
            logger.exception(
                "Unexpected error while updating server '%s'",
                server_id
            )
            raise ServerError(
                f"Failed to update server '{server_id}'",
                context={"server_id": server_id, "error": str(e)}
            ) from e

    async def activate_server(
        self,
        server_id: str,
        mcp_composer,
    ) -> str:
        """Activate a previously deactivated server."""
        try:
            config = self.prepare_activation(server_id)

            if self.has_member_server(server_id):
                logger.warning("Server '%s' already mounted.", server_id)
                return f"Server '{server_id}' already mounted."

            await self._mount_and_register_server(
                config, mcp_composer, save_to_db=False
            )
            return f"Server '{server_id}' activated"

        except (ServerConfigurationError, ServerNotFoundError, ServerMountError, ServerBuildError):
            # Re-raise specific server errors as-is
            raise
        except (NotFoundError, ToolError) as e:
            logger.error("Failed to activate server '%s': %s", server_id, e)
            raise ServerError(
                f"Failed to activate server '{server_id}'",
                context={"server_id": server_id, "error": str(e)}
            ) from e
        except Exception as e:
            logger.exception("Unexpected error activating server '%s'", server_id)
            raise ServerError(
                f"Failed to activate server '{server_id}'",
                context={"server_id": server_id, "error": str(e)}
            ) from e

    def deactivate_server(self, server_id: str, mcp_composer) -> str:
        """Deactivate a mounted server (idempotent operation).

        This operation is idempotent - calling it multiple times on the same
        server will succeed without error, avoiding race conditions in concurrent
        scenarios.

        Args:
            server_id: ID of server to deactivate
            mcp_composer: Composer instance for tool unmounting

        Returns:
            Success message indicating server was deactivated or already deactivated

        Raises:
            ServerNotFoundError: If server doesn't exist
            ServerError: If deactivation fails
        """
        try:
            # Check if already deactivated (idempotent behavior)
            status = self.get_server_status(server_id)

            if status == SERVER_STATUS_UNKNOWN:
                raise ServerNotFoundError(f"Server '{server_id}' not found", context={"server_id": server_id})

            # Idempotent: already deactivated is success, not error
            if status == SERVER_STATUS_DEACTIVATED:
                logger.info("Server '%s' is already deactivated", server_id)
                return f"Server '{server_id}' is already deactivated"

            # Proceed with deactivation
            self.check_server_exist(server_id)
            self.mark_deactivated(server_id)
            self.remove_member(server_id)
            mcp_composer._tool_manager.unmount(server_id)

            return f"Server '{server_id}' deactivated successfully"

        except ServerNotFoundError:
            # Re-raise server not found errors as-is
            raise
        except NotFoundError as e:
            logger.warning("Deactivation failed for '%s': %s", server_id, e)
            raise ServerNotFoundError(f"Server '{server_id}' not found", context={"server_id": server_id}) from e
        except ToolError as e:
            logger.error("Tool error during deactivation of '%s': %s", server_id, e)
            raise ServerError(
                f"Failed to deactivate server '{server_id}': tool unmount failed",
                context={"server_id": server_id, "error": str(e)},
            ) from e
        except Exception as e:
            logger.exception("Unexpected error deactivating server '%s'", server_id)
            raise ServerError(
                f"Failed to deactivate server '{server_id}'", context={"server_id": server_id, "error": str(e)}
            ) from e

    async def member_health(
        self, config: list[MemberMCPServer]
    ) -> list[dict[str, object]]:
        """Return member server's health status"""
        server_config = config if config else self.members()
        health_status = await get_member_health(server_config)
        return health_status

    def list_servers(self) -> list[dict]:
        """
        List status of active member servers only (excludes deactivated servers).
        """
        logger.info("Listing member servers")
        configs = self.load_all_servers_db()

        result = []
        for cfg in configs:  # type: ignore[attr-defined]
            server_id = str(cfg["id"])
            status = self.get_server_status(server_id)

            # Skip deactivated servers
            if status == SERVER_STATUS_DEACTIVATED:
                continue

            # Initialize defaults
            server_name = "N/A"
            endpoint = "N/A"

            # Get server info only if mounted (single check optimization)
            if self.has_member_server(server_id):
                # Get server name with error handling
                try:
                    server_name = self.get(server_id).get_server().name
                except MemberServerError:
                    logger.warning("Server '%s' is unhealthy", server_id)
                    server_name = "UNHEALTHY"
                except Exception as e:
                    logger.error("Error getting server name for '%s': %s", server_id, e)
                    server_name = "ERROR"

                # Get endpoint with error handling
                try:
                    endpoint = get_endpoint_from_config(cfg)
                except Exception as e:
                    logger.error("Error getting endpoint for '%s': %s", server_id, e)
                    endpoint = "ERROR"

            result.append(
                {
                    "id": cfg["id"],
                    "type": cfg["type"],
                    "server_name": server_name,
                    "endpoint": endpoint,
                    "status": status,
                }
            )

        return result

    def check_server_exist(self, server_id) -> None:
        """Check member server is mounted or not"""
        if not self.has_member_server(server_id):
            raise NotFoundError(f"Server '{server_id}' not mounted.")

    def has_member_server(self, key: str) -> bool:
        """Check if a member server exists."""
        return key in self._member_servers

    def add_member(self, server_id: str, server: MemberMCPServer) -> None:
        """Add member server in-memory"""
        if server_id in self._member_servers:
            logger.warning("Overwriting existing MCP server: %s", server_id)
        self._member_servers[server_id] = server
        logger.info("Mounted MCP server:%s", server_id)

    def update_server_db(self, config: dict[str, object]) -> None:
        """Update the server config in the database."""
        server_id = config.get("id")
        if not server_id:
            raise ValueError("Config must include 'id' to update.")
        if self._database:
            self._database.update_server_config(config)

    def remove_member(self, server_id: str) -> None:
        """Remove a member server"""
        if server_id not in self._member_servers:
            logger.warning("MCP server '%s' not found.", server_id)
            return
        del self._member_servers[server_id]
        logger.info("Unmounted MCP server: %s", server_id)

    def get(self, server_id: str) -> MemberMCPServer:
        """Return member server details"""
        if server_id not in self._member_servers:
            raise NotFoundError(f"MCP Server '{server_id}' not mounted.")
        if self._member_servers[server_id].health_status == HealthStatus.unhealthy:
            raise MemberServerError(f"MCP Server '{server_id}' is down.")
        return self._member_servers[server_id]

    def list(self) -> list[MemberMCPServer]:  # type: ignore[valid-type]
        """list all member server"""
        return [v for v in self._member_servers.values()]

    def members(self) -> list[MemberMCPServer]:  # type: ignore[valid-type]
        """Backward-compatible alias for listing all member servers."""
        return self.list()

    def list_serialized(self) -> dict[str, Any]:
        """list all member server"""
        return {
            server_id: self._serializer(server_id, member)
            for server_id, member in self._member_servers.items()
        }

    def add_server_db(self, config: dict[str, object]) -> None:
        """Add member server to database"""
        if self._database:
            self._database.add_server(config)

    def remove_mcp_server(self, server_id: str) -> None:
        """Remove member server from database"""
        if self._database:
            self._database.remove_server(server_id)

    def load_all_servers_db(self) -> list[dict[str, object]]:  # type: ignore[valid-type]
        """fetch all member server from database"""
        if self._database is None:
            return []
        return self._database.load_all_servers()

    def disable_tools(self, tools: list[str], server_id: str) -> None:  # type: ignore[valid-type]
        """Disable tools of member server"""
        try:
            tools = builtins.list(set(tools))
            member = self.get(server_id)
            existing_tools = member.disabled_tools
            tools_description = member.tools_description
            duplicate_tool = check_duplicate_tool(existing_tools, tools)

            if duplicate_tool:
                raise ToolDuplicateError(f"Tool {duplicate_tool} is already disabled")

            existing_tools.extend(tools)
            logger.info(
                "Added new disabled tool list %s for server %s.", tools, server_id
            )

            # Remove tool descriptions if they exist
            if existing_tools and tools_description:
                for tool in existing_tools:
                    tools_description.pop(tool, None)
        except Exception as e:
            raise ToolDisableError(f"Failed to disable tool: {e}") from e

        if self._database:
            self._database.disable_tools(tools, server_id)

    def enable_tools(self, tools: list[str], server_id: str) -> None:  # type: ignore[valid-type]
        """Enable tools of member server and add to database"""
        try:
            tools = builtins.list(set(tools))
            member = self.get(server_id)
            disabled_tools = member.disabled_tools
            tools_to_remove: list[str] = [
                str(tool) for tool in tools if tool in disabled_tools
            ]
            if not tools_to_remove:
                raise ValueError("No tools disabled")

            # Remove matching tools from disabled_tools
            member.disabled_tools = [
                tool for tool in disabled_tools if tool not in tools_to_remove
            ]
            if self._database:
                self._database.enable_tools(member.disabled_tools, server_id)

        except Exception as e:
            raise ToolDisableError(f"Failed to disable tool: {e}") from e

    def update_tool_description(
        self, tool: str, description: str, server_id: str
    ) -> None:
        """Update member server's tool description"""
        member = self.get(server_id)
        # if tools description already found, update it
        # if not add the tools description
        member.tools_description.update({tool: description})
        logger.info(
            "Tool description:%s  is added for server:%s ",
            member.tools_description,
            server_id,
        )

        if self._database:
            self._database.update_tool_description(tool, description, server_id)

    def disable_prompts(self, prompts: list[str], server_id: str) -> None:  # type: ignore[valid-type]
        """Disable prompts of member server"""
        try:
            prompts = builtins.list(set(prompts))
            member = self.get(server_id)
            existing_prompts = member.disabled_prompts
            prompts_description = member.prompts_description
            duplicate_prompt = check_duplicate_tool(existing_prompts, prompts)

            if duplicate_prompt:
                raise ToolDuplicateError(
                    f"Prompt {duplicate_prompt} is already disabled"
                )

            existing_prompts.extend(prompts)
            logger.info(
                "Added new disabled prompt list %s for server %s.", prompts, server_id
            )

            # Remove prompt descriptions if they exist
            if existing_prompts and prompts_description:
                for prompt in existing_prompts:
                    prompts_description.pop(prompt, None)
        except Exception as e:
            raise ToolDisableError(f"Failed to disable prompt: {e}") from e

        if self._database:
            self._database.disable_prompts(prompts, server_id)

    def enable_prompts(self, prompts: list[str], server_id: str) -> None:  # type: ignore[valid-type]
        """Enable prompts of member server and add to database"""
        try:
            prompts = builtins.list(set(prompts))
            member = self.get(server_id)
            disabled_prompts = member.disabled_prompts
            prompts_to_remove: list[str] = [
                str(prompt) for prompt in prompts if prompt in disabled_prompts
            ]
            if not prompts_to_remove:
                raise ValueError("No prompts disabled")

            # Remove matching prompts from disabled_prompts
            member.disabled_prompts = [
                prompt for prompt in disabled_prompts if prompt not in prompts_to_remove
            ]
            if self._database:
                self._database.enable_prompts(member.disabled_prompts, server_id)

        except Exception as e:
            raise ToolDisableError(f"Failed to enable prompt: {e}") from e

    def disable_resources(self, resources: list[str], server_id: str) -> None:  # type: ignore[valid-type]
        """Disable resources of member server"""
        try:
            resources = builtins.list(set(resources))
            member = self.get(server_id)
            existing_resources = member.disabled_resources
            resources_description = member.resources_description
            duplicate_resource = check_duplicate_tool(existing_resources, resources)

            if duplicate_resource:
                raise ToolDuplicateError(
                    f"Resource {duplicate_resource} is already disabled"
                )

            existing_resources.extend(resources)
            logger.info(
                "Added new disabled resource list %s for server %s.",
                resources,
                server_id,
            )

            # Remove resource descriptions if they exist
            if existing_resources and resources_description:
                for resource in existing_resources:
                    resources_description.pop(resource, None)
        except Exception as e:
            raise ToolDisableError(f"Failed to disable resource: {e}") from e

        if self._database:
            self._database.disable_resources(resources, server_id)

    def enable_resources(self, resources: list[str], server_id: str) -> None:  # type: ignore[valid-type]
        """Enable resources of member server and add to database"""
        try:
            resources = builtins.list(set(resources))
            member = self.get(server_id)
            disabled_resources = member.disabled_resources
            resources_to_remove: list[str] = [
                str(resource)
                for resource in resources
                if resource in disabled_resources
            ]
            if not resources_to_remove:
                raise ValueError("No resources disabled")

            # Remove matching resources from disabled_resources
            member.disabled_resources = [
                resource
                for resource in disabled_resources
                if resource not in resources_to_remove
            ]
            if self._database:
                self._database.enable_resources(member.disabled_resources, server_id)

        except Exception as e:
            raise ToolDisableError(f"Failed to enable resource: {e}") from e

    def get_document(self, server_id: str) -> dict[str, object]:
        """Get a member server details from database"""
        if self._database is None:
            return {}
        return self._database.get_document(server_id)

    def get_member(self, server_id: str) -> MemberMCPServer | None:
        """Get a member server details from in-memory"""
        return self._member_servers.get(server_id)

    def prepare_activation(self, server_id: str) -> dict[str, object]:
        """
        Validates and returns updated config for reactivating a server.
        Raises error if not found or not deactivated.
        """
        all_configs = self.load_all_servers_db()
        config = next((cfg for cfg in all_configs if cfg["id"] == server_id), None)  # type: ignore[attr-defined]

        if not config:
            raise NotFoundError(f"No configuration found for server '{server_id}'.")

        if config.get("status") != SERVER_STATUS_DEACTIVATED:
            raise ToolError(f"Server '{server_id}' is not deactivated.")

        config["status"] = SERVER_STATUS_ACTIVE
        self.add_server_db(config)
        return config

    def prepare_deactivation(self, server_id: str) -> None:
        """
        Validates and updates DB to mark the server as deactivated.

        Note: This method is deprecated in favor of the idempotent
        deactivate_server() method. It's kept for backward compatibility
        but should not be used directly.

        Raises:
            ServerNotFoundError: If server doesn't exist
            ServerError: If server is already deactivated
        """
        status = self.get_server_status(server_id)
        if status == SERVER_STATUS_UNKNOWN:
            raise ServerNotFoundError(
                f"Server '{server_id}' not found in database",
                context={"server_id": server_id}
            )

        if status == SERVER_STATUS_DEACTIVATED:
            raise ServerError(
                f"Server '{server_id}' is already deactivated",
                context={"server_id": server_id, "status": status}
            )

        self.check_server_exist(server_id)

        self.mark_deactivated(server_id)
        self.remove_member(server_id)

    def mark_deactivated(self, server_id: str) -> None:
        """Deactivate the member server"""
        if self._database:
            return self._database.mark_deactivated(server_id)
        return None

    def get_server_status(self, server_id: str) -> str:
        """Activate the member server"""
        if self._database:
            return self._database.get_server_status(server_id)

        return "unknown"
