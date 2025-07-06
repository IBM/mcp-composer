from typing import Dict, List
from mcp_composer.store.database import DatabaseInterface


class FakeDatabase(DatabaseInterface):
    """A simple in-memory DB stub used for tests."""

    def __init__(self) -> None:
        self._servers: dict[str, Dict] = {}
        self._tools: list[Dict] = []

    def load_all_servers(self) -> list[Dict]:
        return list(self._servers.values())

    def add_server(self, config: Dict) -> None:
        self._servers[config["id"]] = config

    def remove_server(self, server_id: str) -> None:
        self._servers.pop(server_id, None)

    def reset(self) -> None:
        self._servers.clear()
        self._tools.clear()

    def mark_deactivated(self, server_id: str) -> None:
        if server_id in self._servers:
            self._servers[server_id]["status"] = "deactivated"

    def get_server_status(self, server_id: str) -> str:
        server = self._servers.get(server_id)
        if server:
            return server.get("status", "active")
        return "unknown"

    def get_document(self, server_id: str) -> Dict:
        return self._servers.get(server_id, {})

    def add_remove_tools(self, tools: list[str], server_id: str) -> None:
        for tool_name in tools:
            self._tools = [t for t in self._tools if t["name"] != tool_name]

    def update_tool_description(
        self, tool: str, description: str, server_id: str
    ) -> None:
        for t in self._tools:
            if t["name"] == tool:
                t["description"] = description

    def add_tool(self, tool_config: dict) -> None:
        self._tools.append(tool_config)

    def load_tools(self) -> List[Dict]:
        return self._tools

    def update_server_config(self, config: dict) -> None:
        self._servers[config["id"]] = config
