"""Prompt management module for MCP Composer."""

import logging
from typing import Dict, List, Union

from fastmcp.prompts import PromptManager
from fastmcp.prompts.prompt import Prompt
from fastmcp.settings import DuplicateBehavior

from mcp_composer.core.member_servers.member_server import HealthStatus
from mcp_composer.core.member_servers.server_manager import ServerManager
from mcp_composer.core.utils import build_prompt_from_dict

logger = logging.getLogger(__name__)
# pylint: disable=W0718


class MCPPromptManager(PromptManager):
    """Custom prompt manager that works with FastMCP's internal PromptManager."""

    def __init__(
        self,
        server_manager: ServerManager,
        duplicate_behavior: DuplicateBehavior | None = None,
        database=None,
    ):
        super().__init__(duplicate_behavior)
        self._server_manager = server_manager
        self._database = database
        self._prompts: Dict[str, Prompt] = {}

    def unmount(self, server_id):
        """Unmount a member server."""
        for idx, mounted_server in enumerate(self._mounted_servers):
            if mounted_server.prefix == server_id:
                del self._mounted_servers[idx]

    def add_prompts(self, prompt_config: Union[dict, List[dict]]) -> List[str]:
        """
        Add one or more prompts based on the provided configuration.

        Args:
            prompt_config: Single prompt dict or list of prompt dicts

        Returns:
            List[str]: List of registered prompt names

        Raises:
            TypeError: If prompt_config is not a dict or list
            ValueError: If prompt configuration is invalid
        """
        if isinstance(prompt_config, dict):
            prompt_config = [prompt_config]
        elif not isinstance(prompt_config, list):
            raise TypeError("Prompt config must be a dict or a list of dicts")

        added = []
        errors = []

        for i, entry in enumerate(prompt_config):
            try:
                prompt = build_prompt_from_dict(entry)
                added_prompt = self.add_prompt(prompt)
                added.append(added_prompt.name)
                logger.info("Prompt '%s' added successfully", added_prompt.name)
            except Exception as e:
                error_msg = f"Failed to add prompt at index {i}: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg)

        if errors:
            logger.warning("Some prompts failed to add: %s", errors)

        return added

    async def list_prompts_per_server(self, server_id: str) -> List[Dict]:
        """List all prompts from a specific server."""
        try:
            if not self._server_manager or not self._server_manager.has_member_server(
                server_id
            ):
                return []

            # Use our filtered get_prompts method which automatically excludes disabled prompts
            all_prompts = await self.get_prompts()
            server_prompts = {}
            for key, prompt in all_prompts.items():
                if key.startswith(f"{server_id}_"):
                    server_prompts[key] = prompt
            result = []
            for key, prompt in server_prompts.items():
                name = getattr(prompt, "name", key)
                description = getattr(prompt, "description", "")
                result.append(
                    {
                        "name": name,
                        "description": description,
                        "template": str(prompt),
                        "server_id": server_id,
                    }
                )
            return result
        except Exception as e:
            logger.error("Error listing prompts for server '%s': %s", server_id, e)
            return []

    def _filter_disabled_prompts(self, prompts: dict[str, Prompt]) -> dict[str, Prompt]:
        """Filter prompts by performing the following actions for a member server,
        if it exists
        1. Remove disabled prompts
        2. Update description
        """
        try:
            if not self._server_manager:
                return prompts

            server_config = self._server_manager.list()
            if not server_config:
                return prompts

            remove_set = set()
            description_updates = {}

            for member in server_config:
                if member.health_status == HealthStatus.unhealthy:
                    continue

                if member.disabled_prompts:
                    remove_set.update(member.disabled_prompts)
                if member.prompts_description:
                    description_updates.update(member.prompts_description)

            filtered_prompts = {}
            for name, prompt in prompts.items():
                if name in remove_set:
                    continue
                if name in description_updates:
                    prompt.description = description_updates[name]
                filtered_prompts[name] = prompt
            return filtered_prompts
        except Exception as e:
            logger.exception("Prompts filtering failed: %s", e)
            raise

    async def get_prompts(self) -> dict[str, Prompt]:
        """
        Gets the complete, unfiltered inventory of all prompts and applies filtering.
        """
        prompts = await super().get_prompts()
        return self._filter_disabled_prompts(prompts)

    async def list_prompts(self) -> list[Prompt]:
        """
        Lists all prompts, applying protocol filtering and our custom disabled prompt filtering.
        """
        prompts_dict = await self.get_prompts()
        return list(prompts_dict.values())

    async def disable_prompts(self, prompts: list[str], server_id: str) -> str:
        """
        Disable a prompt or multiple prompts from the member server
        """
        if not self._server_manager:
            return "Server manager not available"

        try:
            self._server_manager.check_server_exist(server_id)
            server_prompts = await self.get_prompts()
            # Check if prompts exist in the server
            available_prompts = [
                name
                for name in server_prompts.keys()
                if name.startswith(f"{server_id}_")
            ]
            prompts_to_disable = []
            for prompt in prompts:
                full_prompt_name = f"{server_id}_{prompt}"
                if full_prompt_name in available_prompts:
                    prompts_to_disable.append(full_prompt_name)

            if not prompts_to_disable:
                return f"No prompts found to disable: {prompts}"

            self._server_manager.disable_prompts(prompts_to_disable, server_id)
            logger.info("Disabled %s prompts from server", prompts_to_disable)
            return f"Disabled {prompts_to_disable} prompts from server {server_id}"
        except Exception as e:
            logger.error("Error disabling prompts: %s", e)
            return f"Failed to disable prompts: {str(e)}"

    async def enable_prompts(self, prompts: list[str], server_id: str) -> str:
        """
        Enable a prompt or multiple prompts from the member server
        """
        if not self._server_manager:
            return "Server manager not available"

        try:
            self._server_manager.check_server_exist(server_id)
            # Convert prompt names to full names with server prefix
            prompts_to_enable = [f"{server_id}_{prompt}" for prompt in prompts]
            self._server_manager.enable_prompts(prompts_to_enable, server_id)
            logger.info("Enabled %s prompts from server", prompts_to_enable)
            return f"Enabled {prompts_to_enable} prompts from server {server_id}"
        except Exception as e:
            logger.error("Error enabling prompts: %s", e)
            return f"Failed to enable prompts: {str(e)}"

    async def filter_prompts(self, filter_criteria: dict) -> list[dict]:
        """Filter prompts based on criteria like name, description, tags."""
        try:
            prompts_dict = await self.get_prompts()
            result = []

            for key, prompt in prompts_dict.items():
                match = True
                name = getattr(prompt, "name", key)
                description = getattr(prompt, "description", "")
                tags = getattr(prompt, "tags", [])

                if "name" in filter_criteria and filter_criteria["name"]:
                    if filter_criteria["name"].lower() not in name.lower():
                        match = False

                if (
                    match
                    and "description" in filter_criteria
                    and filter_criteria["description"]
                ):
                    if (
                        filter_criteria["description"].lower()
                        not in description.lower()
                    ):
                        match = False

                if match and "tags" in filter_criteria and filter_criteria["tags"]:
                    if not any(tag in tags for tag in filter_criteria["tags"]):
                        match = False

                if match:
                    result.append(
                        {
                            "name": name,
                            "description": description,
                            "template": str(prompt),
                        }
                    )

            return result
        except Exception as e:
            logger.error("Error filtering prompts: %s", e)
            return []
