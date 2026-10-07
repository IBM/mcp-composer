"""Unit tests for strongly-typed configuration models.

Tests cover:
- Model validation and field constraints
- Custom validators
- Factory methods
- Serialization/deserialization
- Error handling
- Performance benchmarks
"""

import pytest
import time
from typing import Any

from mcp_composer.core.models.config import (
    AuthConfig,
    AuthStrategy,
    OpenAPIConfig,
    GraphQLConfig,
    ServerConfig,
    ServerType,
    DatabaseConfig,
    DatabaseType,
    MiddlewareConfig,
    MiddlewareMode,
    ToolConfig,
    PromptArgument,
    PromptConfig,
    ResourceConfig,
)


# ============================================================================
# AuthConfig Tests
# ============================================================================


class TestAuthConfig:
    """Tests for AuthConfig model."""

    def test_oauth2_config_valid(self):
        """Test valid OAuth2 configuration."""
        config = AuthConfig(
            strategy="oauth2",
            client_id="test-client",
            client_secret="test-secret", # pragma: allowlist secret
            token_url="https://auth.example.com/token", # pragma: allowlist secret
            scope="read write",
        )
        assert config.strategy == AuthStrategy.OAUTH2
        assert config.client_id == "test-client"
        assert config.scope == "read write"

    def test_oauth2_config_missing_fields(self):
        """Test OAuth2 configuration with missing required fields."""
        with pytest.raises(ValueError, match="OAuth2 authentication requires"):
            AuthConfig(
                strategy="oauth2",
                client_id="test-client",
                # Missing client_secret and token_url
            )

    def test_bearer_config_valid(self):
        """Test valid Bearer token configuration."""
        config = AuthConfig(strategy="bearer", token="my-bearer-token") # pragma: allowlist secret
        assert config.strategy == AuthStrategy.BEARER
        assert config.token == "my-bearer-token" # pragma: allowlist secret

    def test_bearer_config_missing_token(self):
        """Test Bearer configuration with missing token."""
        with pytest.raises(ValueError, match="Bearer authentication requires token"):
            AuthConfig(strategy="bearer")

    def test_basic_auth_config_valid(self):
        """Test valid Basic auth configuration."""
        config = AuthConfig(strategy="basic", username="user", password="pass") # pragma: allowlist secret
        assert config.strategy == AuthStrategy.BASIC
        assert config.username == "user" # pragma: allowlist secret
        assert config.password == "pass" # pragma: allowlist secret

    def test_basic_auth_config_missing_fields(self):
        """Test Basic auth configuration with missing fields."""
        with pytest.raises(ValueError, match="Basic authentication requires"):
            AuthConfig(strategy="basic", username="user")

    def test_api_key_config_valid(self):
        """Test valid API key configuration."""
        config = AuthConfig(
            strategy="api_key", api_key_name="X-API-Key", api_key_value="secret-key" # pragma: allowlist secret
        )
        assert config.strategy == AuthStrategy.API_KEY # pragma: allowlist secret
        assert config.api_key_name == "X-API-Key" # pragma: allowlist secret
        assert config.api_key_value == "secret-key" # pragma: allowlist secret

    def test_api_key_config_missing_fields(self):
        """Test API key configuration with missing fields."""
        with pytest.raises(ValueError, match="API key authentication requires"):
            AuthConfig(strategy="api_key", api_key_name="X-API-Key") # pragma: allowlist secret

    def test_jwt_config_valid(self):
        """Test valid JWT configuration."""
        config = AuthConfig(
            strategy="jwt",
            jwt_secret="valid-value", # pragma: allowlist secret
            jwt_algorithm="HS256",
            jwt_issuer="test-issuer",
        )
        assert config.strategy == AuthStrategy.JWT
        assert config.jwt_secret == "valid-value" # pragma: allowlist secret
        assert config.jwt_algorithm == "HS256"

    def test_jwt_config_missing_secret(self):
        """Test JWT configuration with missing secret.""" # pragma: allowlist secret
        with pytest.raises(ValueError, match="JWT authentication requires jwt_secret"): # pragma: allowlist secret
            AuthConfig(strategy="jwt")

    def test_auth_config_serialization(self):
        """Test AuthConfig serialization."""
        config = AuthConfig(
            strategy="oauth2",
            client_id="test",
            client_secret="secret", # pragma: allowlist secret
            token_url="https://auth.example.com/token", # pragma: allowlist secret
        )
        data = config.to_dict()
        assert data["strategy"] == "oauth2" 
        assert data["client_id"] == "test"

        # Test deserialization
        loaded = AuthConfig.from_dict(data)
        assert loaded.client_id == config.client_id


