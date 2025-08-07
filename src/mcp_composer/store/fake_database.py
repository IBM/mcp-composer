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

    def disable_tools(self, tools: list[str], server_id: str) -> None:
        for tool_name in tools:
            self._tools = [t for t in self._tools if t["name"] != tool_name]

    def enable_tools(self, tools: List[str], server_id: str) -> None:
        """Adds tools to the tool list if not already present."""
        for tool_name in tools:
            if not any(t["name"] == tool_name for t in self._tools):
                self._tools.append(
                    {"name": tool_name, "server_id": server_id, "description": ""}
                )

    def update_tool_description(
        self, tool: str, description: str, server_id: str
    ) -> None:
        for t in self._tools:
            if t["name"] == tool:
                t["description"] = description

    def disable_prompts(self, prompts: list[str], server_id: str) -> None:
        """Disable prompts in the fake database."""
        if server_id in self._servers:
            if "disabled_prompts" not in self._servers[server_id]:
                self._servers[server_id]["disabled_prompts"] = []
            self._servers[server_id]["disabled_prompts"].extend(prompts)

    def enable_prompts(self, prompts: list[str], server_id: str) -> None:
        """Enable prompts in the fake database."""
        if server_id in self._servers:
            if "disabled_prompts" in self._servers[server_id]:
                self._servers[server_id]["disabled_prompts"] = prompts

    def disable_resources(self, resources: list[str], server_id: str) -> None:
        """Disable resources in the fake database."""
        if server_id in self._servers:
            if "disabled_resources" not in self._servers[server_id]:
                self._servers[server_id]["disabled_resources"] = []
            self._servers[server_id]["disabled_resources"].extend(resources)

    def enable_resources(self, resources: list[str], server_id: str) -> None:
        """Enable resources in the fake database."""
        if server_id in self._servers:
            if "disabled_resources" in self._servers[server_id]:
                self._servers[server_id]["disabled_resources"] = resources

    def update_server_config(self, config: dict) -> None:
        self._servers[config["id"]] = config
