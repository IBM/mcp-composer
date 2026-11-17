"""Local File adapter"""

import os
import json
from pathlib import Path
from dotenv import load_dotenv, find_dotenv

from mcp_composer.core.utils.logger import LoggerFactory
from mcp_composer.core.utils.exceptions import ToolDuplicateError
from mcp_composer.core.utils.tools import check_duplicate_tool
from .database import DatabaseInterface
from mcp_composer.core.utils import LoggerFactory
from .base_adapter import BaseDatabaseAdapter

load_dotenv(find_dotenv(".env"))

logger = LoggerFactory.get_logger()


class LocalFileAdapter(BaseDatabaseAdapter):
    """Local file storage"""

    def __init__(
        self,
        file_path: str | None = None,
        resources_file_path: str | None = None,
        prompts_file_path: str | None = None,
    ):
        if file_path is None:
            file_path = os.getenv("SERVER_CONFIG_FILE_PATH", "member_servers.json")
        self._file_path = Path(file_path)
        if resources_file_path is None:
            resources_file_path = os.getenv(
                "RESOURCE_CONFIG_FILE_PATH", "composer_resources.json"
            )
        self._resources_file_path = Path(resources_file_path)
        if prompts_file_path is None:
            prompts_file_path = os.getenv(
                "PROMPTS_CONFIG_FILE_PATH", "composer_prompts.json"
            )
        self._prompts_file_path = Path(prompts_file_path)
        logger.info(
            "Using local file storage for configuration storage: %s", self._file_path
        )

        # Initialize file availability flag to False (pessimistic approach)
        self._file_available = False
        self._resources_file_available = False
        self._prompts_file_available = False

        self._ensure_file_exists()
        self._ensure_resources_file_exists()
        self._ensure_prompts_file_exists()

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

    def _ensure_prompts_file_exists(self) -> None:
        """Ensure the prompts file exists, create it if it doesn't."""
        if not self._prompts_file_path.exists():
            try:
                logger.info("Creating composer prompts storage file")
                self._prompts_file_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self._prompts_file_path, "w", encoding="utf-8") as f:
                    json.dump([], f)
                logger.info("Successfully created composer prompts storage file")
            except Exception as e:
                logger.warning(
                    "Failed to create composer prompts storage file: %s. Continuing without file persistence.",
                    e,
                )
                self._prompts_file_available = False
            else:
                self._prompts_file_available = True
        else:
            self._prompts_file_available = True

    def _read_data(self) -> list[dict[str, object]]:
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

    def _write_data(self, data: list[dict[str, object]]) -> None:
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

    def _read_resources_data(self) -> list[dict[str, object]]:
        if not self._resources_file_available:
            return []

        try:
            with open(self._resources_file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []
        except Exception as e:
            logger.warning("Failed to read from composer resources storage file: %s", e)
            self._resources_file_available = False
            return []

    def _write_resources_data(self, data: list[dict[str, object]]) -> None:
        if not self._resources_file_available:
            return

        try:
            with open(self._resources_file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning("Failed to write to composer resources storage file: %s", e)
            self._resources_file_available = False

    def _read_prompts_data(self) -> list[dict[str, object]]:
        """Read prompts data from file"""
        if not self._prompts_file_available:
            return []

        try:
            with open(self._prompts_file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []
        except Exception as e:
            logger.warning("Failed to read from composer prompts storage file: %s", e)
            self._prompts_file_available = False
            return []

    def _write_prompts_data(self, data: list[dict[str, object]]) -> None:
        """Write prompts data to file"""
        if not self._prompts_file_available:
            return

        try:
            with open(self._prompts_file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning("Failed to write to composer prompts storage file: %s", e)
            self._prompts_file_available = False

    def load_all_servers(self) -> list[dict[str, object]]:
        """Fetch all member server from file storage"""
        return self._read_data()

    def add_server(self, config: dict[str, object]) -> None:
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

    def get_document(self, server_id: str) -> dict[str, object]:
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

        for server in data:
            if server.get("id") != server_id:
                continue

            self._apply_disabled_tools(server, tools, enable)
            logger.info(
                "Updated disabled tool list for server:%s, disabled tools:%s",
                server_id,
                server.get("disabled_tools"),
            )
            break
        else:
            if not enable:
                data.append(
                    self._new_composer_server_stub(server_id, disabled_tools=tools)
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
                self._apply_tool_description(server, tool, description)
                logger.info("Tool description updated for server: %s", server_id)

        self._write_data(data)

    def _find_resource_index(
        self, storage_id: str, data: list[dict[str, object]]
    ) -> int:
        for idx, record in enumerate(data):
            if record.get("storage_id") == storage_id:
                return idx
        return -1

    def load_all_resources(self) -> list[dict[str, object]]:
        return self._read_resources_data()

    def upsert_resource(self, resource: dict[str, object]) -> None:
        data = self._read_resources_data()
        storage_id = str(resource["storage_id"])
        idx = self._find_resource_index(storage_id, data)
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
        for server in data:
            if server.get("id") != server_id:
                continue

            self._apply_disabled_named_items(
                server,
                "disabled_prompts",
                "prompts_description",
                prompts,
                "Prompt",
            )
            logger.info("Updated disabled prompt list for server:%s", server_id)
            break

        self._write_data(data)

    def enable_prompts(self, prompts: list[str], server_id: str) -> None:
        """Enable prompts which already disabled"""
        data = self._read_data()
        for server in data:
            if server.get("id") != server_id:
                continue

            self._apply_enabled_named_items(server, "disabled_prompts", prompts)
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
        for server in data:
            if server.get("id") != server_id:
                continue

            self._apply_disabled_named_items(
                server,
                "disabled_resources",
                "resources_description",
                resources,
                "Resource",
            )
            logger.info("Updated disabled resource list for server:%s", server_id)
            break

        self._write_data(data)

    def enable_resources(self, resources: list[str], server_id: str) -> None:
        """Enable resources which already disabled"""
        data = self._read_data()
        for server in data:
            if server.get("id") != server_id:
                continue

            self._apply_enabled_named_items(server, "disabled_resources", resources)
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
                status = server.get("status", "active")
                return str(status)
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

    def load_all_prompts(self) -> list[dict[str, object]]:
        """Load all prompts from storage"""
        return self._read_prompts_data()

    def add_prompt(self, prompt: dict[str, object]) -> None:
        """Add or update a prompt in storage"""
        data = self._read_prompts_data()
        prompt_name = prompt.get("name")

        if not prompt_name:
            logger.warning("Prompt missing 'name' field, skipping storage")
            return

        # Check if prompt already exists and update it
        updated = False
        for i, existing_prompt in enumerate(data):
            if existing_prompt.get("name") == prompt_name:
                data[i] = prompt
                updated = True
                logger.info("Updated prompt '%s' in local file", prompt_name)
                break

        if not updated:
            data.append(prompt)
            logger.info("Added new prompt '%s' to local file", prompt_name)

        self._write_prompts_data(data)

    def remove_prompt(self, prompt_name: str) -> None:
        """Remove a prompt from storage"""
        data = self._read_prompts_data()
        updated_data = [p for p in data if p.get("name") != prompt_name]

        if len(updated_data) < len(data):
            self._write_prompts_data(updated_data)
            logger.info("Deleted prompt '%s' from local file", prompt_name)
        else:
            logger.info("Prompt '%s' not found in local file", prompt_name)

    def get_prompt(self, prompt_name: str) -> dict[str, object]:
        """Get a specific prompt from storage"""
        data = self._read_prompts_data()
        for prompt in data:
            if prompt.get("name") == prompt_name:
                logger.info("Retrieved prompt '%s' from local file", prompt_name)
                return prompt
        logger.warning("Prompt '%s' not found in local file", prompt_name)
        return {}
