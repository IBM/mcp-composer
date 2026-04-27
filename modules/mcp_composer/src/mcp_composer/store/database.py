# database.py
from abc import ABC, abstractmethod


class DatabaseInterface(ABC):
    @abstractmethod
    def load_all_servers(self) -> list[dict[str, object]]:
        pass

    @abstractmethod
    def add_server(self, config: dict[str, object]) -> None:
        pass

    @abstractmethod
    def remove_server(self, server_id: str) -> None:
        pass

    @abstractmethod
    def get_document(self, server_id: str) -> dict[str, object]:
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
        pass

    @abstractmethod
    def get_server_status(self, server_id: str) -> str:
        pass

    @abstractmethod
    def update_server_config(self, config: dict[str, object]) -> None:
        pass

    @abstractmethod
    def load_all_resources(self) -> list[dict[str, object]]:
        pass

    @abstractmethod
    def upsert_resource(self, resource: dict[str, object]) -> None:
        pass

    @abstractmethod
    def delete_resource(self, resource_id: str) -> None:
        pass

    @abstractmethod
    def load_all_prompts(self) -> list[dict[str, object]]:
        """Load all prompts from storage"""
        pass

    @abstractmethod
    def add_prompt(self, prompt: dict[str, object]) -> None:
        """Add or update a prompt in storage"""
        pass

    @abstractmethod
    def remove_prompt(self, prompt_name: str) -> None:
        """Remove a prompt from storage"""
        pass

    @abstractmethod
    def get_prompt(self, prompt_name: str) -> dict[str, object]:
        """Get a specific prompt from storage"""
        pass
