class MCPGatewayError(Exception):
    """Base error for MCP Gateway Server."""


class ToolDuplicateError(MCPGatewayError):
    """Tool duplicate error"""
