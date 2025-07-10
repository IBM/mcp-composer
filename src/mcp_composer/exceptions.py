"""MCP-Composer custom exceptions"""


class MCPComposerError(Exception):
    """Base error for MCP Composer Server."""


class ToolDuplicateError(MCPComposerError):
    """Tool duplicate error"""


class ToolFilterError(MCPComposerError):
    """Tool filter error"""


class ToolGenerateError(MCPComposerError):
    """Tool Generate error"""


class ToolDisableError(MCPComposerError):
    """Tool Remove error"""


class MemberServerError(MCPComposerError):
    """Error in Member Server"""