# ============================================================================
# OpenAPIConfig Tests
# ============================================================================


class TestOpenAPIConfig:
    """Tests for OpenAPIConfig model."""

    def test_openapi_config_valid(self):
        """Test valid OpenAPI configuration."""
        config = OpenAPIConfig(
            endpoint="https://api.example.com/openapi.json", # pragma: allowlist secret
            version="3.0.0",
            timeout=30,
        )
        assert config.endpoint == "https://api.example.com/openapi.json" # pragma: allowlist secret
        assert config.version == "3.0.0"
        assert config.timeout == 30

    def test_openapi_config_invalid_url(self):
        """Test OpenAPI configuration with invalid URL."""
        with pytest.raises(ValueError, match="must be a valid HTTP"):
            OpenAPIConfig(endpoint="not-a-url")

    def test_openapi_config_invalid_version(self):
        """Test OpenAPI configuration with invalid version."""
        with pytest.raises(ValueError, match="Version must be in format"):
            OpenAPIConfig(
                endpoint="https://api.example.com/openapi.json", version="invalid" # pragma: allowlist secret
            )

    def test_openapi_config_with_auth(self):
        """Test OpenAPI configuration with authentication."""
        auth = AuthConfig(strategy="bearer", token="test-token") # pragma: allowlist secret
        config = OpenAPIConfig(
            endpoint="https://api.example.com/openapi.json", auth=auth # pragma: allowlist secret
        )
        assert config.auth.strategy == AuthStrategy.BEARER


# ============================================================================
# GraphQLConfig Tests
# ============================================================================


class TestGraphQLConfig:
    """Tests for GraphQLConfig model."""

    def test_graphql_config_valid(self):
        """Test valid GraphQL configuration."""
        config = GraphQLConfig(
            endpoint="https://api.example.com/graphql", # pragma: allowlist secret
            max_depth=10,
            introspection_enabled=True,
        )
        assert config.endpoint == "https://api.example.com/graphql" # pragma: allowlist secret
        assert config.max_depth == 10
        assert config.introspection_enabled is True

    def test_graphql_config_invalid_url(self):
        """Test GraphQL configuration with invalid URL."""
        with pytest.raises(ValueError, match="must be a valid HTTP"):
            GraphQLConfig(endpoint="invalid-url")

    def test_graphql_config_max_depth_validation(self):
        """Test GraphQL configuration with invalid max_depth."""
        with pytest.raises(ValueError):
            GraphQLConfig(endpoint="https://api.example.com/graphql", max_depth=0)


# ============================================================================
# ServerConfig Tests
# ============================================================================


