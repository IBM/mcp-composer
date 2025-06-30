import json
from pathlib import Path
from typing import List, Dict
from mcp_composer.utils import LoggerFactory, check_duplicate_tool
from mcp_composer.exceptions import ToolDuplicateError
from .database import DatabaseInterface
import os
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(".env"))

logger = LoggerFactory.get_logger()

MEMBER_SERVER_CONFIG_FILE_PATH = os.environ["SERVER_CONFIG_FILE_PATH"]
TOOLS_CONFIG_FILE_PATH = os.environ["TOOLS_CONFIG_FILE_PATH"]


class LocalFileAdapter(DatabaseInterface):
    def __init__(
        self,
        file_path: str = MEMBER_SERVER_CONFIG_FILE_PATH,
        tool_file_path: str = TOOLS_CONFIG_FILE_PATH,
    ):
        self._file_path = Path(file_path)
        self._tool_path = Path(tool_file_path)
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        if not self._file_path.exists():
            self._file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._file_path, "w") as f:
                json.dump([], f)

    def _read_data(self, file_type="server") -> List[Dict]:
        path = self._tool_path if file_type == "tool" else self._file_path

        try:
            with open(path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _write_data(self, data: List[Dict], file_type="server"):
        path = self._tool_path if file_type == "tool" else self._file_path
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def load_all_servers(self) -> List[Dict]:
        return self._read_data()

    def load_tools(self) -> List[Dict]:
        return self._read_data(file_type="tool")

    def add_server(self, config: Dict) -> None:
        data = self._read_data()
        server_id = config["id"]

        updated = False
        for i, server in enumerate(data):
            if server.get("id") == server_id:
                data[i] = config  # Overwrite with new config
                updated = True
                logger.info("Updated server '%s' in local file", server_id)
                break

        if not updated:
            data.append(config)
            logger.info("Added new server '%s' to local file", server_id)

        self._write_data(data)

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

    def mark_deactivated(self, server_id: str) -> None:
        data = self._read_data()
        for server in data:
            if server.get("id") == server_id:
                server["status"] = "deactivated"
                logger.info(f"Marked server '{server_id}' as deactivated.")
                break
        self._write_data(data)

    def get_server_status(self, server_id: str) -> str:
        data = self._read_data()
        for server in data:
            if server.get("id") == server_id:
                return server.get("status", "active")
        return "unknown"

    def add_tool(self, tool_config: dict) -> None:
        data = self._read_data(file_type="tool")
        tool_id = tool_config.get("id")
        updated = False
        for i, tool in enumerate(data):
            if tool.get("id") == tool_id:
                data[i] = tool_config  # Overwrite with new config
                updated = True
                logger.info("Updated tool '%s' in local file", tool_id)
                break

        if not updated:
            data.append(tool_config)
            logger.info("Added new tool '%s' to local file", tool_id)

        self._write_data(data, file_type="tool")
