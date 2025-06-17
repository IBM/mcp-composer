import json
from pathlib import Path
from typing import List, Dict
from mcp_composer.utils import LoggerFactory, check_duplicate_tool
from mcp_composer.exceptions import ToolDuplicateError
from .database import DatabaseInterface

logger = LoggerFactory.get_logger()


class LocalFileAdapter(DatabaseInterface):
    def __init__(self, file_path: str = "mcp_servers.json"):
        self._file_path = Path(file_path)
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        if not self._file_path.exists():
            self._file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._file_path, "w") as f:
                json.dump([], f)

    def _read_data(self) -> List[Dict]:
        try:
            with open(self._file_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _write_data(self, data: List[Dict]):
        with open(self._file_path, "w") as f:
            json.dump(data, f, indent=2)

    def load_all_servers(self) -> List[Dict]:
        return self._read_data()

    def add_server(self, config: Dict) -> None:
        data = self._read_data()
        server_id = config["id"]

        # Check if server already exists
        if any(server.get("id") == server_id for server in data):
            logger.info(
                "Server '%s' already exists in local file. Skipping add.", server_id
            )
            return

        data.append(config)
        self._write_data(data)
        logger.info("Saved server '%s' to local file", server_id)

    def remove_server(self, server_id: str) -> None:
        data = self._read_data()
        updated_data = [server for server in data if server.get("id") != server_id]

        if len(updated_data) < len(data):
            self._write_data(updated_data)
            logger.info("Deleted server '%s' from local file", server_id)
        else:
            logger.info("Server '%s' not found in local file", server_id)

    def get_document(self, server_id: str) -> Dict:
        # get the server config details of a single server
        data = self._read_data()
        for server_cfg in data:
            if server_cfg["id"] == server_id:
                logger.info(
                    f"Retrive server({server_id}) config details from local. Response: {server_cfg}"
                )
            return server_cfg
        return {}

    def add_remove_tools(self, tools: list[str], server_id: str) -> None:
        data = self._read_data()
        tools = list(set(tools))

        for server in data:
            if server.get("id") != server_id:
                continue

            existing_tools = server.get("remove_tools", [])
            tools_description = server.get("tools_description", {})

            duplicate_tool = check_duplicate_tool(existing_tools, tools)
            if duplicate_tool:
                raise ToolDuplicateError(f"Tool {duplicate_tool} is already removed")

            # Update remove_tools
            if existing_tools:
                server["remove_tools"].extend(tools)
                logger.info(
                    f"Updated remove tool list for server {server_id}. "
                    f"Previous tools: {existing_tools}"
                )
            else:
                server["remove_tools"] = tools
                logger.info(
                    f"Added new remove tool list {tools} for server {server_id}."
                )

            # Remove tool descriptions if they exist
            if server["remove_tools"] and tools_description:
                for tool in server["remove_tools"]:
                    tools_description.pop(tool, None)

            break

        self._write_data(data)

    def update_tool_description(
        self, tool: str, description: str, server_id: str
    ) -> None:
        data = self._read_data()
        for server in data:
            if server.get("id") == server_id:
                tools_description = server.get("tools_description")
                # if tools description already found, update it
                # if not add the tools description
                if tools_description:
                    tools_description.update({tool: description})
                    logger.info(
                        f"Tool description: {tools_description} is updated for server: {server_id}"
                    )
                else:
                    server["tools_description"] = {tool: description}
                    logger.info(
                        f"Tool description: {tools_description} is added for server: {server_id}"
                    )

        self._write_data(data)
