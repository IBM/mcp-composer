# database.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any


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
    def add_remove_tools(self, tools: list[str], server_id: str) -> None:
        pass

    @abstractmethod
    def fetch_remove_tools(self) -> Dict[Any, List]:
        pass
