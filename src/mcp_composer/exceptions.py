class MCPComposerError(Exception):
    """Base error for MCP Composer Server."""


class ToolDuplicateError(MCPComposerError):
    """Tool duplicate error"""
