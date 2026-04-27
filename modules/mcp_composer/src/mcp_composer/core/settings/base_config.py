from abc import ABC, abstractmethod
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    app_name: str = Field("MCP Composer", description="Name of the application.")
    debug: bool = Field(default=False, description="Enable debug mode.")

    model_config = SettingsConfigDict(env_file=".env", env_prefix="APP_")


class SecretAdapter(ABC):
    @abstractmethod
    def load_config(self, server_id: str) -> dict[str, Any]:
        pass

    @abstractmethod
    def save_config(self, server_id: str, versions: list[dict[str, Any]]) -> None:
        pass

    @abstractmethod
    def get_all_versions(self, server_id: str) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    def get_latest_version(self, server_id: str) -> dict[str, Any] | None:
        pass

    @abstractmethod
    def get_version_by_id(
        self, server_id: str, version_id: str
    ) -> dict[str, Any] | None:
        pass
