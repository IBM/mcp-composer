# database.py
from abc import ABC, abstractmethod
from typing import List, Dict


class DatabaseInterface(ABC):
    @abstractmethod
    def load_all_servers(self) -> List[Dict]:
        pass

    @abstractmethod
    def add_server(self, config: Dict) -> None:
        pass

    @abstractmethod
    def remove_server(self, server_id: str) -> None:
        pass

    @abstractmethod
    def get_document(self, server_id: str) -> Dict:
        pass

    @abstractmethod
    def enable_tools(self, tools: list[str], server_id: str) -> None:
        pass

    @abstractmethod
    def disable_tools(self, tools: list[str], server_id: str) -> None:
        pass

    @abstractmethod
    def update_tool_description(
        self, tool: str, description: str, server_id: str
    ) -> None:
        pass

    @abstractmethod
    def enable_prompts(self, prompts: list[str], server_id: str) -> None:
        pass

    @abstractmethod
    def disable_prompts(self, prompts: list[str], server_id: str) -> None:
        pass

    @abstractmethod
    def enable_resources(self, resources: list[str], server_id: str) -> None:
        pass

    @abstractmethod
    def disable_resources(self, resources: list[str], server_id: str) -> None:
        pass

    @abstractmethod
    def mark_deactivated(self, server_id: str) -> None:
        """Marks the given server as deactivated (sets status='deactivated')"""
        pass

    @abstractmethod
    def get_server_status(self, server_id: str) -> str:
        """Returns the status of the given server (e.g., 'active' or 'deactivated')"""
        pass

    @abstractmethod
    def update_server_config(self, config: dict) -> None:
        pass

    @abstractmethod
    def load_all_resources(self) -> List[Dict]:
        """Return all stored resource/template definitions."""
        pass

    @abstractmethod
    def upsert_resource(self, resource: Dict) -> None:
        """Insert or update a stored resource/template definition."""
        pass

    @abstractmethod
    def delete_resource(self, resource_id: str) -> None:
        """Remove a stored resource/template definition."""
        pass
