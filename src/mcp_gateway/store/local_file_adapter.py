import json
from pathlib import Path
from typing import List, Dict
from mcp_gateway.utils import LoggerFactory
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
        data = self._read_data()
        server_cfg = {}
        for server_cfg in data:
            if server_cfg["id"] == server_id:
                return server_cfg

    def add_remove_tools(self, tools: list[str], server_id: str) -> None:
        data = self._read_data()

        for server in data:
            if server.get("id") == server_id:
                if server.get("remove_tools"):
                    server["remove_tools"].extend(tools)
                    server["remove_tools"] = list(set(server["remove_tools"]))
                else:
                    server["remove_tools"] = list(set(tools))

        self._write_data(data)
        logger.info("Saved server '%s' to local file", server_id)
