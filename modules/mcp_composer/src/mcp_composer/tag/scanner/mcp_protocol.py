from __future__ import annotations
import asyncio
import json
import shlex
from typing import List, Dict, Any, Optional
import httpx
from mcp.client.streamable_http import streamablehttp_client
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client
from mcp.types import ToolAnnotations
from mcp import ClientSession, StdioServerParameters, Tool

from ..models import ToolDescriptor
from .base import Scanner


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

    def collect(self) -> List[ToolDescriptor]:
        """
        Collect tools from MCP server using the MCP protocol.

        Parameters:
            None

        Returns:
            List[ToolDescriptor]: A list of ToolDescriptor objects representing the discovered tools.
        """
        try:
            if self.transport == "http":
                self.endpoint = f"{self.endpoint}/mcp"
                return asyncio.run(self._connect_streamable_http())
            elif self.transport == "sse":
                self.endpoint = f"{self.endpoint}/sse"
                return asyncio.run(self._connect_sse())
            elif self.transport == "stdio":
                return asyncio.run(self._connect_stdio())
            else:
                raise ValueError(f"Unsupported transport: {self.transport}")
        except Exception as e:
            raise RuntimeError(
                f"Failed to collect tools from MCP server {self.endpoint}: {e}"
            )

    async def _connect_streamable_http(self) -> List[ToolDescriptor]:
        """Connect using streamable HTTP transport."""
        try:
            async with streamablehttp_client(self.endpoint) as (
                read_stream,
                write_stream,
                get_session_id,
            ):
                return await self._run_session(read_stream, write_stream)
        except Exception:
            # Fallback to basic discovery
            return self._fallback_discovery()

    async def _connect_sse(self) -> List[ToolDescriptor]:
        """Connect using SSE transport."""
        try:
            async with sse_client(url=self.endpoint, headers=self.headers) as (
                read_stream,
                write_stream,
            ):
                return await self._run_session(read_stream, write_stream)
        except Exception:
            # Fallback to basic discovery
            return self._fallback_discovery()

    async def _connect_stdio(self) -> List[ToolDescriptor]:
        """Connect using stdio transport."""
        print("Collecting tools via stdio transport...")

        parts = self.command.split() if self.command else []
        if not parts:
            print("Error: No command provided for stdio transport.")
            return []
        cmd = parts[0]
        args = shlex.split(self.args) if self.args else []
        print(f"Executing command: {cmd} {' '.join(args)}")

        server_params = StdioServerParameters(command=cmd, args=args)

        try:
            async with stdio_client(server_params) as (read_stream, write_stream):
                return await self._run_session(read_stream, write_stream)
        except Exception as e:
            print(f"An error occurred during stdio communication: {e}")
            return []

    def _get_server_info(self) -> Dict[str, Any]:
        """Get MCP server information"""
        info_endpoints = [
            f"{self.endpoint}/info",
            f"{self.endpoint}/info",
            f"{self.endpoint}/api/info",
        ]

        for endpoint in info_endpoints:
            try:
                response = httpx.get(endpoint, headers=self.headers, timeout=10.0)
                if response.status_code == 200:
                    return response.json()
            except Exception:
                continue

        # Get server info via POST or GET method
        return self._get_server_info_via_transport()

    def _get_server_info_via_transport(self) -> Dict[str, Any]:
        """Get server info using POST method (MCP protocol style)."""
        post_endpoints = [
            f"{self.endpoint}/sse",
            f"{self.endpoint}/mcp",
            f"{self.endpoint}/api/sse",
            f"{self.endpoint}/api/mcp",
        ]

        for endpoint in post_endpoints:
            try:
                with httpx.stream(
                    "POST",
                    endpoint,
                    headers=self.headers,
                    json=MCPTransportMessage.INIT_MESSAGE,
                    timeout=10.0,
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

                    for line in response.iter_lines():
                        if line and line.startswith("data:"):
                            response_data = line.split("data:", 1)[1].strip()
                            data = json.loads(response_data)
                            if "result" in data and "serverInfo" in data["result"]:
                                print("Received server info via POST", response_data)
                                return data["result"]["serverInfo"]
                            break

            except Exception:
                continue
        # Return default server info if none found
        return {"name": "mcp-server", "version": "1.0.0", "capabilities": {}}

    async def _run_session(self, read_stream, write_stream):
        """Run analysis session."""
        server_info = self._get_server_info()
        async with ClientSession(read_stream, write_stream) as session:
            self.session = session

            print("Initializing MCP session...")
            await session.initialize()
            print("Connected to MCP server")

            # Then get tools list
            tools = await self._get_tools_list()
            print(f"Discovered {len(tools)} tools from {self.endpoint}")

            # Convert to ToolDescriptor objects
            return [
                self._convert_to_tool_descriptor(tool, server_info) for tool in tools
            ]

    async def _get_tools_list(self) -> List[Tool]:
        """Get tools list using MCP protocol"""
        # Try different MCP protocol endpoints
        mcp_endpoints = [f"{self.endpoint}/tools/list", f"{self.endpoint}/tools"]
        for endpoint in mcp_endpoints:
            try:
                response = httpx.get(endpoint, headers=self.headers, timeout=10.0)
                if response.status_code == 200:
                    data = response.json()
                    return self._extract_tools_from_response(data)
            except Exception:
                continue

        # Fetch list of tools
        return await self._get_tools_via_session()

    async def _get_tools_via_session(self) -> List[Tool]:
        """Get tools list using the established MCP session"""
        try:
            if not self.session:
                print("No active MCP session available.")
                return []
            result = await self.session.list_tools()
            if not hasattr(result, "tools") or not result.tools:
                print("No tools available")
                return []

            return self._extract_tools_from_response(result.tools)
        except Exception:
            print("Error fetching tools via MCP session")

        return []

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
        )

    def _fallback_discovery(self) -> List[ToolDescriptor]:
        """Fallback discovery when MCP protocol fails"""
        return [
            ToolDescriptor(
                id="discovered_tool",
                name="Discovered Tool",
                description="Tool discovered from MCP server (fallback method)",
                input_schema={},
                output_schema={},
                annotations={
                    "discovery_method": "fallback",
                    "transport": self.transport,
                    "endpoint": self.endpoint,
                },
                endpoint=self.endpoint,
            )
        ]
