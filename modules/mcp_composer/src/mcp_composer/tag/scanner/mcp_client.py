from __future__ import annotations
from typing import List, Dict, Any, Optional
import httpx
from ..models import ToolDescriptor
from .base import Scanner


class McpClientScanner(Scanner):
    def __init__(self, endpoint: str, auth_token: Optional[str] = None):
        self.endpoint = endpoint
        self.auth_token = auth_token
        self.headers = {}
        if auth_token:
            self.headers["Authorization"] = f"Bearer {auth_token}"

    def collect(self) -> List[ToolDescriptor]:
        """Collect tools from MCP server using HTTP/SSE transport"""
        try:
            # Try to get tools list from the server
            tools = self._get_tools_list()
            return [self._convert_to_tool_descriptor(tool) for tool in tools]
        except Exception as e:
            raise RuntimeError(
                f"Failed to collect tools from MCP server {self.endpoint}: {e}"
            )

    def _get_tools_list(self) -> List[Dict[str, Any]]:
        """Get tools list from MCP server"""
        # Try different MCP endpoints for tools
        endpoints_to_try = [
            f"{self.endpoint}/tools",
            f"{self.endpoint}/mcp/tools",
            f"{self.endpoint}/api/tools",
            f"{self.endpoint}/tools/list",
        ]

        for endpoint in endpoints_to_try:
            try:
                response = httpx.get(endpoint, headers=self.headers, timeout=10.0)
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list):
                        return data
                    elif isinstance(data, dict) and "tools" in data:
                        return data["tools"]
                    elif isinstance(data, dict) and "data" in data:
                        return data["data"]
            except Exception:
                continue

        # If no standard endpoints work, try to discover tools via MCP protocol
        return self._discover_tools_via_mcp()

    def _discover_tools_via_mcp(self) -> List[Dict[str, Any]]:
        """Discover tools using MCP protocol discovery"""
        try:
            # Try to connect and discover tools using MCP protocol
            # This is a simplified implementation - in practice you might want to use
            # a proper MCP client library
            response = httpx.post(
                f"{self.endpoint}/mcp/discover",
                headers={**self.headers, "Content-Type": "application/json"},
                json={"method": "tools/list"},
                timeout=10.0,
            )

            if response.status_code == 200:
                data = response.json()
                if "result" in data and "tools" in data["result"]:
                    return data["result"]["tools"]

            # Fallback: try to get server info and infer tools
            return self._infer_tools_from_server_info()

        except Exception:
            return self._infer_tools_from_server_info()

    def _infer_tools_from_server_info(self) -> List[Dict[str, Any]]:
        """Infer available tools from server information"""
        try:
            # Try to get server info
            info_endpoints = [
                f"{self.endpoint}/info",
                f"{self.endpoint}/mcp/info",
                f"{self.endpoint}/api/info",
            ]

            for endpoint in info_endpoints:
                try:
                    response = httpx.get(endpoint, headers=self.headers, timeout=5.0)
                    if response.status_code == 200:
                        data = response.json()
                        # Try to extract tool information from server info
                        if "tools" in data:
                            return data["tools"]
                        elif "capabilities" in data:
                            # Convert capabilities to tool-like structure
                            return self._capabilities_to_tools(data["capabilities"])
                except Exception:
                    continue

            # If all else fails, return a basic tool descriptor
            return [
                {
                    "name": "unknown_tool",
                    "description": "Tool discovered from MCP server",
                    "inputSchema": {},
                    "outputSchema": {},
                    "annotations": {"discovery_method": "fallback"},
                }
            ]

        except Exception:
            # Return minimal tool info
            return [
                {
                    "name": "mcp_server_tool",
                    "description": "Tool from MCP server",
                    "inputSchema": {},
                    "outputSchema": {},
                    "annotations": {"discovery_method": "minimal"},
                }
            ]

    def _capabilities_to_tools(
        self, capabilities: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Convert server capabilities to tool-like structure"""
        tools = []
        for cap_name, cap_info in capabilities.items():
            if isinstance(cap_info, dict):
                tools.append(
                    {
                        "name": cap_name,
                        "description": cap_info.get(
                            "description", f"Capability: {cap_name}"
                        ),
                        "inputSchema": cap_info.get("inputSchema", {}),
                        "outputSchema": cap_info.get("outputSchema", {}),
                        "annotations": {
                            "type": "capability",
                            **cap_info.get("annotations", {}),
                        },
                    }
                )
            else:
                tools.append(
                    {
                        "name": cap_name,
                        "description": f"Capability: {cap_name}",
                        "inputSchema": {},
                        "outputSchema": {},
                        "annotations": {"type": "capability"},
                    }
                )
        return tools

    def _convert_to_tool_descriptor(self, tool: dict) -> ToolDescriptor:
        """Convert MCP tool format to ToolDescriptor"""
        return ToolDescriptor(
            id=tool.get("name", tool.get("id", "")),
            name=tool.get("name", ""),
            description=tool.get("description", ""),
            input_schema=tool.get("inputSchema", tool.get("input_schema", {})),
            output_schema=tool.get("outputSchema", tool.get("output_schema", {})),
            annotations=tool.get("annotations", {}),
            vendor=tool.get("vendor"),
            endpoint=self.endpoint,
        )
