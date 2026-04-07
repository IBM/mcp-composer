"""MCP-Composer custom exceptions

This module defines a comprehensive exception hierarchy for the MCP Composer system.
All exceptions inherit from MCPComposerError and include support for error context.

Example:
    try:
        await server_manager.mount_server(config)
    except ServerConfigurationError as e:
        logger.error("Invalid config: %s", e)
        logger.debug("Context: %s", e.context)
        raise
"""

from typing import Any, Dict, Optional


class MCPComposerError(Exception):
    """Base error for MCP Composer Server.
    
    All MCP Composer exceptions inherit from this class and support
    optional context information for better error diagnostics.
    
    Args:
        message: Human-readable error message
        context: Optional dictionary with additional error context
    
    Attributes:
        message: The error message
        context: Dictionary containing error context (empty if not provided)
    """
    
    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        self.message = message
        self.context = context or {}
        super().__init__(message)
    
    def __str__(self) -> str:
        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            return f"{self.message} ({context_str})"
        return self.message
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(message={self.message!r}, context={self.context!r})"


# ============================================================================
# Server-related Exceptions
# ============================================================================

class ServerError(MCPComposerError):
    """Base exception for server-related errors."""


class ServerMountError(ServerError):
    """Raised when a server fails to mount."""


class ServerConfigurationError(ServerError):
    """Raised when server configuration is invalid or incomplete."""


class ServerNotFoundError(ServerError):
    """Raised when a requested server is not found."""


class ServerAlreadyExistsError(ServerError):
    """Raised when attempting to register a server that already exists."""


class ServerBuildError(ServerError):
    """Raised when server building/initialization fails."""


# ============================================================================
# Tool-related Exceptions
# ============================================================================

class ToolError(MCPComposerError):
    """Base exception for tool-related errors."""


class ToolRegistrationError(ToolError):
    """Raised when tool registration fails."""


class ToolNotFoundError(ToolError):
    """Raised when a requested tool is not found."""


class ToolExecutionError(ToolError):
    """Raised when tool execution fails."""


class ToolValidationError(ToolError):
    """Raised when tool validation fails."""


class ToolDuplicateError(ToolError):
    """Raised when attempting to register a duplicate tool."""


class ToolFilterError(ToolError):
    """Raised when tool filtering fails."""


class ToolGenerateError(ToolError):
    """Raised when tool generation fails."""


class ToolDisableError(ToolError):
    """Raised when tool disable/enable operation fails."""


# ============================================================================
# Database-related Exceptions
# ============================================================================

class DatabaseError(MCPComposerError):
    """Base exception for database-related errors."""


class DatabaseConnectionError(DatabaseError):
    """Raised when database connection fails."""


class DatabaseOperationError(DatabaseError):
    """Raised when a database operation fails."""


class DatabaseNotAvailableError(DatabaseError):
    """Raised when database is not available or not configured."""


# ============================================================================
# Authentication-related Exceptions
# ============================================================================

class AuthenticationError(MCPComposerError):
    """Base exception for authentication-related errors."""


class TokenExpiredError(AuthenticationError):
    """Raised when an authentication token has expired."""


class InvalidCredentialsError(AuthenticationError):
    """Raised when provided credentials are invalid."""


class AuthorizationError(AuthenticationError):
    """Raised when user lacks required permissions."""


# ============================================================================
# Validation-related Exceptions
# ============================================================================

class ValidationError(MCPComposerError):
    """Base exception for validation errors."""


class ConfigValidationError(ValidationError):
    """Raised when configuration validation fails."""


class InputValidationError(ValidationError):
    """Raised when input validation fails."""


# ============================================================================
# Middleware-related Exceptions
# ============================================================================

class MiddlewareError(MCPComposerError):
    """Base exception for middleware-related errors."""


class MiddlewareExecutionError(MiddlewareError):
    """Raised when middleware execution fails."""


class MiddlewareConfigurationError(MiddlewareError):
    """Raised when middleware configuration is invalid."""


# ============================================================================
# Legacy Exceptions (maintained for backward compatibility)
# ============================================================================

class MemberServerError(ServerError):
    """Error in Member Server.
    
    Note: This is maintained for backward compatibility.
    New code should use more specific ServerError subclasses.
    """

# Made with Bob
