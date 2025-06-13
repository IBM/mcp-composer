from typing import Dict
from mcp_gateway.store.database import DatabaseInterface


class FakeDatabase(DatabaseInterface):
    """A simple in-memory DB stub used for tests."""

    def __init__(self) -> None:
        self._servers: dict[str, Dict] = {}

    def load_all_servers(self) -> list[Dict]:
        return list(self._servers.values())

    def add_server(self, config: Dict) -> None:
        self._servers[config["id"]] = config

    def remove_server(self, server_id: str) -> None:
        self._servers.pop(server_id, None)

    def reset(self) -> None:
        self._servers.clear()

    def get_document(self, server_id):
        raise NotImplementedError

    def add_remove_tools(self, tools, server_id):
        raise NotImplementedError
