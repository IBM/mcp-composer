from typing import Dict, List, Any
from fastmcp import FastMCP
from fastmcp.settings import DuplicateBehavior
from mcp_gateway.utils import LoggerFactory
from collections.abc import Callable
from mcp_gateway.member_servers.member_server import MemberMCPServer

import os
from ibmcloudant import CloudantV1
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
from ibmcloudant.cloudant_v1 import Document

logger = LoggerFactory.get_logger()


class ServerManager:
    """
    Manages registration and lifecycle of mounted MCP servers,
    with optional serialization for monitoring, or persistence.
    """

    _db_name: str = "mcp_servers"
    _cloudant_client: CloudantV1 | None = None

    def __init__(
        self,
        duplicate_behavior: DuplicateBehavior | None = None,
        serializer: Callable[[str, MemberMCPServer], Any] | None = None,
    ):
        self._member_servers: dict[str, MemberMCPServer] = {}
        # Fix here: explicitly declare non-optional type
        self._serializer: Callable[[str, MemberMCPServer], Any] = serializer or self.default_serializer

        if duplicate_behavior is None:
            duplicate_behavior = "warn"

        if duplicate_behavior not in DuplicateBehavior.__args__:
            raise ValueError(
                f"Invalid duplicate_behavior: {duplicate_behavior}. "
                f"Must be one of: {', '.join(DuplicateBehavior.__args__)}"
            )

        self.duplicate_behavior = duplicate_behavior

    def has_member_server(self, key: str) -> bool:
        """Check if a memeber server exists."""
        return key in self._member_servers

    def add_member(self, server_id: str, server: MemberMCPServer):
        if server_id in self._member_servers:
            logger.warning(f"Overwriting existing MCP server: {server_id}")
        self._member_servers[server_id] = server
        logger.info(f"Mounted MCP server: {server_id}")

    def remove_member(self, server_id: str):
        if server_id not in self._member_servers:
            logger.warning(f"MCP server '{server_id}' not found.")
            return
        del self._member_servers[server_id]
        logger.info(f"Unmounted MCP server: {server_id}")

    def get(self, server_id: str) -> MemberMCPServer:
        if server_id not in self._member_servers:
            raise KeyError(f"MCP server '{server_id}' not found.")
        return self._member_servers[server_id]

    def list(self) -> list[MemberMCPServer]:
        return list(self._member_servers.values())

    def list_serialized(self) -> Dict[str, Any]:
        return {
            server_id: self._serializer(server_id, member)
            for server_id, member in self._member_servers.items()
        }

    @staticmethod
    def default_serializer(server_id: str, member: MemberMCPServer):
        return member.to_dict()

    @classmethod
    def _cloudant(cls) -> CloudantV1:
        if cls._cloudant_client is None:
            authenticator = IAMAuthenticator(os.environ.get("CLOUDANT_API_KEY"))
            client = CloudantV1(authenticator=authenticator)
            client.set_service_url(os.environ.get("CLOUDANT_URL"))

            if cls._db_name not in client.get_all_dbs().get_result():
                client.put_database(cls._db_name)
            cls._cloudant_client = client

        return cls._cloudant_client

    def add_server_db(self, config: dict) -> None:
        client = self._cloudant()
        doc_id = config["id"]
        try:
            existing = client.get_document(db=self._db_name, doc_id=doc_id).get_result()
            config["_rev"] = existing["_rev"]
        except Exception:
            pass
        client.post_document(db=self._db_name, document=Document(**config)).get_result()
        logger.info("Saved server '%s' to Cloudant", doc_id)

    def load_all_servers_db(self) -> List[dict]:
        client = self._cloudant()
        try:
            result = client.post_all_docs(db=self._db_name, include_docs=True).get_result()
            return [row["doc"] for row in result.get("rows", []) if "doc" in row]
        except Exception as exc:
            logger.error("Cloudant read failed: %s", exc)
            return []