class TestServerConfig:
    """Tests for ServerConfig model."""

    def test_http_server_config_valid(self):
        """Test valid HTTP server configuration."""
        config = ServerConfig(
            id="test-server",
            type="http",
            endpoint="https://api.example.com", # pragma: allowlist secret
            tags=["production", "api"],
        )
        assert config.id == "test-server"
        assert config.type == ServerType.HTTP
        assert config.endpoint == "https://api.example.com" # pragma: allowlist secret
        assert "production" in config.tags

    def test_server_config_invalid_id(self):
        """Test server configuration with invalid ID."""
        with pytest.raises(ValueError, match="must contain only alphanumeric"):
            ServerConfig(
                id="invalid id with spaces", type="http", endpoint="https://api.example.com" # pragma: allowlist secret
            )

    def test_http_server_missing_endpoint(self):
        """Test HTTP server configuration without endpoint."""
        with pytest.raises(ValueError, match="requires 'endpoint' field"):
            ServerConfig(id="test", type="http")

    def test_stdio_server_config_valid(self):
        """Test valid STDIO server configuration."""
        config = ServerConfig(
            id="local-tool",
            type="stdio",
            command="python",
            args=["-m", "my_tool"],
            cwd="/path/to/tool",
        )
        assert config.type == ServerType.STDIO
        assert config.command == "python"
        assert config.args == ["-m", "my_tool"]

    def test_stdio_server_missing_command(self):
        """Test STDIO server configuration without command."""
        with pytest.raises(ValueError, match="requires 'command' field"):
            ServerConfig(id="test", type="stdio")

    def test_openapi_server_config_valid(self):
        """Test valid OpenAPI server configuration."""
        openapi_config = OpenAPIConfig(endpoint="https://api.example.com/openapi.json") # pragma: allowlist secret
        config = ServerConfig(id="api-server", type="openapi", open_api=openapi_config)
        assert config.type == ServerType.OPENAPI
        assert isinstance(config.open_api, OpenAPIConfig)

    def test_openapi_server_missing_config(self):
        """Test OpenAPI server configuration without open_api field."""
        with pytest.raises(ValueError, match="requires 'open_api' field"):
            ServerConfig(id="test", type="openapi")

    def test_server_config_with_auth(self):
        """Test server configuration with authentication."""
        auth = AuthConfig(strategy="bearer", token="test-token") # pragma: allowlist secret
        config = ServerConfig(
            id="secure-api", type="http", endpoint="https://api.example.com", auth=auth # pragma: allowlist secret
        )
        assert isinstance(config.auth, AuthConfig)
        assert config.auth.strategy == AuthStrategy.BEARER

    def test_server_config_tags_deduplication(self):
        """Test that duplicate tags are removed."""
        config = ServerConfig(
            id="test",
            type="http",
            endpoint="https://api.example.com", # pragma: allowlist secret
            tags=["api", "production", "api", "production"],
        )
        assert len(config.tags) == 2
        assert set(config.tags) == {"api", "production"}


# ============================================================================
# DatabaseConfig Tests
# ============================================================================


class TestDatabaseConfig:
    """Tests for DatabaseConfig model."""

    def test_postgres_config_with_url(self):
        """Test PostgreSQL configuration with connection URL."""
        config = DatabaseConfig(
            type="postgres",
            url="postgresql://localhost:5432/mydb",
            min_pool_size=2,
            max_pool_size=10,
        )
        assert config.type == DatabaseType.POSTGRES
        assert config.url == "postgresql://localhost:5432/mydb"

    def test_postgres_config_with_params(self):
        """Test PostgreSQL configuration with individual parameters."""
        config = DatabaseConfig(
            type="postgres",
            host="localhost",
            port=5432,
            database="mydb",
            user="admin",
            password="secret", # pragma: allowlist secret
        )
        assert config.host == "localhost"
        assert config.port == 5432
        assert config.database == "mydb"

    def test_postgres_config_missing_params(self):
        """Test PostgreSQL configuration with missing parameters."""
        with pytest.raises(ValueError, match="PostgreSQL requires"):
            DatabaseConfig(type="postgres", host="localhost")
    def test_local_file_config_valid(self):
        """Test valid local file configuration."""
        config = DatabaseConfig(type="local_file", file_path="/path/to/config.json")
        assert config.type == DatabaseType.LOCAL_FILE
        assert config.file_path == "/path/to/config.json"

    def test_local_file_config_missing_path(self):
        """Test local file configuration with missing path."""
        with pytest.raises(ValueError, match="requires 'file_path'"):
            DatabaseConfig(type="local_file")

    def test_database_config_pool_size_validation(self):
        """Test database configuration pool size validation."""
        with pytest.raises(ValueError, match="min_pool_size cannot be greater"):
            DatabaseConfig(
                type="postgres",
                url="postgresql://user:pass@localhost:5432/mydb", # pragma: allowlist secret
                min_pool_size=20,
                max_pool_size=10,
            )


