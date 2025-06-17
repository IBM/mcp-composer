class MCPComposerError(Exception):
    """Base error for MCP Composer Server."""


class ToolDuplicateError(MCPComposerError):
    """Tool duplicate error"""


class ToolRemoveError(MCPComposerError):
    """Tool Remove error"""


class MemberServerError(MCPComposerError):
    """Error in Member Server"""
