"""Unit tests for MCP Composer exception hierarchy."""

import pytest
from mcp_composer.core.utils.exceptions import (
    MCPComposerError,
    ServerError,
    ServerMountError,
    ServerConfigurationError,
    ServerNotFoundError,
    ServerAlreadyExistsError,
    ServerBuildError,
    ToolError,
    ToolRegistrationError,
    ToolNotFoundError,
    ToolExecutionError,
    ToolValidationError,
    ToolDuplicateError,
    ToolFilterError,
    ToolGenerateError,
    ToolDisableError,
    DatabaseError,
    DatabaseConnectionError,
    DatabaseOperationError,
    DatabaseNotAvailableError,
    AuthenticationError,
    TokenExpiredError,
    InvalidCredentialsError,
    AuthorizationError,
    ValidationError,
    ConfigValidationError,
    InputValidationError,
    MiddlewareError,
    MiddlewareExecutionError,
    MiddlewareConfigurationError,
    MemberServerError,
)


class TestMCPComposerError:
    """Test base MCPComposerError class."""

    def test_basic_error(self):
        """Test basic error creation without context."""
        error = MCPComposerError("Test error")
        assert str(error) == "Test error"
        assert error.message == "Test error"
        assert error.context == {}

    def test_error_with_context(self):
        """Test error creation with context."""
        context = {"server_id": "test-server", "operation": "mount"}
        error = MCPComposerError("Test error", context=context)

        assert error.message == "Test error"
        assert error.context == context
        assert "server_id=test-server" in str(error)
        assert "operation=mount" in str(error)

    def test_error_repr(self):
        """Test error representation."""
        context = {"key": "value"}
        error = MCPComposerError("Test error", context=context)
        repr_str = repr(error)

        assert "MCPComposerError" in repr_str
        assert "Test error" in repr_str
        assert "key" in repr_str

    def test_error_inheritance(self):
        """Test that MCPComposerError inherits from Exception."""
        error = MCPComposerError("Test")
        assert isinstance(error, Exception)


class TestExceptionHierarchy:
    """Test exception inheritance hierarchy."""

    def test_server_error_hierarchy(self):
        """Test server exception hierarchy."""
        assert issubclass(ServerError, MCPComposerError)
        assert issubclass(ServerMountError, ServerError)
        assert issubclass(ServerConfigurationError, ServerError)
        assert issubclass(ServerNotFoundError, ServerError)
        assert issubclass(ServerAlreadyExistsError, ServerError)
        assert issubclass(ServerBuildError, ServerError)
        assert issubclass(MemberServerError, ServerError)

    def test_tool_error_hierarchy(self):
        """Test tool exception hierarchy."""
        assert issubclass(ToolError, MCPComposerError)
        assert issubclass(ToolRegistrationError, ToolError)
        assert issubclass(ToolNotFoundError, ToolError)
        assert issubclass(ToolExecutionError, ToolError)
        assert issubclass(ToolValidationError, ToolError)
        assert issubclass(ToolDuplicateError, ToolError)
        assert issubclass(ToolFilterError, ToolError)
        assert issubclass(ToolGenerateError, ToolError)
        assert issubclass(ToolDisableError, ToolError)

    def test_database_error_hierarchy(self):
        """Test database exception hierarchy."""
        assert issubclass(DatabaseError, MCPComposerError)
        assert issubclass(DatabaseConnectionError, DatabaseError)
        assert issubclass(DatabaseOperationError, DatabaseError)
        assert issubclass(DatabaseNotAvailableError, DatabaseError)

    def test_authentication_error_hierarchy(self):
        """Test authentication exception hierarchy."""
        assert issubclass(AuthenticationError, MCPComposerError)
        assert issubclass(TokenExpiredError, AuthenticationError)
        assert issubclass(InvalidCredentialsError, AuthenticationError)
        assert issubclass(AuthorizationError, AuthenticationError)

    def test_validation_error_hierarchy(self):
        """Test validation exception hierarchy."""
        assert issubclass(ValidationError, MCPComposerError)
        assert issubclass(ConfigValidationError, ValidationError)
        assert issubclass(InputValidationError, ValidationError)

    def test_middleware_error_hierarchy(self):
        """Test middleware exception hierarchy."""
        assert issubclass(MiddlewareError, MCPComposerError)
        assert issubclass(MiddlewareExecutionError, MiddlewareError)
        assert issubclass(MiddlewareConfigurationError, MiddlewareError)


class TestServerExceptions:
    """Test server-related exceptions."""

    def test_server_mount_error(self):
        """Test ServerMountError with context."""
        context = {"server_id": "test-server", "config": {"type": "stdio"}}
        error = ServerMountError("Failed to mount server", context=context)

        assert "Failed to mount server" in str(error)
        assert "server_id=test-server" in str(error)
        assert error.context["server_id"] == "test-server"

    def test_server_configuration_error(self):
        """Test ServerConfigurationError."""
        error = ServerConfigurationError("Missing required field 'id'")
        assert "Missing required field" in str(error)

    def test_server_not_found_error(self):
        """Test ServerNotFoundError."""
        context = {"server_id": "missing-server"}
        error = ServerNotFoundError("Server not found", context=context)
        assert "Server not found" in str(error)


