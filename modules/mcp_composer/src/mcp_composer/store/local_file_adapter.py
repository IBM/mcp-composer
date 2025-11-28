"""Local File adapter"""

import os
import json
from pathlib import Path
from typing import List, Dict
from dotenv import load_dotenv, find_dotenv

from mcp_composer.core.utils import LoggerFactory
from mcp_composer.core.utils.exceptions import ToolDuplicateError
from mcp_composer.core.utils.tools import check_duplicate_tool
from .database import DatabaseInterface

load_dotenv(find_dotenv(".env"))

logger = LoggerFactory.get_logger()


class LocalFileAdapter(DatabaseInterface):
    """Local file storage"""

    def __init__(
        self,
        file_path: str | None = None,
        resources_file_path: str | None = None,
    ):
        if file_path is None:
            file_path = os.getenv("SERVER_CONFIG_FILE_PATH", "member_servers.json")
        self._file_path = Path(file_path)
        if resources_file_path is None:
            resources_file_path = os.getenv(
                "RESOURCE_CONFIG_FILE_PATH", "composer_resources.json"
            )
        self._resources_file_path = Path(resources_file_path)
        logger.info(
            "Using local file storage for configuration storage: %s", self._file_path
        )

        # Initialize file availability flag to False (pessimistic approach)
        self._file_available = False
        self._resources_file_available = False

        self._ensure_file_exists()
        self._ensure_resources_file_exists()

    def _ensure_file_exists(self) -> None:
        """Ensure the file exists, create it if it doesn't. Fail gracefully if creation fails."""
        if not self._file_path.exists():
            try:
                logger.info("Creating member_servers.json file")
                self._file_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self._file_path, "w", encoding="utf-8") as f:
                    json.dump([], f)
                logger.info("Successfully created member_servers.json file")
            except Exception as e:
                logger.warning(
                    "Failed to create member_servers.json file: %s. Continuing without file persistence.",
                    e,
                )
                # Set a flag to indicate file operations are not available
                self._file_available = False
            else:
                self._file_available = True
        else:
            self._file_available = True

    def _ensure_resources_file_exists(self) -> None:
        if not self._resources_file_path.exists():
            try:
                logger.info("Creating composer resources storage file")
                self._resources_file_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self._resources_file_path, "w", encoding="utf-8") as f:
                    json.dump([], f)
                logger.info("Successfully created composer resources storage file")
            except Exception as e:
                logger.warning(
                    "Failed to create composer resources storage file: %s. Continuing without file persistence.",
                    e,
                )
                self._resources_file_available = False
            else:
                self._resources_file_available = True
        else:
            self._resources_file_available = True

    def _read_data(self) -> List[Dict]:
        if not self._file_available:
            logger.debug("File not available, returning empty data")
            return []

        try:
            with open(self._file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []
        except Exception as e:
            logger.warning("Failed to read from member_servers.json file: %s", e)
            # Mark file as unavailable for future operations
            self._file_available = False
            return []

    def _write_data(self, data: List[Dict]) -> None:
        if not self._file_available:
            logger.debug("File not available, skipping write operation")
            return

        try:
            with open(self._file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning("Failed to write to member_servers.json file: %s", e)
            # Mark file as unavailable for future operations
            self._file_available = False

    def _read_resources_data(self) -> List[Dict]:
        if not self._resources_file_available:
            return []

        try:
            with open(self._resources_file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []
        except Exception as e:
            logger.warning(
                "Failed to read from composer resources storage file: %s", e
            )
            self._resources_file_available = False
            return []

    def _write_resources_data(self, data: List[Dict]) -> None:
        if not self._resources_file_available:
            return

        try:
            with open(self._resources_file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning(
                "Failed to write to composer resources storage file: %s", e
            )
            self._resources_file_available = False

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
        logger.warning("Server ID (%s) not found in local config.", server_id)
        return {}

    def _update_disabled_tools(
        self, tools: list[str], server_id: str, enable: bool = False
    ) -> None:
        """Common method to update the disabled tools list for a server."""
        data = self._read_data()
        tools = list(set(tools))  # Remove duplicates

        for server in data:
            if server.get("id") != server_id:
                continue

            if enable:
                server["disabled_tools"] = tools
                logger.info(
                    "Updated disabled tool list for server:%s, disabled tools:%s",
                    server_id,
                    server["disabled_tools"],
                )
            else:
                if len(tools) == 1 and tools[0].lower() == "all":
                    existing_tools = []
                else:
                    existing_tools = server.get("disabled_tools", [])

                duplicate_tool = check_duplicate_tool(existing_tools, tools)
                if duplicate_tool:
                    raise ToolDuplicateError(
                        f"Tool {duplicate_tool} is already removed"
                    )

                if existing_tools:
                    server["disabled_tools"].extend(tools)
                    logger.info("Updated remove tool list for server:%s", server_id)
                    logger.info("Previous tools:%s", existing_tools)
                else:
                    server["disabled_tools"] = tools
                    logger.info(
                        "Added new remove tool list: %s for server %s", tools, server_id
                    )

            break
        else:
            if not enable:
                # Create new server entry if not found
                data.append(
                    {
                        "id": server_id,
                        "type": "composer",
                        "disabled_tools": tools,
                    }
                )

        self._write_data(data)

    def disable_tools(self, tools: list[str], server_id: str) -> None:
        """Add or update disabled tools in file for a given member server or composer."""
        self._update_disabled_tools(tools, server_id, enable=False)

    def enable_tools(self, tools: list[str], server_id: str) -> None:
        """Enable tools which are already disabled on the given member server or composer."""
        self._update_disabled_tools(tools, server_id, enable=True)

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

    def _find_resource_index(self, storage_id: str, data: List[Dict]) -> int:
        for idx, record in enumerate(data):
            if record.get("storage_id") == storage_id:
                return idx
        return -1

    def load_all_resources(self) -> List[Dict]:
        return self._read_resources_data()

    def upsert_resource(self, resource: Dict) -> None:
        data = self._read_resources_data()
        idx = self._find_resource_index(resource["storage_id"], data)
        if idx >= 0:
            data[idx] = resource
        else:
            data.append(resource)
        self._write_resources_data(data)

    def delete_resource(self, resource_id: str) -> None:
        data = self._read_resources_data()
        updated = [record for record in data if record.get("storage_id") != resource_id]
        if len(updated) != len(data):
            self._write_resources_data(updated)

    def disable_prompts(self, prompts: list[str], server_id: str) -> None:
        """Add or Update disabled prompts in file for the member server"""
        data = self._read_data()
        prompts = list(set(prompts))

        for server in data:
            if server.get("id") != server_id:
                continue

            existing_prompts = server.get("disabled_prompts", [])
            prompts_description = server.get("prompts_description", {})

            duplicate_prompt = check_duplicate_tool(existing_prompts, prompts)
            if duplicate_prompt:
                raise ToolDuplicateError(
                    f"Prompt {duplicate_prompt} is already disabled"
                )

            # Update disabled_prompts
            if existing_prompts:
                server["disabled_prompts"].extend(prompts)
                logger.info("Updated disabled prompt list for server:%s", server_id)
                logger.info("Previous prompts:%s", existing_prompts)
            else:
                server["disabled_prompts"] = prompts
                logger.info(
                    "Added new disabled prompt list: %s  for server %s",
                    prompts,
                    server_id,
                )

            # Remove prompt descriptions if they exist
            if server["disabled_prompts"] and prompts_description:
                for prompt in server["disabled_prompts"]:
                    prompts_description.pop(prompt, None)

            break

        self._write_data(data)

    def enable_prompts(self, prompts: list[str], server_id: str) -> None:
        """Enable prompts which already disabled"""
        data = self._read_data()
        prompts = list(set(prompts))
        for server in data:
            if server.get("id") != server_id:
                continue

            server["disabled_prompts"] = prompts
            logger.info(
                "Updated disabled prompt list for server:%s, disabled prompts:%s",
                server_id,
                server["disabled_prompts"],
            )

            break
        self._write_data(data)

    def disable_resources(self, resources: list[str], server_id: str) -> None:
        """Add or Update disabled resources in file for the member server"""
        data = self._read_data()
        resources = list(set(resources))

        for server in data:
            if server.get("id") != server_id:
                continue

            existing_resources = server.get("disabled_resources", [])
            resources_description = server.get("resources_description", {})

            duplicate_resource = check_duplicate_tool(existing_resources, resources)
            if duplicate_resource:
                raise ToolDuplicateError(
                    f"Resource {duplicate_resource} is already disabled"
                )

            # Update disabled_resources
            if existing_resources:
                server["disabled_resources"].extend(resources)
                logger.info("Updated disabled resource list for server:%s", server_id)
                logger.info("Previous resources:%s", existing_resources)
            else:
                server["disabled_resources"] = resources
                logger.info(
                    "Added new disabled resource list: %s  for server %s",
                    resources,
                    server_id,
                )

            # Remove resource descriptions if they exist
            if server["disabled_resources"] and resources_description:
                for resource in server["disabled_resources"]:
                    resources_description.pop(resource, None)

            break

        self._write_data(data)

    def enable_resources(self, resources: list[str], server_id: str) -> None:
        """Enable resources which already disabled"""
        data = self._read_data()
        resources = list(set(resources))
        for server in data:
            if server.get("id") != server_id:
                continue

            server["disabled_resources"] = resources
            logger.info(
                "Updated disabled resource list for server:%s, disabled resources:%s",
                server_id,
                server["disabled_resources"],
            )

            break
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
