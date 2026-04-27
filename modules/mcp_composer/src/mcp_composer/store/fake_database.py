from mcp_composer.store.database import DatabaseInterface


class FakeDatabase(DatabaseInterface):
    """A simple in-memory DB stub used for tests.

    Implements all abstract methods from DatabaseInterface for testing purposes.
    """

    def __init__(self) -> None:
        self._servers: dict[str, dict[str, object]] = {}
        self._tools: list[dict[str, object]] = []
        self._resources: dict[str, dict[str, object]] = {}
        self._prompts: dict[str, dict[str, object]] = {}

    def load_all_servers(self) -> list[dict[str, object]]:
        return list(self._servers.values())

    def add_server(self, config: dict[str, object]) -> None:
        server_id = str(config["id"])
        self._servers[server_id] = config

    def remove_server(self, server_id: str) -> None:
        self._servers.pop(server_id, None)

    def reset(self) -> None:
        self._servers.clear()
        self._tools.clear()
        self._resources.clear()
        self._prompts.clear()

    def mark_deactivated(self, server_id: str) -> None:
        if server_id in self._servers:
            self._servers[server_id]["status"] = "deactivated"

    def get_server_status(self, server_id: str) -> str:
        server = self._servers.get(server_id)
        if server:
            status = server.get("status", "active")
            return str(status)
        return "unknown"

    def get_document(self, server_id: str) -> dict[str, object]:
        return self._servers.get(server_id, {})

    def disable_tools(self, tools: list[str], server_id: str) -> None:
        for tool_name in tools:
            self._tools = [t for t in self._tools if t["name"] != tool_name]

    def enable_tools(self, tools: list[str], server_id: str) -> None:
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
            disabled = self._servers[server_id]["disabled_prompts"]
            if isinstance(disabled, list):
                disabled.extend(prompts)

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
            disabled = self._servers[server_id]["disabled_resources"]
            if isinstance(disabled, list):
                disabled.extend(resources)

    def enable_resources(self, resources: list[str], server_id: str) -> None:
        """Enable resources in the fake database."""
        if server_id in self._servers:
            if "disabled_resources" in self._servers[server_id]:
                self._servers[server_id]["disabled_resources"] = resources

    def update_server_config(self, config: dict[str, object]) -> None:
        server_id = str(config["id"])
        self._servers[server_id] = config

    def load_all_resources(self) -> list[dict[str, object]]:
        return list(self._resources.values())

    def upsert_resource(self, resource: dict[str, object]) -> None:
        storage_id = str(resource["storage_id"])
        self._resources[storage_id] = resource

    def delete_resource(self, resource_id: str) -> None:
        self._resources.pop(resource_id, None)

    def load_all_prompts(self) -> list[dict[str, object]]:
        """Load all prompts from storage"""
        return list(self._prompts.values())

    def add_prompt(self, prompt: dict[str, object]) -> None:
        """Add or update a prompt in storage"""
        prompt_name = prompt.get("name")
        if prompt_name:
            self._prompts[str(prompt_name)] = prompt

    def remove_prompt(self, prompt_name: str) -> None:
        """Remove a prompt from storage"""
        self._prompts.pop(prompt_name, None)

    def get_prompt(self, prompt_name: str) -> dict[str, object]:
        """Get a specific prompt from storage"""
        return self._prompts.get(prompt_name, {})
