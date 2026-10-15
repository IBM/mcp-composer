"""MCP-Composer custom exceptions

This module defines a comprehensive exception hierarchy for the MCP Composer system.
All exceptions inherit from MCPComposerError and include support for error context.

Exception Handling Strategy:
- Use specific exception types for better error handling and debugging
- Include context dictionaries for additional diagnostic information
- Sanitize sensitive data before logging (use security.sanitize_config)
- Re-raise specific exceptions to preserve context
- Wrap unexpected errors in appropriate base exceptions

Example:
    from mcp_composer.core.utils.security import sanitize_config

    try:
        await server_manager.mount_server(config)
    except ServerConfigurationError as e:
        logger.error("Invalid config: %s", e)
        logger.debug("Context: %s", sanitize_config(e.context))
        raise
"""

from typing import Any
from datetime import datetime


class MCPComposerError(Exception):
    """Base error for MCP Composer Server.

    All MCP Composer exceptions inherit from this class and support
    optional context information for better error diagnostics.

    The context dictionary is automatically enhanced with metadata including
    exception type and timestamp for better debugging.

    Args:
        message: Human-readable error message
        context: Optional dictionary with additional error context

    Attributes:
        message: The error message
        context: Dictionary containing error context with metadata
    """

    def __init__(self, message: str, context: dict[str, Any] | None = None):
        self.message = message
        self.context = context or {}

        # Enhance context with metadata
        self.context.setdefault("exception_type", self.__class__.__name__)
        self.context.setdefault("timestamp", datetime.utcnow().isoformat())

        super().__init__(message)

    def __str__(self) -> str:
        if self.context:
            # Filter out metadata for cleaner string representation
            display_context = {k: v for k, v in self.context.items() if k not in ("exception_type", "timestamp")}
            if display_context:
                context_str = ", ".join(f"{k}={v}" for k, v in display_context.items())
                return f"{self.message} ({context_str})"
        return self.message

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(message={self.message!r}, context={self.context!r})"

    def to_dict(self) -> dict[str, Any]:
        """
        Convert exception to structured dictionary for logging.

        Note: This method does NOT automatically sanitize sensitive data.
        Use security.sanitize_config() on the result before logging.

        Returns:
            Dictionary with error details and context
        """
        return {
            "error": self.message,
            "type": self.__class__.__name__,
            "context": self.context,
        }


# ============================================================================
# Server-related Exceptions
# ============================================================================


class ServerError(MCPComposerError):
    """Base exception for server-related errors.

    Use when:
    - Generic server operation failure
    - Wrapping unexpected exceptions
    - No more specific exception type applies

    Example: Server state corruption, unexpected runtime errors
    """


class ServerMountError(ServerError):
    """Raised when a server fails to mount or connect.

    Use when:
    - Network connection failures
    - Timeout during server initialization
    - Server unreachable or not responding
    - Transport-level errors (stdio, SSE, HTTP)

    Example: Connection refused, timeout connecting to remote server
    """


class ServerConfigurationError(ServerError):
    """Raised when server configuration is invalid or incomplete.

    Use when:
    - Invalid server configuration format
    - Missing required configuration fields
    - Configuration type mismatches
    - Schema validation failures
    - Invalid endpoint URLs or paths

    Example: Missing 'id' field, invalid endpoint URL format, wrong type for 'args'
    """


class ServerNotFoundError(ServerError):
    """Raised when a requested server is not found.

    Use when:
    - Attempting to access non-existent server
    - Server ID not found in registry or database
    - Server was deleted or never registered

    Example: Trying to activate server that was never registered
    """


class ServerAlreadyExistsError(ServerError):
    """Raised when attempting to register a server that already exists.

    Use when:
    - Duplicate server ID in registration
    - Server already mounted with same ID

    Example: Registering server with ID that's already in use
    """


class ServerBuildError(ServerError):
    """Raised when server building/initialization fails.

    Use when:
    - Server factory creation fails
    - Tool registration fails during build
    - Resource initialization fails
    - MCP client creation fails

    Example: Failed to create MCP client, tool schema invalid during build
    """


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
