# file_loader.py

import json
import os
from typing import Any, Dict, List, Optional

from dotenv import find_dotenv, load_dotenv

from mcp_composer.core.settings.base_adapter import SecretAdapter
from mcp_composer.core.utils.logger import LoggerFactory

load_dotenv(find_dotenv(".env"))

logger = LoggerFactory.get_logger()


class FileSecretAdapter(SecretAdapter):
    def __init__(
        self, file_path: str = "versioned_config.json", history_limit: int = 10
    ):
        self.file_path = file_path
        self.history_limit = history_limit
        self.history = {}
        self._load()

    def _load(self) -> None:
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    self.history = json.load(f)
            except (json.JSONDecodeError, OSError):
                self.history = {}
        else:
            self.history = {}

    def _save(self) -> None:
        """Writes current version history to the version file in JSON format."""
        if self.file_path:
            try:
                with open(self.file_path, "w", encoding="utf-8") as f:
                    json.dump(self.history, f, indent=2)
                logger.debug("Version history saved to file: %s", self.file_path)
            except OSError as e:
                logger.warning("Failed to save version history: %s", e)

    def load_config(self, server_id: str) -> Dict[str, Any]:
        """Loads version history from the file into memory."""
        try:
            if self.file_path is not None:
                logger.info("Version history loaded from file: %s", self.file_path)
                with open(self.file_path, "r", encoding="utf-8") as f:
                    self.history = json.load(f)
                    latest = self.get_latest_version(server_id)
                    return latest.get("config", {}) if latest else {}
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load version history from file: %s", e)
            self.history = {}
            return {}
        # Ensure a dictionary is always returned
        return {}

    def save_config(self, server_id: str, versions: list[dict[str, Any]]) -> None:
        self.history[server_id] = versions[-self.history_limit :]
        self._save()

    def get_all_versions(self, server_id: str) -> List[Dict[str, Any]]:
        """
        Get all saved versions for a given server.
        Args:
            server_id (str): The ID of the server.
        Returns:
            List[Dict[str, Any]]: List of version data dictionaries.
        """
        return self.history.get(server_id, [])

    def get_latest_version(self, server_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the most recent version config for a given server.
        Args:
            server_id (str): The ID of the server.
        Returns:
            Dict[str, Any]: Latest config version, or empty dict if none exist.
        """
        versions = self.get_all_versions(server_id)
        if versions:
            logger.debug(
                "Latest version for server '%s' is version_id=%s",
                server_id,
                versions[-1]["version_id"],
            )
        return versions[-1] if versions else {}

    def get_version_by_id(
        self, server_id: str, version_id: str
    ) -> Optional[Dict[str, Any]]:
        """_summary_

        Args:
            server_id (str): _description_
            version_id (str): _description_

        Returns:
            Optional[Dict[str, Any]]: _description_
        """
        for v in self.get_all_versions(server_id):
            if v["version_id"] == version_id:
                return v
        return None

    def rollback(self, server_id: str, version_id: str) -> dict[str, Any]:
        """
        Roll back to a specific version of a server config.
        Args:
            server_id (str): The ID of the server.
            version_id (str): The version ID to roll back to.
        Returns:
            Dict[str, Any]: The config corresponding to the specified version.
        Raises:
            ValueError: If the specified version ID is not found.
        """
        for version in self.history.get(server_id, []):
            if version["version_id"] == version_id:
                logger.info(
                    "Rolling back server '%s' to version_id=%s", server_id, version_id
                )
                return version["config"]

        logger.error(
            "No version with ID '%s' found for server '%s'", version_id, server_id
        )
        raise ValueError(
            f"No version with ID '{version_id}' found for server '{server_id}'"
        )
