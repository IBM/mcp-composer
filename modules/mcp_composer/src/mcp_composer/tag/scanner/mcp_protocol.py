from __future__ import annotations
import asyncio
import json
import shlex
from typing import List, Dict, Any, Optional, Tuple
import httpx
from fastmcp.client import Client
from fastmcp.client.transports import (
    StreamableHttpTransport,
    SSETransport,
    StdioTransport,
)
from mcp.types import ToolAnnotations
from mcp import ClientSession, Tool

from mcp_composer.core.utils.logger import LoggerFactory
from ..models import ToolDescriptor
from .base import Scanner

# Initialize logger
logger = LoggerFactory.get_logger()


class MCPTransportMessage:
    INIT_MESSAGE = {
        "jsonrpc": "2.0",
        "id": 101,  # Unique ID
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "clientInfo": {"name": "mcp-tag", "version": "0.0.1"},
            "capabilities": {
                "sampling": {},
                "elicitation": {},
                "roots": {"listChanged": True},
            },
        },
    }
    INIT_NOTIFICATION = {"jsonrpc": "2.0", "method": "notifications/initialized"}
    TOOLS_LIST_MESSAGE = {
        "jsonrpc": "2.0",
        "id": 1,  # Unique ID
        "method": "tools/list",
        "params": {"_meta": {"progressToken": 1}},
    }