# ============================================================================
# MiddlewareConfig Tests
# ============================================================================
class TestMiddlewareConfig:
    """Tests for MiddlewareConfig model."""
    def test_middleware_config_invalid_name(self):
        """Test middleware configuration with invalid name."""
        with pytest.raises(ValueError, match="must contain only alphanumeric"):
            MiddlewareConfig(
                name="invalid name with spaces",
                kind="module.Class",
                applied_hooks=["hook"],
            )

    def test_middleware_config_invalid_kind(self):
        """Test middleware configuration with invalid kind."""
        with pytest.raises(ValueError, match="must be a valid Python import path"):
            MiddlewareConfig(name="test", kind="InvalidClass", applied_hooks=["hook"])

    def test_middleware_config_empty_hooks(self):
        """Test middleware configuration with empty hooks."""
        with pytest.raises(ValueError, match="At least one hook must be specified"):
            MiddlewareConfig(name="test", kind="module.Class", applied_hooks=[])

    def test_middleware_config_invalid_version(self):
        """Test middleware configuration with invalid version."""
        with pytest.raises(ValueError, match="must be in semver format"):
            MiddlewareConfig(
                name="test",
                kind="module.Class",
                applied_hooks=["hook"],
                version="invalid",
            )

    def test_middleware_config_hooks_deduplication(self):
        """Test that duplicate hooks are removed."""
        config = MiddlewareConfig(
            name="test",
            kind="module.Class",
            applied_hooks=["hook1", "hook2", "hook1", "hook2"],
        )
        assert len(config.applied_hooks) == 2


# ============================================================================
# ToolConfig Tests
# ============================================================================


class TestToolConfig:
    """Tests for ToolConfig model."""

    def test_openapi_tool_config_valid(self):
        """Test valid OpenAPI tool configuration."""
        config = ToolConfig(
            openapi="3.0.0",
            info={"title": "My API", "version": "1.0.0"},
            servers=[{"url": "https://api.example.com"}], # pragma: allowlist secret
            paths={"/users": {"get": {"summary": "List users"}}},
        )
        assert config.openapi == "3.0.0"
        assert config.info["title"] == "My API"

    def test_openapi_tool_missing_paths(self):
        """Test OpenAPI tool configuration without paths."""
        with pytest.raises(ValueError, match="OpenAPI tools require 'paths' field"):
            ToolConfig(
                openapi="3.0.0",
                info={"title": "My API"},
                servers=[{"url": "https://api.example.com"}], # pragma: allowlist secret
            )

    def test_curl_tool_config_valid(self):
        """Test valid curl tool configuration."""
        config = ToolConfig(
            tool_type="curl",
            name="fetch-data",
            description="Fetch data from API",
            endpoint="https://api.example.com/data", # pragma: allowlist secret
        )
        assert config.tool_type == "curl"
        assert config.name == "fetch-data"

    def test_curl_tool_missing_name(self):
        """Test curl tool configuration without name."""
        with pytest.raises(ValueError, match="requires 'name' field"):
            ToolConfig(tool_type="curl", endpoint="https://api.example.com") # pragma: allowlist secret

    def test_tool_config_invalid_openapi_version(self):
        """Test tool configuration with invalid OpenAPI version."""
        with pytest.raises(ValueError, match="must be in format"):
            ToolConfig(openapi="invalid", paths={})


# ============================================================================
# PromptConfig Tests
# ============================================================================


