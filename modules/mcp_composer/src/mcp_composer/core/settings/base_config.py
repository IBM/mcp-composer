from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    app_name: str = Field("MCP Composer", description="Name of the application.")
    debug: bool = Field(default=False, description="Enable debug mode.")

    model_config = SettingsConfigDict(env_file=".env", env_prefix="APP_")


class SecretAdapter(ABC):
    @abstractmethod
    def load_config(self, server_id: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    def save_config(self, server_id: str, versions: List[Dict[str, Any]]) -> None:
        pass

    @abstractmethod
    def get_all_versions(self, server_id: str) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_latest_version(self, server_id: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_version_by_id(
        self, server_id: str, version_id: str
    ) -> Optional[Dict[str, Any]]:
        pass
