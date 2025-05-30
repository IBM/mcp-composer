class MCPGatewayError(Exception):
    """Base error for MCP Gateway Server."""


class ToolError(MCPGatewayError):
    """Error in tool operations."""