class TestPromptConfig:
    """Tests for PromptConfig model."""

    def test_prompt_config_valid(self):
        """Test valid prompt configuration."""
        config = PromptConfig(
            name="user-greeting",
            description="Generate a personalized greeting",
            template="Hello {{name}}, welcome to {{service}}!",
            arguments=[
                PromptArgument(name="name", type="string", required=True),
                PromptArgument(name="service", type="string", required=True),
            ],
            tags=["greeting", "user"],
            version="1.0.0",
        )
        assert config.name == "user-greeting"
        assert len(config.arguments) == 2

    def test_prompt_config_invalid_name(self):
        """Test prompt configuration with invalid name."""
        with pytest.raises(ValueError, match="must contain only alphanumeric"):
            PromptConfig(
                name="invalid name",
                description="Test",
                template="Hello {{name}}",
            )

    def test_prompt_config_unbalanced_braces(self):
        """Test prompt configuration with unbalanced template braces."""
        with pytest.raises(ValueError, match="unbalanced placeholder braces"):
            PromptConfig(
                name="test",
                description="Test",
                template="Hello {{name}",
            )

    def test_prompt_config_invalid_version(self):
        """Test prompt configuration with invalid version."""
        with pytest.raises(ValueError, match="must be in semver format"):
            PromptConfig(
                name="test",
                description="Test",
                template="Hello",
                version="invalid",
            )

    def test_prompt_argument_valid(self):
        """Test valid prompt argument."""
        arg = PromptArgument(
            name="user_id",
            type="string",
            required=True,
            description="User identifier",
            pattern="^[a-zA-Z0-9-]+$",
            min_length=1,
            max_length=50,
        )
        assert arg.name == "user_id"
        assert arg.pattern == "^[a-zA-Z0-9-]+$"

    def test_prompt_argument_invalid_name(self):
        """Test prompt argument with invalid name."""
        with pytest.raises(ValueError, match="must be a valid identifier"):
            PromptArgument(name="123invalid", type="string")

    def test_prompt_argument_invalid_pattern(self):
        """Test prompt argument with invalid regex pattern."""
        with pytest.raises(ValueError, match="Invalid regex pattern"):
            PromptArgument(name="test", type="string", pattern="[invalid(")


# ============================================================================
# ResourceConfig Tests
# ============================================================================


class TestResourceConfig:
    """Tests for ResourceConfig model."""

    def test_static_resource_config_valid(self):
        """Test valid static resource configuration."""
        config = ResourceConfig(
            name="api-docs",
            description="API documentation",
            uri="resource://docs/api.md",
            text="# API Documentation\n...",
            mime_type="text/markdown",
            tags=["documentation"],
        )
        assert config.name == "api-docs"
        assert config.uri == "resource://docs/api.md"
        assert config.mime_type == "text/markdown"

    def test_dynamic_resource_config_valid(self):
        """Test valid dynamic resource configuration."""
        config = ResourceConfig(
            name="user-profile",
            description="User profile template",
            uri_template="resource://users/{user_id}/profile",
            template="User: {{name}}\nEmail: {{email}}",
            mime_type="text/plain",
        )
        assert config.uri_template == "resource://users/{user_id}/profile"
        assert config.parameters is not None
        assert "user_id" in config.parameters

    def test_resource_config_auto_uri_generation(self):
        """Test automatic URI generation when not provided."""
        config = ResourceConfig(
            name="test-resource",
            description="Test resource",
            text="Content",
        )
        assert config.uri == "resource://test-resource"

    def test_resource_config_both_uri_and_template(self):
        """Test resource configuration with both uri and uri_template."""
        with pytest.raises(ValueError, match="cannot have both"):
            ResourceConfig(
                name="test",
                uri="resource://test",
                uri_template="resource://test/{id}",
            )

    def test_resource_config_invalid_mime_type(self):
        """Test resource configuration with invalid MIME type."""
        with pytest.raises(ValueError, match="must be in format"):
            ResourceConfig(
                name="test",
                uri="resource://test",
                mime_type="invalid",
            )

    def test_resource_config_invalid_name(self):
        """Test resource configuration with invalid name."""
        with pytest.raises(ValueError, match="must contain only alphanumeric"):
            ResourceConfig(
                name="invalid name",
                uri="resource://test",
            )


# ============================================================================
# Performance Benchmarks
# ============================================================================


