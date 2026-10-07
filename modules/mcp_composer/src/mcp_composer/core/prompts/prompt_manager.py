"""Prompt management module for MCP Composer.

MCPPromptManager registers FastMCP ``Prompt`` objects in memory and optionally
persists composer prompt configs via ``DatabaseInterface`` (e.g. ``load_all_prompts`` /
``add_prompt``). That is separate from ``mcp_composer.core.catalog.prompt_manager``,
which implements the versioned prompt *catalog* on ``CatalogDatabaseInterface``
(``catalog_resources`` rows). The two managers are not interchangeable.

When ``MCP_DATABASE_TYPE=postgres``, composer persistence and the catalog use the same
``MCP_DATABASE_URL`` / ``MCP_DATABASE_HOST`` (etc.) environment variables, but
different tables: composer prompts live in the adapter's ``*_prompts`` table; catalog
prompts use ``catalog_resources``.
"""

import logging

from fastmcp.prompts import Prompt

from mcp_composer.core.member_servers.member_server import HealthStatus
from mcp_composer.core.member_servers.server_manager import ServerManager
from mcp_composer.core.utils import build_prompt_from_dict

logger = logging.getLogger(__name__)
# pylint: disable=W0718


class MCPPromptManager:
    """Runtime FastMCP prompt registry; not a substitute for the catalog PromptManager."""

    def __init__(
        self,
        server_manager: ServerManager,
        database=None,
    ):
        self._server_manager = server_manager
        self._database = database
        self._prompts: dict[str, Prompt] = {}
        self.warn_on_duplicate_prompts = True

    def get_prompt(self, name: str) -> Prompt | None:
        """Get prompt by name."""
        return self._prompts.get(name)

    def add_prompt(self, prompt: Prompt) -> Prompt:
        """Add a prompt to the manager."""
        # Check for duplicates
        existing = self._prompts.get(prompt.name)
        if existing:
            if self.warn_on_duplicate_prompts:
                logger.warning("Prompt already exists: %s", prompt.name)
            return existing
        self._prompts[prompt.name] = prompt
        return prompt

    def add_prompts(self, prompt_config: dict | list[dict]) -> list[str]:
        """
        Add one or more prompts based on the provided configuration.

        Args:
            prompt_config: Single prompt dict or list of prompt dicts

        Returns:
            list[str]: List of registered prompt names

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

                # Save to database if available
                if self._database:
                    try:
                        self._save_prompt_to_db(entry)
                    except Exception as db_error:
                        logger.warning(
                            "Failed to save prompt '%s' to database: %s",
                            added_prompt.name,
                            db_error,
                        )
            except Exception as e:
                error_msg = f"Failed to add prompt at index {i}: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg)

        if errors:
            logger.warning("Some prompts failed to add: %s", errors)

        return added

    def _save_prompt_to_db(self, prompt_config: dict) -> None:
        """Save a prompt configuration to the database."""
        if not self._database:
            return

        try:
            self._database.add_prompt(prompt_config)
            logger.debug("Saved prompt '%s' to database", prompt_config.get("name"))
        except Exception as e:
            logger.error("Failed to save prompt to database: %s", e)
            raise

    def load_prompts_from_db(self) -> list[str]:
        """Load all prompts from database and register them."""
        if not self._database:
            logger.info("No database configured, skipping prompt loading")
            return []

        try:
            stored_prompts = self._database.load_all_prompts()
            logger.info("Loading %d prompts from database", len(stored_prompts))

            loaded = []
            for prompt_config in stored_prompts:
                try:
                    prompt = build_prompt_from_dict(prompt_config)
                    added_prompt = self.add_prompt(prompt)
                    loaded.append(added_prompt.name)
                    logger.info("Loaded prompt '%s' from database", added_prompt.name)
                except Exception as e:
                    logger.error(
                        "Failed to load prompt '%s' from database: %s",
                        prompt_config.get("name", "unknown"),
                        e,
                    )

            return loaded
        except Exception as e:
            logger.error("Failed to load prompts from database: %s", e)
            return []

    def delete_prompts(self, prompt_names: str | list[str]) -> dict[str, str]:
        """
        Delete one or more prompts from the composer and database.

        Args:
            prompt_names: Single prompt name or list of prompt names to delete

        Returns:
            dict[str, str]: Dictionary with prompt names as keys and status messages as values
        """
        if isinstance(prompt_names, str):
            prompt_names = [prompt_names]
        elif not isinstance(prompt_names, list):
            raise TypeError("Prompt names must be a string or a list of strings")

        results = {}

        for prompt_name in prompt_names:
            try:
                # Remove from in-memory prompts
                if prompt_name in self._prompts:
                    del self._prompts[prompt_name]
                    logger.info("Removed prompt '%s'", prompt_name)
                else:
                    logger.warning("Prompt '%s' not found in memory", prompt_name)

                # Remove from database if available
                if self._database:
                    try:
                        self._database.remove_prompt(prompt_name)
                        results[prompt_name] = "Successfully deleted"
                        logger.info("Deleted prompt '%s'", prompt_name)
                    except Exception as db_error:
                        results[prompt_name] = (
                            f"Deleted from memory but failed to delete from database: {str(db_error)}"
                        )
                        logger.warning(
                            "Failed to delete prompt '%s' from database: %s",
                            prompt_name,
                            db_error,
                        )
                else:
                    results[prompt_name] = (
                        "Successfully deleted from memory (no database configured)"
                    )

            except Exception as e:
                error_msg = f"Failed to delete prompt: {str(e)}"
                results[prompt_name] = error_msg
                logger.error("Failed to delete prompt '%s': %s", prompt_name, e)

        return results

    async def list_prompts_per_server(self, server_id: str) -> list[dict[str, object]]:
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
        return self._filter_disabled_prompts(self._prompts)

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
