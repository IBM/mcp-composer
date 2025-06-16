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
    def add_remove_tools(self, tools: list[str], server_id: str) -> None:
        pass

    @abstractmethod
    def update_tool_description(
        self, tool: str, description: str, server_id: str
    ) -> None:
        pass