class TestPerformanceBenchmarks:
    """Performance benchmarks for configuration models."""

    def test_server_config_validation_performance(self):
        """Test that server config validation is fast (<1ms)."""
        config_data = {
            "id": "test-server",
            "type": "http",
            "endpoint": "https://api.example.com", # pragma: allowlist secret
            "tags": ["production", "api"],
        }

        start = time.perf_counter()
        for _ in range(1000):
            ServerConfig.model_validate(config_data)
        end = time.perf_counter()

        avg_time = (end - start) / 1000
        assert avg_time < 0.001, f"Validation took {avg_time*1000:.2f}ms (expected <1ms)"

    def test_auth_config_validation_performance(self):
        """Test that auth config validation is fast (<1ms)."""
        config_data = {
            "strategy": "oauth2",
            "client_id": "test",
            "client_secret": "secret", # pragma: allowlist secret
            "token_url": "https://auth.example.com/token", # pragma: allowlist secret
        }

        start = time.perf_counter()
        for _ in range(1000):
            AuthConfig.model_validate(config_data)
        end = time.perf_counter()

        avg_time = (end - start) / 1000
        assert avg_time < 0.001, f"Validation took {avg_time*1000:.2f}ms (expected <1ms)"

    def test_middleware_config_validation_performance(self):
        """Test that middleware config validation is fast (<1ms)."""
        config_data = {
            "name": "test-middleware",
            "kind": "module.Class",
            "applied_hooks": ["before_request"],
        }

        start = time.perf_counter()
        for _ in range(1000):
            MiddlewareConfig.model_validate(config_data)
        end = time.perf_counter()

        avg_time = (end - start) / 1000
        assert avg_time < 0.001, f"Validation took {avg_time*1000:.2f}ms (expected <1ms)"


# ============================================================================
# Integration Tests
# ============================================================================


class TestConfigIntegration:
    """Integration tests for configuration models."""

    def test_complete_server_config_with_auth(self):
        """Test complete server configuration with authentication."""
        auth = AuthConfig(
            strategy="oauth2",
            client_id="test-client",
            client_secret="test-secret", # pragma: allowlist secret
            token_url="https://auth.example.com/token", # pragma: allowlist secret
            scope="read write",
        )

        server = ServerConfig(
            id="production-api",
            type="http",
            endpoint="https://api.example.com", # pragma: allowlist secret
            auth=auth,
            tags=["production", "api"],
            timeout=60,
            retry_count=5,
        )

        # Serialize and deserialize
        data = server.to_dict()
        loaded = ServerConfig.from_dict(data)

        assert loaded.id == server.id
        assert loaded.auth.client_id == auth.client_id
        assert loaded.timeout == 60

    def test_openapi_server_with_nested_config(self):
        """Test OpenAPI server with nested configuration."""
        openapi_config = OpenAPIConfig(
            endpoint="https://api.example.com/openapi.json", # pragma: allowlist secret
            version="3.0.0",
            auth=AuthConfig(strategy="bearer", token="test-token"), # pragma: allowlist secret
        )

        server = ServerConfig(
            id="openapi-server",
            type="openapi",
            open_api=openapi_config,
        )

        # Serialize and deserialize
        data = server.to_dict()
        loaded = ServerConfig.from_dict(data)

        assert isinstance(loaded.open_api, OpenAPIConfig)
        assert loaded.open_api.auth.strategy == AuthStrategy.BEARER

    def test_database_config_serialization(self):
        """Test database configuration serialization."""
        config = DatabaseConfig(
            type="postgres",
            host="localhost",
            port=5432,
            database="mcp_composer",
            user="admin",
            password="secret", # pragma: allowlist secret
            min_pool_size=2,
            max_pool_size=10,
        )

        data = config.to_dict()
        loaded = DatabaseConfig.from_dict(data)

        assert loaded.host == config.host
        assert loaded.port == config.port
        assert loaded.min_pool_size == config.min_pool_size

# Made with Bob
