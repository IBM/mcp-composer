# base_adapter.py

from abc import ABC, abstractmethod
from typing import Any


class SecretAdapter(ABC):
    """
    Abstract adapter interface for secret/config version storage.
    """

    @abstractmethod
    def load_config(self, server_id: str) -> dict[str, Any]:
        """Return the latest config for the server."""

    @abstractmethod
    def save_config(self, server_id: str, versions: list[dict[str, Any]]) -> None:
        """Save a list of versions for the given server."""

    @abstractmethod
    def get_all_versions(self, server_id: str) -> list[dict[str, Any]]:
        """Return all versions for a given server."""

    @abstractmethod
    def get_latest_version(self, server_id: str) -> dict[str, Any] | None:
        """Return the latest version of the config."""

    @abstractmethod
    def get_version_by_id(
        self, server_id: str, version_id: str
    ) -> dict[str, Any] | None:
        """Return a specific version by ID."""

    @abstractmethod
    def rollback(self, server_id: str, version_id: str) -> dict[str, Any]:
        """
        Roll back the server config to a previous version.

        Returns:
            The rolled-back config dictionary.
        Raises:
            ValueError: if the specified version_id is not found.
        """