class McpProtocolScanner(Scanner):
    """
    MCP Protocol Scanner that implements the Model Context Protocol
    for discovering and extracting tools from MCP servers.
    """

    LEVEL_MAP = {
        "CRITICAL": "🔴 CRITICAL",
        "HIGH": "⚠️ HIGH",
        "MEDIUM": "🟡 MEDIUM",
        "LOW": "🟢 LOW",
    }

    # Keywords indicating system modification or potential harm
    DESTRUCTIVE_KEYWORDS = [
        "delete",
        "remove",
        "destroy",
        "shutdown",
        "terminate",
        "unregister",
        "modify system",
        "send money",
        "register",
        "write file",
        "save file",
        "update database",
        "sql execute",
        "drop table",
        "delete row",
        "mkdir",
        "rmdir",  # Added file/DB write/delete ops
    ]
    MSG_DESTRUCTIVE = "System/DB Write or Irreversible Operation"

    # Keywords indicating access to sensitive data
    PRIVATE_DATA_KEYWORDS = [
        "read file",
        "get secrets",
        "fetch data",
        "read config",
        "access private",
        "get user data",
        "credentials",
        "get_",
        "open file",
        "select from",
        "query database",
        "private logs",
        "db access",  # Added file/DB read ops
    ]
    MSG_PRIVATE_DATA = "File/DB Read or Secret Access Operation"

    # Keywords indicating external data transmission
    PUBLIC_SINK_KEYWORDS = [
        "send",
        "upload",
        "post",
        "register",
        "submit",
        "exfiltrate",
        "log external",
        "post_",
        "transmit data",
        "external" "http request",  # General external transmission
    ]
    MSG_PUBLIC_SINK = "External Data Transmission or Registration"

    def __init__(
        self,
        endpoint: str,
        auth_token: Optional[str] = None,
        transport: str = "http",
        command: Optional[str] = None,
        args: Optional[str] = None,
    ):
        self.endpoint = endpoint
        self.auth_token = auth_token
        self.transport = transport.lower()
        self.command = command
        self.args = args
        self.session: ClientSession | None = None
        self.headers = {
            "Content-Type": "application/json",
            "accept": "application/json, text/event-stream",
        }
        self.server_info = {}
        self.tool_list = []
        if auth_token:
            self.headers["Authorization"] = f"Bearer {auth_token}"

    def collect(
        self,
    ) -> List:
        """
        Collect tools from MCP server using the MCP protocol.

        Parameters:
            None

        Returns:
            List:
                A list containing ToolDescriptor
                representing the discovered items from the MCP server.
        """
        try:
            if self.transport == "http":
                self.endpoint = f"{self.endpoint}/mcp"
            elif self.transport == "sse":
                self.endpoint = f"{self.endpoint}/sse"
            elif self.transport == "stdio":
                pass
            else:
                raise ValueError(f"Unsupported transport: {self.transport}")

            self.client = self._create_mcp_client()
            return asyncio.run(self._collect_all())

        except Exception as e:
            logger.error(
                "Failed to collect tools from MCP server %s: %s", self.endpoint, str(e)
            )
            raise RuntimeError(
                f"Failed to collect tools from MCP server {self.endpoint}: {e}"
            )

    def _create_mcp_client(self) -> Client:
        """Create a fastmcp client for the given URL and transport."""
        try:
            logger.info(
                f"Creating MCP client for {self.endpoint} using transport {self.transport}"
            )
            if self.transport == "http":
                transport_obj = StreamableHttpTransport(
                    self.endpoint, headers=self.headers
                )
            elif self.transport == "sse":
                transport_obj = SSETransport(self.endpoint, headers=self.headers)
            elif self.transport == "stdio":

                parts = self.command.split() if self.command else []
                if not parts:
                    print("Error: No command provided for stdio transport.")
                    raise ValueError("Error: No command provided for stdio transport.")
                cmd = parts[0]
                args = shlex.split(self.args) if self.args else []
                print(f"Executing command: {cmd} {' '.join(args)}")
                transport_obj = StdioTransport(command=cmd, args=args)
            else:
                raise ValueError(f"Unsupported transport: {self.transport}")

            return Client(transport_obj)
        except Exception as e:
            logger.error("Failed to create MCP client: %s", str(e))
            raise RuntimeError(f"Failed to create MCP client: {e}")

    def _classify_tool(self, tool: Tool) -> Dict[str, Tuple[bool, str]]:
        """Classifies a tool into potential Toxic Flow component roles."""

        name = (getattr(tool, "name", None) or "").lower()
        description = (getattr(tool, "description", None) or "").lower()

        # Check against heuristics
        is_destructive = any(
            kw in description for kw in self.DESTRUCTIVE_KEYWORDS
        ) or any(
            name.startswith(kw)
            for kw in ["delete_", "remove_", "shutdown_", "terminate_"]
        )
        is_private_data = any(
            kw in description for kw in self.PRIVATE_DATA_KEYWORDS
        ) or any(name.startswith(kw) for kw in ["get_", "read_", "fetch_"])
        is_public_sink = any(
            kw in description for kw in self.PUBLIC_SINK_KEYWORDS
        ) or any(
            name.startswith(kw) for kw in ["send_", "upload_", "post_", "register_"]
        )

        return {
            "Destructive": (is_destructive, self.MSG_DESTRUCTIVE),
            "Private Data": (is_private_data, self.MSG_PRIVATE_DATA),
            "Public Sink": (is_public_sink, self.MSG_PUBLIC_SINK),
        }

    def _determine_risk_level(self, classification: Dict[str, Tuple[bool, str]]) -> str:
        """Determines the overall risk level and returns it along with its ANSI color code."""

        is_destructive, _ = classification["Destructive"]
        is_private_data, _ = classification["Private Data"]
        is_public_sink, _ = classification["Public Sink"]

        risk_key = "LOW"

        if is_destructive or (is_private_data and is_public_sink):
            # Immediate destructive capability or full data leak (Source + Sink)
            risk_key = "CRITICAL"
        elif is_private_data and is_public_sink:
            # Reverting to HIGH for single-component risk if CRITICAL is not met
            risk_key = "HIGH"
        elif is_private_data or is_public_sink:
            # Component is necessary for a flow, but not sufficient alone
            risk_key = "MEDIUM"
        else:
            risk_key = "LOW"

        return self.LEVEL_MAP[risk_key]

    def _scan_tool(self, tool: Tool) -> Dict[str, str]:
        """Scan a single tool and return scan report."""
        # The result of classification is Dict[str, Tuple[bool, str]]
        classification = self._classify_tool(tool)
        # Calculate the risk level and color
        risk_level = self._determine_risk_level(classification)

        # Build the final output dictionary
        report_output = {}

        # 1. Add the Risk Level
        report_output["Level"] = risk_level

        # 2. Add the Component Classifications
        for role, (is_match, message) in classification.items():
            status_emoji = "✅ YES" if is_match else "❌ NO"
            report_output[role] = f"{status_emoji} ({message})"

        return report_output

    def _extract_tools_from_response(self, data: Any) -> List[Tool]:
        """Extract tools from various response formats"""
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            if "tools" in data:
                return data["tools"]
            elif "data" in data and isinstance(data["data"], list):
                return data["data"]
            elif "result" in data and isinstance(data["result"], list):
                return data["result"]
            elif (
                "result" in data
                and isinstance(data["result"], dict)
                and "tools" in data["result"]
            ):
                return data["result"]["tools"]

        return []

    def _convert_to_tool_descriptor(
        self, tool: Tool, server_info: Dict[str, Any]
    ) -> ToolDescriptor:
        """Convert MCP tool format to ToolDescriptor"""

        # Extract vendor information from server info
        vendor = getattr(tool, "vendor", None) or server_info.get("name") or "unknown"

        # Handle different tool ID formats
        tool_id = (
            getattr(tool, "id", None) or getattr(tool, "name", None) or "unknown_tool"
        )

        # Extract input/output schemas
        input_schema = (
            getattr(tool, "inputSchema", None)
            or getattr(tool, "input_schema", None)
            or getattr(tool, "schema", {})
        )
        output_schema = (
            getattr(tool, "outputSchema", None)
            or getattr(tool, "output_schema", None)
            or getattr(tool, "resultSchema", {})
        )

        # Build annotations
        annotations = getattr(tool, "annotations", {})
        if annotations and isinstance(annotations, dict):
            annotations.update(
                {
                    "mcp_protocol": True,
                    "server_name": server_info.get("name", "unknown"),
                    "server_version": server_info.get("version", "unknown"),
                    "transport": self.transport,
                }
            )
        elif annotations and isinstance(annotations, ToolAnnotations):
            annotations_dict = annotations.__dict__
            annotations_dict.update(
                {
                    "mcp_protocol": True,
                    "server_name": server_info.get("name", "unknown"),
                    "server_version": server_info.get("version", "unknown"),
                    "transport": self.transport,
                }
            )
            annotations = annotations_dict
        else:
            annotations = {
                "mcp_protocol": True,
                "server_name": server_info.get("name", "unknown"),
                "server_version": server_info.get("version", "unknown"),
                "transport": self.transport,
            }

        return ToolDescriptor(
            id=tool_id,
            name=getattr(tool, "name", tool_id),
            description=getattr(tool, "description", ""),
            input_schema=input_schema,
            output_schema=output_schema,
            annotations=annotations,
            vendor=vendor,
            endpoint=self.endpoint,
            scan_report=self._scan_tool(tool),
        )

    async def _get_server_info(self) -> Dict[str, Any]:
        """Get server info using POST method (MCP protocol style, async)."""
        post_endpoints = [
            f"{self.endpoint}/sse",
            f"{self.endpoint}/mcp",
            f"{self.endpoint}/api/sse",
            f"{self.endpoint}/api/mcp",
        ]

        async with httpx.AsyncClient(timeout=10.0) as client:
            for endpoint in post_endpoints:
                try:
                    async with client.stream(
                        "POST",
                        endpoint,
                        headers=self.headers,
                        json=MCPTransportMessage.INIT_MESSAGE,
                    ) as response:

                        if (
                            not response.is_success
                            or "text/event-stream"
                            not in response.headers.get("Content-Type", "")
                        ):
                            continue

                        session_id = response.headers.get("mcp-session-id")
                        if session_id:
                            self.headers["mcp-session-id"] = session_id

                        async for line in response.aiter_lines():
                            if line and line.startswith("data:"):
                                response_data = line.split("data:", 1)[1].strip()
                                data = json.loads(response_data)
                                if "result" in data and "serverInfo" in data["result"]:
                                    print(
                                        "Received server info via POST", response_data
                                    )
                                    return data["result"]["serverInfo"]
                                break

                except Exception:
                    continue

        # Default fallback
        return {"name": "mcp-server", "version": "1.0.0", "capabilities": {}}

    async def _get_tools_list(self) -> List[Tool]:
        """Get tools list using the established MCP session"""
        try:
            tools_result = await self.client.list_tools()
            return self._extract_tools_from_response(tools_result)
        except Exception:
            print("Error fetching tools via MCP session")
        return []

    async def _collect_all(
        self,
    ) -> List[ToolDescriptor]:
        try:
            async with self.client:
                logger.info(
                    f"Connected to MCP server at {self.endpoint} using {self.transport}"
                )
                self.server_info = await self._get_server_info()
                tools = await self._get_tools_list()

                logger.info(f"Server Info: {self.server_info}")
                logger.info(f"Collecting tools via {self.transport} transport...")
                logger.info(
                    f"Discovered {len(tools)} tools from MCP server {self.endpoint}"
                )
                return [
                    self._convert_to_tool_descriptor(tool, self.server_info)
                    for tool in tools
                ]
        except Exception as e:
            logger.error(
                "Error during MCP protocol collection from %s: %s",
                self.endpoint,
                str(e),
            )
            raise RuntimeError(
                f"Error during MCP protocol collection from {self.endpoint}: {e}"
            )
