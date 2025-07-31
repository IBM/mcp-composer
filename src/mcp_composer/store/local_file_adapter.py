"""Local File adapter"""

import os
import json
from pathlib import Path
from typing import List, Dict
from dotenv import load_dotenv, find_dotenv

from mcp_composer.utils import LoggerFactory
from mcp_composer.exceptions import ToolDuplicateError
from mcp_composer.utils.tools import check_duplicate_tool
from .database import DatabaseInterface

load_dotenv(find_dotenv(".env"))

logger = LoggerFactory.get_logger()


class LocalFileAdapter(DatabaseInterface):
    """Local file storage"""

    def __init__(
        self,
        file_path: str | None = None,
    ):
        if file_path is None:
            file_path = os.getenv("SERVER_CONFIG_FILE_PATH", "member_servers.json")
        self._file_path = Path(file_path)
        logger.info("Using local file storage: %s", self._file_path)
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        if not self._file_path.exists():
            self._file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._file_path, "w", encoding="utf-8") as f:
                json.dump([], f)

    def _read_data(self) -> List[Dict]:
        try:
            with open(self._file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _write_data(self, data: List[Dict]):
        with open(self._file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def load_all_servers(self) -> List[Dict]:
        """Fetch all member server from file storage"""
        return self._read_data()

    def add_server(self, config: Dict) -> None:
        """Add members server"""
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
        """Remove members server"""
        data = self._read_data()
        updated_data = [server for server in data if server.get("id") != server_id]

        if len(updated_data) < len(data):
            self._write_data(updated_data)
            logger.info("Deleted server '%s' from local file", server_id)
        else:
            logger.info("Server '%s' not found in local file", server_id)

    def get_document(self, server_id: str) -> Dict:
        """get the server config details of a single server"""
        data = self._read_data()
        for server_cfg in data:
            if server_cfg["id"] == server_id:
                logger.info(
                    "Retrieve server(%s) config details from local. Response: %s",
                    server_id,
                    server_cfg,
                )
            return server_cfg
        return {}

    def disable_tools(self, tools: list[str], server_id: str) -> None:
        """Add or Update disabled tools in file for the member server"""
        data = self._read_data()
        tools = list(set(tools))

        for server in data:
            if server.get("id") != server_id:
                continue

            existing_tools = server.get("disabled_tools", [])
            tools_description = server.get("tools_description", {})

            duplicate_tool = check_duplicate_tool(existing_tools, tools)
            if duplicate_tool:
                raise ToolDuplicateError(f"Tool {duplicate_tool} is already removed")

            # Update disabled_tools
            if existing_tools:
                server["disabled_tools"].extend(tools)
                logger.info("Updated remove tool list for server:%s", server_id)
                logger.info("Previous tools:%s", existing_tools)
            else:
                server["disabled_tools"] = tools
                logger.info(
                    "Added new remove tool list: %s  for server %s", tools, server_id
                )

            # Remove tool descriptions if they exist
            if server["disabled_tools"] and tools_description:
                for tool in server["disabled_tools"]:
                    tools_description.pop(tool, None)

            break

        self._write_data(data)

    def enable_tools(self, tools: list[str], server_id: str) -> None:
        """Enable tools which already disabled"""
        data = self._read_data()
        tools = list(set(tools))
        for server in data:
            if server.get("id") != server_id:
                continue

            server["disabled_tools"] = tools = tools
            logger.info(
                "Updated disabled tool list for server:%s, disabled tools:%s",
                server_id,
                server["disabled_tools"],
            )

            break
        self._write_data(data)

    def update_tool_description(
        self, tool: str, description: str, server_id: str
    ) -> None:
        """store tool description of member server in file storage"""
        data = self._read_data()
        for server in data:
            if server.get("id") == server_id:
                tools_description = server.get("tools_description")
                # if tools description already found, update it
                # if not add the tools description
                if tools_description:
                    tools_description.update({tool: description})
                    logger.info(
                        "Tool description:%s is updated for server: %s",
                        tools_description,
                        server_id,
                    )
                else:
                    server["tools_description"] = {tool: description}
                    logger.info(
                        "Tool description: %s is added for server: %s",
                        tools_description,
                        server_id,
                    )

        self._write_data(data)

    def mark_deactivated(self, server_id: str) -> None:
        """Save deactivated member server"""
        data = self._read_data()
        for server in data:
            if server.get("id") == server_id:
                server["status"] = "deactivated"
                logger.info("Marked server %s  as deactivated.", server_id)
                break
        self._write_data(data)

    def get_server_status(self, server_id: str) -> str:
        """Get server status"""
        data = self._read_data()
        for server in data:
            if server.get("id") == server_id:
                return server.get("status", "active")
        return "unknown"

    def update_server_config(self, config: dict) -> None:
        """
        Update local JSON file with new server config.
        """
        server_id = config.get("id")
        if not server_id:
            raise ValueError("Server config must contain an 'id' field")

        data = self._read_data()

        updated = False
        for i, entry in enumerate(data):
            if entry.get("id") == server_id:
                data[i] = config
                updated = True
                break

        if not updated:
            raise ValueError(f"Server '{server_id}' not found in local database")

        self._write_data(data)
        logger.info("Updated local config for server %s", server_id)
