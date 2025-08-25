"""
ServerManager module handles the lifecycle of MCP member servers,
including mounting, registration, persistence, tool management, and health checks.
"""

from typing import Dict, List, Any, Optional
from collections.abc import Callable

from fastmcp.settings import DuplicateBehavior
from fastmcp.exceptions import NotFoundError, ToolError

from mcp_composer.core.member_servers.builder import MCPServerBuilder
from mcp_composer.core.utils import LoggerFactory, get_member_health
from mcp_composer.core.member_servers.member_server import HealthStatus, MemberMCPServer
from mcp_composer.core.utils.exceptions import (
    MemberServerError,
    ToolDuplicateError,
    ToolDisableError,
)
from mcp_composer.store.database import DatabaseInterface
from mcp_composer.core.utils.tools import check_duplicate_tool
from mcp_composer.core.utils.validator import ServerConfigValidator, ValidationError

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
        config_manager=None,
    ):
        self._member_servers: dict[str, MemberMCPServer] = {}
        # Fix here: explicitly declare non-optional type
        self._serializer: Callable[[str, MemberMCPServer], Any] = (
            serializer or self.default_serializer
        )
        self._database = database
        self._config_manager = config_manager

        if duplicate_behavior is None:
            duplicate_behavior = "warn"

        if duplicate_behavior not in DuplicateBehavior.__args__:
            raise ValueError(
                f"Invalid duplicate_behavior: {duplicate_behavior}. "
                f"Must be one of: {', '.join(DuplicateBehavior.__args__)}"
            )

        self.duplicate_behavior = duplicate_behavior

    @staticmethod
    def default_serializer(
        server_id: str, member: MemberMCPServer
    ):  # pylint: disable=W0613
        """serializer convert to dict"""
        return member.to_dict()

    async def _mount_and_register_server(
        self,
        config: dict,
        mount_callback: Callable[[Any, str], None],
        save_to_db: bool = True,
    ) -> str:
        server_id = config["id"]
        config["_id"] = server_id

        builder = MCPServerBuilder(config)
        sub_mcp = await builder.build()

        mount_callback(sub_mcp, server_id)

        member = MemberMCPServer(
            id=server_id,
            type=config["type"],
            config=config,
            label=config.get("label"),
            tags=config.get("tags", []),
            tool_count=None,
        )
        member.set_server(sub_mcp)

        if save_to_db:
            self.add_server_db(config)

        self.add_member(server_id, member)

        return f"Server '{server_id}' mounted successfully."

    async def register_server(
        self,
        config: dict,
        mount_callback: Callable[[Any, str], None],
    ) -> str:
        """Register a new member server."""
        try:
            ServerConfigValidator(config).validate()

            server_id = config.get("id", "")
            if self.has_member_server(server_id):
                logger.warning("Server '%s' already mounted.", server_id)
                return f"Server '{server_id}' already mounted."

            return await self._mount_and_register_server(config, mount_callback)

        except Exception as e:
            logger.exception("Failed to register server: %s", e)
            raise ToolError(f"Failed to register server: {e}") from e

    async def update_server_config(
        self,
        server_id: str,
        new_config: dict,
        unmount_callback: Callable[[str], Any],
        mount_callback: Callable[[Any, str], None],
    ) -> str:
        """Update an existing server's configuration."""
        try:
            logger.info(
                "Updating server '%s' with new config: %s", server_id, new_config
            )

            if new_config.get("id") and new_config["id"] != server_id:
                raise ValidationError(
                    "Server ID in config does not match the target server ID."
                )
            new_config["id"] = server_id

            ServerConfigValidator(new_config).validate()

            if not self.has_member_server(server_id):
                raise NotFoundError(f"Server '{server_id}' not found.")

            unmount_callback(server_id)
            self.remove_member(server_id)

            if not self._database:
                raise NotFoundError("Database not found.")

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
                new_config, mount_callback, save_to_db=False
            )

        except (ValidationError, NotFoundError) as err:
            logger.error("Error updating server '%s': %s", server_id, err)
            raise ToolError(f"Failed to update server '{server_id}': {err}") from err

        except Exception as e:
            logger.exception(
                "Unexpected error while updating server '%s': %s", server_id, e
            )
            raise ToolError(f"Failed to update server '{server_id}': {e}") from e

    async def activate_server(
        self,
        server_id: str,
        mount_callback: Callable[[Any, str], None],
    ) -> str:
        """Activate a previously deactivated server."""
        try:
            config = self.prepare_activation(server_id)

            if self.has_member_server(server_id):
                logger.warning("Server '%s' already mounted.", server_id)
                return f"Server '{server_id}' already mounted."

            await self._mount_and_register_server(
                config, mount_callback, save_to_db=False
            )
            return f"Server '{server_id}' activated"

        except Exception as e:
            logger.exception("Failed to activate server '%s': %s", server_id, e)
            raise ToolError(f"Failed to activate server '{server_id}': {e}") from e

    def deactivate_server(
        self, server_id: str, unmount_callback: Callable[[str], None]
    ) -> str:
        """Deactivate a mounted server."""
        try:
            self.prepare_deactivation(server_id)
            unmount_callback(server_id)
            return f"Server '{server_id}' deactivated."
        except NotFoundError as e:
            logger.warning("Deactivation failed: %s", e)
            raise ToolError(str(e)) from e
        except Exception as e:
            logger.exception("Error deactivating server '%s': %s", server_id, e)
            raise ToolError(f"Failed to deactivate server '{server_id}': {e}") from e

    async def member_health(self, config: list[MemberMCPServer]) -> list[dict]:
        """Return member server's health status"""
        server_config = config if config else self.list()
        health_status = await get_member_health(server_config)
        return health_status

    def list_member_servers(self) -> list[dict]:
        """
        List status of all member servers (active or deactivated).
        """
        logger.info("Listing member servers")
        configs = self.load_all_servers_db()

        return [
            {
                "id": cfg["id"],
                "server_name": (
                    self.get(cfg["id"]).get_server().name
                    if self.has_member_server(cfg["id"])
                    else "N/A"
                ),
                "status": self.get_server_status(cfg["id"]),
            }
            for cfg in configs
        ]

    def check_server_exist(self, server_id) -> None:
        """Check member server is mounted or not"""
        if not self.has_member_server(server_id):
            raise NotFoundError(f"Server '{server_id}' not mounted.")

    def has_member_server(self, key: str) -> bool:
        """Check if a member server exists."""
        return key in self._member_servers

    def add_member(self, server_id: str, server: MemberMCPServer):
        """Add member server in-memory"""
        if server_id in self._member_servers:
            logger.warning("Overwriting existing MCP server: %s", server_id)
        self._member_servers[server_id] = server
        logger.info("Mounted MCP server:%s", server_id)

    def update_server_db(self, config: dict) -> None:
        """Update the server config in the database."""
        server_id = config.get("id")
        if not server_id:
            raise ValueError("Config must include 'id' to update.")
        if self._database:
            self._database.update_server_config(config)

    def remove_member(self, server_id: str):
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

    def list(self) -> list[MemberMCPServer]:
        """List all member server"""
        return list(self._member_servers.values())

    def list_serialized(self) -> Dict[str, Any]:
        """List all member server"""
        return {
            server_id: self._serializer(server_id, member)
            for server_id, member in self._member_servers.items()
        }

    def add_server_db(self, config: dict) -> None:
        """Add member server to database"""
        if self._database:
            self._database.add_server(config)

    def remove_mcp_server(self, server_id: str) -> None:
        """Remove member server from database"""
        if self._database:
            self._database.remove_server(server_id)

    def load_all_servers_db(self) -> List[dict]:
        """fetch all member server from database"""
        if self._database is None:
            return []
        return self._database.load_all_servers()

    def disable_tools(self, tools: List[str], server_id: str) -> None:
        """Disable tools of member server"""
        try:
            tools = list(set(tools))
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

    def enable_tools(self, tools: List[str], server_id: str) -> None:
        """Enable tools of member server and add to database"""
        try:
            tools = list(set(tools))
            member = self.get(server_id)
            disabled_tools = member.disabled_tools
            tools_to_remove = [tool for tool in tools if tool in disabled_tools]
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

    def disable_prompts(self, prompts: List[str], server_id: str) -> None:
        """Disable prompts of member server"""
        try:
            prompts = list(set(prompts))
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

    def enable_prompts(self, prompts: List[str], server_id: str) -> None:
        """Enable prompts of member server and add to database"""
        try:
            prompts = list(set(prompts))
            member = self.get(server_id)
            disabled_prompts = member.disabled_prompts
            prompts_to_remove = [
                prompt for prompt in prompts if prompt in disabled_prompts
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

    def disable_resources(self, resources: List[str], server_id: str) -> None:
        """Disable resources of member server"""
        try:
            resources = list(set(resources))
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

    def enable_resources(self, resources: List[str], server_id: str) -> None:
        """Enable resources of member server and add to database"""
        try:
            resources = list(set(resources))
            member = self.get(server_id)
            disabled_resources = member.disabled_resources
            resources_to_remove = [
                resource for resource in resources if resource in disabled_resources
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

    def get_document(self, server_id: str) -> Dict:
        """Get a member server details from database"""
        if self._database is None:
            return {}
        return self._database.get_document(server_id)

    def get_member(self, server_id: str) -> MemberMCPServer | None:
        """Get a member server details from in-memory"""
        return self._member_servers.get(server_id)

    def prepare_activation(self, server_id: str) -> dict:
        """
        Validates and returns updated config for reactivating a server.
        Raises error if not found or not deactivated.
        """
        all_configs = self.load_all_servers_db()
        config = next((cfg for cfg in all_configs if cfg["id"] == server_id), None)

        if not config:
            raise NotFoundError(f"No configuration found for server '{server_id}'.")

        if config.get("status") != "deactivated":
            raise ToolError(f"Server '{server_id}' is not deactivated.")

        config["status"] = "active"
        self.add_server_db(config)
        return config

    def prepare_deactivation(self, server_id: str) -> None:
        """
        Validates and updates DB to mark the server as deactivated.
        Raises appropriate exceptions if validation fails.
        """
        status = self.get_server_status(server_id)
        if status == "unknown":
            raise NotFoundError(f"Server '{server_id}' not found in DB.")

        if status == "deactivated":
            raise ToolError(f"Server '{server_id}' is already deactivated.")

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