class TestToolExceptions:
    """Test tool-related exceptions."""

    def test_tool_registration_error(self):
        """Test ToolRegistrationError."""
        context = {"tool_name": "test_tool", "server_id": "test-server"}
        error = ToolRegistrationError("Failed to register tool", context=context)

        assert "Failed to register tool" in str(error)
        assert "tool_name=test_tool" in str(error)

    def test_tool_validation_error(self):
        """Test ToolValidationError."""
        context = {"tool_name": "invalid_tool", "reason": "missing description"}
        error = ToolValidationError("Tool validation failed", context=context)

        assert "Tool validation failed" in str(error)
        assert error.context["reason"] == "missing description"

    def test_tool_execution_error(self):
        """Test ToolExecutionError."""
        error = ToolExecutionError("Tool execution failed")
        assert "Tool execution failed" in str(error)


class TestDatabaseExceptions:
    """Test database-related exceptions."""

    def test_database_connection_error(self):
        """Test DatabaseConnectionError."""
        context = {"host": "localhost", "port": 5432}
        error = DatabaseConnectionError("Failed to connect", context=context)

        assert "Failed to connect" in str(error)
        assert "host=localhost" in str(error)

    def test_database_operation_error(self):
        """Test DatabaseOperationError."""
        context = {"operation": "save", "collection": "servers"}
        error = DatabaseOperationError("Operation failed", context=context)

        assert "Operation failed" in str(error)
        assert error.context["operation"] == "save"


class TestAuthenticationExceptions:
    """Test authentication-related exceptions."""

    def test_token_expired_error(self):
        """Test TokenExpiredError."""
        context = {"token_type": "JWT", "expired_at": "2024-01-01"}
        error = TokenExpiredError("Token has expired", context=context)

        assert "Token has expired" in str(error)
        assert error.context["token_type"] == "JWT"

    def test_invalid_credentials_error(self):
        """Test InvalidCredentialsError."""
        error = InvalidCredentialsError("Invalid username or password")
        assert "Invalid username or password" in str(error)

    def test_authorization_error(self):
        """Test AuthorizationError."""
        context = {"user": "test_user", "required_permission": "admin"}
        error = AuthorizationError("Insufficient permissions", context=context)

        assert "Insufficient permissions" in str(error)
        assert error.context["required_permission"] == "admin"


class TestValidationExceptions:
    """Test validation-related exceptions."""

    def test_config_validation_error(self):
        """Test ConfigValidationError."""
        context = {"field": "server_id", "value": None}
        error = ConfigValidationError("Invalid configuration", context=context)

        assert "Invalid configuration" in str(error)
        assert error.context["field"] == "server_id"

    def test_input_validation_error(self):
        """Test InputValidationError."""
        context = {"parameter": "port", "expected": "integer", "got": "string"}
        error = InputValidationError("Invalid input", context=context)

        assert "Invalid input" in str(error)
        assert error.context["expected"] == "integer"


class TestMiddlewareExceptions:
    """Test middleware-related exceptions."""

    def test_middleware_execution_error(self):
        """Test MiddlewareExecutionError."""
        context = {"middleware": "auth_middleware", "phase": "pre_request"}
        error = MiddlewareExecutionError("Middleware failed", context=context)

        assert "Middleware failed" in str(error)
        assert error.context["middleware"] == "auth_middleware"

    def test_middleware_configuration_error(self):
        """Test MiddlewareConfigurationError."""
        error = MiddlewareConfigurationError("Invalid middleware config")
        assert "Invalid middleware config" in str(error)


class TestExceptionChaining:
    """Test exception chaining and context preservation."""

    def test_exception_chaining(self):
        """Test that exceptions can be chained properly."""
        try:
            try:
                raise ServerBuildError("Build failed")
            except ServerBuildError as e:
                raise ServerMountError(
                    "Mount failed", context={"server_id": "test"}
                ) from e
        except ServerMountError as e:
            assert isinstance(e.__cause__, ServerBuildError)
            assert "Mount failed" in str(e)
            assert e.context["server_id"] == "test"

    def test_context_preservation(self):
        """Test that context is preserved through exception handling."""
        context = {"server_id": "test", "operation": "mount", "attempt": 1}
        error = ServerMountError("Failed", context=context)

        # Simulate catching and re-raising
        try:
            raise error
        except ServerMountError as e:
            assert e.context == context
            assert e.context["server_id"] == "test"
            assert e.context["attempt"] == 1


class TestBackwardCompatibility:
    """Test backward compatibility with existing code."""

    def test_member_server_error_compatibility(self):
        """Test that MemberServerError still works for backward compatibility."""
        error = MemberServerError("Server error")

        # Should inherit from ServerError
        assert isinstance(error, ServerError)
        assert isinstance(error, MCPComposerError)
        assert "Server error" in str(error)

    def test_tool_errors_compatibility(self):
        """Test that existing tool errors still work."""
        duplicate_error = ToolDuplicateError("Duplicate tool")
        filter_error = ToolFilterError("Filter failed")
        generate_error = ToolGenerateError("Generation failed")
        disable_error = ToolDisableError("Disable failed")

        assert all(
            isinstance(e, ToolError)
            for e in [duplicate_error, filter_error, generate_error, disable_error]
        )


# Made with Bob
