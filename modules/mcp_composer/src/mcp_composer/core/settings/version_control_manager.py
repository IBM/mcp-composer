import uuid
import datetime
import copy
from typing import Any
from mcp_composer.core.settings.base_adapter import SecretAdapter


class ConfigManager:
    """Manager for version control of configurations using an adapter pattern.
    This module provides a ConfigManager class that interacts with a SecretAdapter to manage configuration versions.
    It allows saving, retrieving, and rolling back configurations based on version IDs.
    """

    def __init__(self, adapter: SecretAdapter):
        self.adapter = adapter

    def _timestamp(self) -> str:
        """Returns the current timestamp in ISO format."""
        return datetime.datetime.now(datetime.timezone.utc).isoformat()

    def save_version(self, server_id: str, config: dict[str, Any]) -> str:
        """Writes current version history to the version file in JSON format

        Args:
            server_id (str): _description_
            config (dict[str, Any]): _description_

        Returns:
            str: _description_
        """
        version_id = str(uuid.uuid4())
        version_data = {
            "version_id": version_id,
            "timestamp": self._timestamp(),
            "config": copy.deepcopy(config),
        }
        versions = self.adapter.get_all_versions(server_id)
        versions.append(version_data)
        self.adapter.save_config(server_id, versions)
        return version_id

    def get_latest_version(self, server_id: str) -> dict[str, Any]:
        """Returns the latest version of the config for the given server ID."""
        latest = self.adapter.get_latest_version(server_id)
        return latest.get("config", {}) if latest else {}

    def get_all_versions(self, server_id: str) -> list[dict[str, Any]]:
        """Returns all versions of the config for the given server ID."""
        return self.adapter.get_all_versions(server_id)

    def rollback(self, server_id: str, version_id: str) -> dict[str, Any]:
        """Rolls back to a specific version by ID for the given server ID."""
        version = self.adapter.get_version_by_id(server_id, version_id)
        if version:
            return version["config"]
        raise ValueError(
            f"Version ID '{version_id}' not found for server '{server_id}'"
        )
