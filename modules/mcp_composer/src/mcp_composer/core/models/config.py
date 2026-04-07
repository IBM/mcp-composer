"""Strongly-typed configuration models for MCP Composer.

This module provides Pydantic models for all configuration types in the system,
replacing generic dictionaries with validated, typed objects. All models include:
- Field validation with regex patterns, min/max constraints, and required fields
- Custom validators for complex validation logic
- JSON serialization/deserialization support
- Comprehensive docstrings with examples
- Factory methods for backward compatibility
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    field_validator,
    model_validator,
)


# ============================================================================
# Enums for type safety
# ============================================================================


class ServerType(str, Enum):
    """Supported server types."""

    HTTP = "http"
    SSE = "sse"
    OPENAPI = "openapi"
    STDIO = "stdio"
    GRAPHQL = "graphql"
    LOCAL = "local"
    CLIENT = "client"


class AuthStrategy(str, Enum):
    """Supported authentication strategies."""

    OAUTH = "oauth" # pragma: allowlist secret
    OAUTH2 = "oauth2"
    JWT = "jwt"
    BEARER = "bearer"
    BASIC = "basic"
    API_KEY = "api_key"
    NONE = "none"


class DatabaseType(str, Enum):
    """Supported database types."""

    POSTGRES = "postgres"
    POSTGRESQL = "postgresql"
    CLOUDANT = "cloudant"
    LOCAL_FILE = "local_file"
    FAKE = "fake"


class MiddlewareMode(str, Enum):
    """Middleware execution modes."""

    ENABLED = "enabled"
    DISABLED = "disabled"


# ============================================================================
# Base Configuration Model
# ============================================================================


class BaseConfig(BaseModel):
    """Base configuration model with common settings.

    All configuration models inherit from this class to ensure consistent
    behavior across the system.
    """

    model_config = ConfigDict(
        extra="forbid",  # Prevent extra fields by default
        validate_assignment=True,  # Validate on attribute assignment
        str_strip_whitespace=True,  # Strip whitespace from strings
        use_enum_values=True,  # Use enum values instead of enum objects
    )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> BaseConfig:
        """Factory method to create config from dictionary.

        Args:
            data: Dictionary containing configuration data

        Returns:
            Validated configuration instance

        Example:
            >>> config = ServerConfig.from_dict({"id": "test", "type": "http", "endpoint": "https://api.example.com"})
        """
        return cls.model_validate(data)

    def to_dict(self, exclude_none: bool = True) -> Dict[str, Any]:
        """Convert config to dictionary.

        Args:
            exclude_none: Whether to exclude None values

        Returns:
            Dictionary representation of the configuration

        Example:
            >>> config_dict = server.to_dict()
        """
        return self.model_dump(exclude_none=exclude_none, by_alias=True)


# ============================================================================
# Authentication Configuration Models
# ============================================================================


class AuthConfig(BaseConfig):
    """Authentication configuration for servers and tools.

    Supports multiple authentication strategies including OAuth2, JWT,
    Bearer tokens, Basic auth, and API keys.

    Attributes:
        strategy: Authentication strategy to use
        client_id: OAuth2/OIDC client ID
        client_secret: OAuth2/OIDC client secret
        token_url: OAuth2 token endpoint URL
        auth_url: OAuth2 authorization endpoint URL
        refresh_token: OAuth2 refresh token
        scope: OAuth2 scopes (space-separated)
        token: Bearer token or API key value
        username: Basic auth username
        password: Basic auth password
        api_key_name: API key header/query parameter name
        api_key_value: API key value
        jwt_secret: JWT signing secret
        jwt_algorithm: JWT signing algorithm
        jwt_issuer: JWT issuer claim
        jwt_audience: JWT audience claim
        extra: Additional authentication parameters

    Example:
        >>> # OAuth2 configuration
        >>> oauth_config = AuthConfig(
        ...     strategy="oauth2",
        ...     client_id="my-client",
        ...     client_secret="secret",
        ...     token_url="https://auth.example.com/token",
        ...     scope="read write"
        ... )
        >>>
        >>> # Bearer token configuration
        >>> bearer_config = AuthConfig(
        ...     strategy="bearer",
        ...     token="my-bearer-token"
        ... )
        >>>
        >>> # API key configuration
        >>> api_key_config = AuthConfig(
        ...     strategy="api_key",
        ...     api_key_name="X-API-Key",
        ...     api_key_value="my-api-key"
        ... )
    """

    model_config = ConfigDict(extra="allow")  # Allow extra fields for flexibility

    strategy: AuthStrategy = Field(
        ..., description="Authentication strategy (oauth2, jwt, bearer, basic, api_key)"
    )

    # OAuth2/OIDC fields
    client_id: Optional[str] = Field(None, description="OAuth2 client ID", min_length=1)
    client_secret: Optional[str] = Field(None, description="OAuth2 client secret", min_length=1)
    token_url: Optional[str] = Field(None, description="OAuth2 token endpoint URL")
    auth_url: Optional[str] = Field(None, description="OAuth2 authorization endpoint URL")
    refresh_token: Optional[str] = Field(None, description="OAuth2 refresh token")
    scope: Optional[str] = Field(None, description="OAuth2 scopes (space-separated)")

    # Bearer token fields
    token: Optional[str] = Field(None, description="Bearer token or API key value", min_length=1)

    # Basic auth fields
    username: Optional[str] = Field(None, description="Basic auth username", min_length=1)
    password: Optional[str] = Field(None, description="Basic auth password", min_length=1)

    # API key fields
    api_key_name: Optional[str] = Field(None, description="API key header/query parameter name")
    api_key_value: Optional[str] = Field(None, description="API key value", min_length=1)

    # JWT fields
    jwt_secret: Optional[str] = Field(None, description="JWT signing secret", min_length=1)
    jwt_algorithm: Optional[str] = Field("HS256", description="JWT signing algorithm")
    jwt_issuer: Optional[str] = Field(None, description="JWT issuer claim")
    jwt_audience: Optional[str] = Field(None, description="JWT audience claim")

    # Additional parameters
    extra: Optional[Dict[str, Any]] = Field(None, description="Additional authentication parameters")

    @model_validator(mode="after")
    def validate_auth_fields(self) -> AuthConfig:
        """Validate that required fields are present for each auth strategy."""
        strategy = self.strategy

        if strategy in [AuthStrategy.OAUTH, AuthStrategy.OAUTH2]:
            if not self.client_id or not self.client_secret or not self.token_url:
                raise ValueError(
                    f"OAuth2 authentication requires client_id, client_secret, and token_url"
                )

        elif strategy == AuthStrategy.BEARER:
            if not self.token:
                raise ValueError("Bearer authentication requires token")

        elif strategy == AuthStrategy.BASIC:
            if not self.username or not self.password:
                raise ValueError("Basic authentication requires username and password")

        elif strategy == AuthStrategy.API_KEY:
            if not self.api_key_name or not self.api_key_value:
                raise ValueError("API key authentication requires api_key_name and api_key_value")

        elif strategy == AuthStrategy.JWT:
            if not self.jwt_secret:
                raise ValueError("JWT authentication requires jwt_secret")

        return self


# ============================================================================
# OpenAPI Configuration Model
# ============================================================================


class OpenAPIConfig(BaseConfig):
    """OpenAPI server configuration.

    Configuration for servers that expose OpenAPI/Swagger specifications.

    Attributes:
        endpoint: OpenAPI specification endpoint URL
        spec_url: Alternative field name for endpoint
        version: OpenAPI specification version
        auth: Authentication configuration
        headers: Additional HTTP headers
        timeout: Request timeout in seconds
        verify_ssl: Whether to verify SSL certificates
        base_path: Base path for API endpoints

    Example:
        >>> openapi_config = OpenAPIConfig(
        ...     endpoint="https://api.example.com/openapi.json",
        ...     version="3.0.0",
        ...     auth=AuthConfig(strategy="bearer", token="my-token"),
        ...     timeout=30
        ... )
    """

    endpoint: str = Field(..., description="OpenAPI specification endpoint URL", min_length=1)
    spec_url: Optional[str] = Field(None, description="Alternative field name for endpoint")
    version: Optional[str] = Field("3.0.0", description="OpenAPI specification version")
    auth: Optional[AuthConfig] = Field(None, description="Authentication configuration")
    headers: Optional[Dict[str, str]] = Field(None, description="Additional HTTP headers")
    timeout: Optional[int] = Field(30, ge=1, le=300, description="Request timeout in seconds")
    verify_ssl: Optional[bool] = Field(True, description="Whether to verify SSL certificates")
    base_path: Optional[str] = Field(None, description="Base path for API endpoints")

    @field_validator("endpoint", "spec_url")
    @classmethod
    def validate_url(cls, v: Optional[str]) -> Optional[str]:
        """Validate that endpoint is a valid URL."""
        if v and not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("Endpoint must be a valid HTTP(S) URL")
        return v

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: Optional[str]) -> Optional[str]:
        """Validate OpenAPI version format."""
        if v and not re.match(r"^\d+\.\d+(\.\d+)?$", v):
            raise ValueError("Version must be in format X.Y or X.Y.Z")
        return v


# ============================================================================
# GraphQL Configuration Model
# ============================================================================


class GraphQLConfig(BaseConfig):
    """GraphQL server configuration.

    Configuration for servers that expose GraphQL APIs.

    Attributes:
        endpoint: GraphQL endpoint URL
        schema_url: GraphQL schema endpoint URL (if different from endpoint)
        auth: Authentication configuration
        headers: Additional HTTP headers
        timeout: Request timeout in seconds
        verify_ssl: Whether to verify SSL certificates
        introspection_enabled: Whether introspection queries are allowed
        max_depth: Maximum query depth allowed
        max_complexity: Maximum query complexity allowed

    Example:
        >>> graphql_config = GraphQLConfig(
        ...     endpoint="https://api.example.com/graphql",
        ...     auth=AuthConfig(strategy="bearer", token="my-token"),
        ...     max_depth=10,
        ...     introspection_enabled=True
        ... )
    """

    endpoint: str = Field(..., description="GraphQL endpoint URL", min_length=1)
    schema_url: Optional[str] = Field(None, description="GraphQL schema endpoint URL")
    auth: Optional[AuthConfig] = Field(None, description="Authentication configuration")
    headers: Optional[Dict[str, str]] = Field(None, description="Additional HTTP headers")
    timeout: Optional[int] = Field(30, ge=1, le=300, description="Request timeout in seconds")
    verify_ssl: Optional[bool] = Field(True, description="Whether to verify SSL certificates")
    introspection_enabled: Optional[bool] = Field(
        True, description="Whether introspection queries are allowed"
    )
    max_depth: Optional[int] = Field(None, ge=1, le=100, description="Maximum query depth allowed")
    max_complexity: Optional[int] = Field(
        None, ge=1, le=10000, description="Maximum query complexity allowed"
    )

    @field_validator("endpoint", "schema_url")
    @classmethod
    def validate_url(cls, v: Optional[str]) -> Optional[str]:
        """Validate that endpoint is a valid URL."""
        if v and not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("Endpoint must be a valid HTTP(S) URL")
        return v


# ============================================================================
# Server Configuration Model (Enhanced)
# ============================================================================


class ServerConfig(BaseConfig):
    """Enhanced server configuration with comprehensive validation.

    Attributes:
        id: Unique identifier for the server
        type: Server type (http, sse, openapi, stdio, graphql, local, client)
        endpoint: Server endpoint URL (required for http, sse, graphql)
        open_api: OpenAPI configuration (required for openapi type)
        graphql: GraphQL configuration (required for graphql type)
        auth_strategy: Authentication strategy name
        auth: Authentication configuration
        command: Command for stdio servers
        args: Command arguments for stdio servers
        env: Environment variables
        cwd: Working directory for stdio servers
        label: Human-readable label
        tags: Tags for categorization
        enabled: Whether the server is enabled
        timeout: Request timeout in seconds
        retry_count: Number of retries for failed requests
        retry_delay: Delay between retries in seconds

    Example:
        >>> # HTTP server with OAuth
        >>> server = ServerConfig(
        ...     id="my-api",
        ...     type="http",
        ...     endpoint="https://api.example.com",
        ...     auth=AuthConfig(strategy="oauth2", client_id="id", client_secret="secret", token_url="https://auth.example.com/token"),
        ...     tags=["production", "api"]
        ... )
        >>>
        >>> # STDIO server
        >>> stdio_server = ServerConfig(
        ...     id="local-tool",
        ...     type="stdio",
        ...     command="python",
        ...     args=["-m", "my_tool"],
        ...     cwd="/path/to/tool"
        ... )
    """

    id: str = Field(..., description="Unique identifier for the server", min_length=1, max_length=255)
    type: ServerType = Field(..., description="Server type")
    endpoint: Optional[str] = Field(None, description="Server endpoint URL")
    open_api: Optional[Union[OpenAPIConfig, Dict[str, Any]]] = Field(
        None, description="OpenAPI configuration"
    )
    graphql: Optional[Union[GraphQLConfig, Dict[str, Any]]] = Field(
        None, description="GraphQL configuration"
    )
    auth_strategy: Optional[str] = Field(None, description="Authentication strategy name")
    auth: Optional[Union[AuthConfig, Dict[str, Any]]] = Field(
        None, description="Authentication configuration"
    )
    command: Optional[str] = Field(None, description="Command for stdio servers")
    args: Optional[List[str]] = Field(None, description="Command arguments for stdio servers")
    env: Optional[Dict[str, str]] = Field(None, description="Environment variables")
    cwd: Optional[str] = Field(None, description="Working directory")
    label: Optional[str] = Field(None, description="Human-readable label", max_length=255)
    tags: Optional[List[str]] = Field(None, description="Tags for categorization")
    enabled: Optional[bool] = Field(True, description="Whether the server is enabled")
    timeout: Optional[int] = Field(30, ge=1, le=300, description="Request timeout in seconds")
    retry_count: Optional[int] = Field(3, ge=0, le=10, description="Number of retries")
    retry_delay: Optional[float] = Field(1.0, ge=0.1, le=60.0, description="Delay between retries")

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        """Validate server ID format."""
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError("Server ID must contain only alphanumeric characters, hyphens, and underscores")
        return v

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(cls, v: Optional[str]) -> Optional[str]:
        """Validate endpoint URL format."""
        if v and not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("Endpoint must be a valid HTTP(S) URL")
        return v

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Validate and normalize tags."""
        if v:
            # Remove duplicates and empty strings
            return list(set(tag.strip() for tag in v if tag and tag.strip()))
        return v

    @model_validator(mode="after")
    def validate_server_type_requirements(self) -> ServerConfig:
        """Validate that required fields are present for each server type."""
        if self.type in [ServerType.HTTP, ServerType.SSE, ServerType.GRAPHQL]:
            if not self.endpoint:
                raise ValueError(f"Server type '{self.type}' requires 'endpoint' field")

        elif self.type == ServerType.OPENAPI:
            if not self.open_api:
                raise ValueError("Server type 'openapi' requires 'open_api' field")
            # Convert dict to OpenAPIConfig if needed
            if isinstance(self.open_api, dict):
                self.open_api = OpenAPIConfig.model_validate(self.open_api)

        elif self.type == ServerType.STDIO:
            if not self.command:
                raise ValueError("Server type 'stdio' requires 'command' field")

        # Convert auth dict to AuthConfig if needed
        if self.auth and isinstance(self.auth, dict):
            self.auth = AuthConfig.model_validate(self.auth)

        return self


# ============================================================================
# Database Configuration Model
# ============================================================================


class DatabaseConfig(BaseConfig):
    """Database configuration for persistent storage.

    Supports PostgreSQL, Cloudant, and local file storage.

    Attributes:
        type: Database type (postgres, cloudant, local_file, fake)
        host: Database host (for PostgreSQL)
        port: Database port (for PostgreSQL)
        database: Database name (for PostgreSQL)
        user: Database username (for PostgreSQL)
        password: Database password (for PostgreSQL)
        url: Database connection URL (alternative to individual params)
        api_key: API key (for Cloudant)
        service_url: Service URL (for Cloudant)
        db_name: Database/collection name
        table_name: Table name (for PostgreSQL)
        file_path: File path (for local_file type)
        min_pool_size: Minimum connection pool size
        max_pool_size: Maximum connection pool size
        connection_timeout: Connection timeout in seconds
        ssl_mode: SSL mode for PostgreSQL connections

    Example:
        >>> # PostgreSQL configuration
        >>> postgres_config = DatabaseConfig(
        ...     type="postgres",
        ...     host="localhost",
        ...     port=5432,
        ...     database="mcp_composer",
        ...     user="admin",
        ...     password="secret",
        ...     min_pool_size=2,
        ...     max_pool_size=10
        ... )
        >>>
        >>> # Cloudant configuration
        >>> cloudant_config = DatabaseConfig(
        ...     type="cloudant",
        ...     api_key="value", # pragma: allowlist secret
        ...     service_url="https://my-instance.cloudant.com",
        ...     db_name="mcp_servers"
        ... )
        >>>
        >>> # Local file configuration
        >>> file_config = DatabaseConfig(
        ...     type="local_file",
        ...     file_path="/path/to/config.json"
        ... )
    """

    type: DatabaseType = Field(..., description="Database type")

    # PostgreSQL fields
    host: Optional[str] = Field(None, description="Database host")
    port: Optional[int] = Field(5432, ge=1, le=65535, description="Database port")
    database: Optional[str] = Field(None, description="Database name")
    user: Optional[str] = Field(None, description="Database username")
    password: Optional[str] = Field(None, description="Database password")
    url: Optional[str] = Field(None, description="Database connection URL")

    # Cloudant fields
    api_key: Optional[str] = Field(None, description="API key (for Cloudant)")
    service_url: Optional[str] = Field(None, description="Service URL (for Cloudant)")

    # Common fields
    db_name: Optional[str] = Field("mcp_servers", description="Database/collection name")
    table_name: Optional[str] = Field("mcp_servers", description="Table name (for PostgreSQL)")

    # Local file fields
    file_path: Optional[str] = Field(None, description="File path (for local_file type)")

    # Connection pool settings
    min_pool_size: Optional[int] = Field(1, ge=1, le=100, description="Minimum connection pool size")
    max_pool_size: Optional[int] = Field(10, ge=1, le=100, description="Maximum connection pool size")
    connection_timeout: Optional[int] = Field(
        30, ge=1, le=300, description="Connection timeout in seconds"
    )

    # SSL settings
    ssl_mode: Optional[str] = Field(None, description="SSL mode for PostgreSQL connections")

    @model_validator(mode="after")
    def validate_database_requirements(self) -> DatabaseConfig:
        """Validate that required fields are present for each database type."""
        if self.type in [DatabaseType.POSTGRES, DatabaseType.POSTGRESQL]:
            if not self.url:
                if not all([self.host, self.database, self.user, self.password]):
                    raise ValueError(
                        "PostgreSQL requires either 'url' or all of 'host', 'database', 'user', 'password'"
                    )

        elif self.type == DatabaseType.CLOUDANT:
            if not self.api_key or not self.service_url:
                raise ValueError("Cloudant requires 'api_key' and 'service_url'")

        elif self.type == DatabaseType.LOCAL_FILE:
            if not self.file_path:
                raise ValueError("Local file database requires 'file_path'")

        # Validate pool sizes
        if self.min_pool_size and self.max_pool_size:
            if self.min_pool_size > self.max_pool_size:
                raise ValueError("min_pool_size cannot be greater than max_pool_size")

        return self


# ============================================================================
# Middleware Configuration Model (Enhanced)
# ============================================================================


class MiddlewareConfig(BaseConfig):
    """Enhanced middleware configuration with comprehensive validation.

    Attributes:
        name: Unique name for the middleware
        kind: Python import path to middleware class (module.Class)
        mode: Middleware mode (enabled/disabled)
        priority: Execution priority (0-10000, lower executes first)
        applied_hooks: Hooks where middleware is applied
        config: Middleware-specific configuration
        description: Middleware description
        version: Middleware version
        enabled: Whether the middleware is enabled
        timeout: Middleware execution timeout in seconds
        retry_on_failure: Whether to retry on failure
        max_retries: Maximum number of retries

    Example:
        >>> middleware = MiddlewareConfig(
        ...     name="auth-middleware",
        ...     kind="mcp_composer.middleware.auth_context_middleware.AuthContextMiddleware",
        ...     mode="enabled",
        ...     priority=100,
        ...     applied_hooks=["before_request", "after_request"],
        ...     config={"require_auth": True},
        ...     version="1.0.0"
        ... )
    """

    name: str = Field(..., description="Unique name for the middleware", min_length=1, max_length=255)
    kind: str = Field(..., description="Python import path to middleware class", min_length=1)
    mode: MiddlewareMode = Field(MiddlewareMode.ENABLED, description="Middleware mode")
    priority: int = Field(100, ge=0, le=10000, description="Execution priority (lower = earlier)")
    applied_hooks: List[str] = Field(..., description="Hooks where middleware is applied")
    config: Optional[Dict[str, Any]] = Field(None, description="Middleware-specific configuration")
    description: Optional[str] = Field(None, description="Middleware description", max_length=1000)
    version: Optional[str] = Field("0.0.0", description="Middleware version")
    enabled: Optional[bool] = Field(True, description="Whether the middleware is enabled")
    timeout: Optional[int] = Field(30, ge=1, le=300, description="Execution timeout in seconds")
    retry_on_failure: Optional[bool] = Field(False, description="Whether to retry on failure")
    max_retries: Optional[int] = Field(3, ge=0, le=10, description="Maximum number of retries")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate middleware name format."""
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError(
                "Middleware name must contain only alphanumeric characters, hyphens, and underscores"
            )
        return v

    @field_validator("kind")
    @classmethod
    def validate_kind(cls, v: str) -> str:
        """Validate that kind is a valid Python import path."""
        if "." not in v:
            raise ValueError("Kind must be a valid Python import path (e.g., 'module.submodule.ClassName')")
        # Validate format: module.submodule.ClassName
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)+$", v):
            raise ValueError("Kind must be a valid Python import path (e.g., 'module.submodule.ClassName')")
        return v

    @field_validator("applied_hooks")
    @classmethod
    def validate_hooks(cls, v: List[str]) -> List[str]:
        """Validate and normalize hooks."""
        if not v:
            raise ValueError("At least one hook must be specified")
        # Remove duplicates and empty strings
        hooks = list(set(hook.strip() for hook in v if hook and hook.strip()))
        if not hooks:
            raise ValueError("At least one valid hook must be specified")
        return hooks

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: Optional[str]) -> Optional[str]:
        """Validate version format (semver)."""
        if v and not re.match(r"^\d+\.\d+\.\d+(-[a-zA-Z0-9.-]+)?(\+[a-zA-Z0-9.-]+)?$", v):
            raise ValueError("Version must be in semver format (e.g., '1.0.0', '1.0.0-beta', '1.0.0+build')")
        return v


# ============================================================================
# Tool Configuration Model (Enhanced)
# ============================================================================


class ToolConfig(BaseConfig):
    """Enhanced tool configuration with comprehensive validation.

    Supports OpenAPI tools, custom tools, and script-based tools.

    Attributes:
        openapi: OpenAPI specification version
        info: API information
        servers: API servers
        paths: API paths
        tool_type: Type of tool (openapi, curl, script)
        name: Tool name
        description: Tool description
        endpoint: Tool endpoint URL
        auth: Authentication configuration
        timeout: Request timeout in seconds
        enabled: Whether the tool is enabled

    Example:
        >>> # OpenAPI tool
        >>> openapi_tool = ToolConfig(
        ...     openapi="3.0.0",
        ...     info={"title": "My API", "version": "1.0.0"},
        ...     servers=[{"url": "https://api.example.com"}],
        ...     paths={"/users": {"get": {"summary": "List users"}}}
        ... )
        >>>
        >>> # Custom curl tool
        >>> curl_tool = ToolConfig(
        ...     tool_type="curl",
        ...     name="fetch-data",
        ...     description="Fetch data from API",
        ...     endpoint="https://api.example.com/data"
        ... )
    """

    model_config = ConfigDict(extra="allow")  # Allow extra fields for flexibility

    # OpenAPI fields
    openapi: Optional[str] = Field(None, description="OpenAPI specification version")
    info: Optional[Dict[str, Any]] = Field(None, description="API information")
    servers: Optional[List[Dict[str, Any]]] = Field(None, description="API servers")
    paths: Optional[Dict[str, Any]] = Field(None, description="API paths")

    # Custom tool fields
    tool_type: Optional[Literal["openapi", "curl", "script"]] = Field(
        None, description="Type of tool"
    )
    name: Optional[str] = Field(None, description="Tool name", min_length=1, max_length=255)
    description: Optional[str] = Field(None, description="Tool description", max_length=1000)
    endpoint: Optional[str] = Field(None, description="Tool endpoint URL")
    auth: Optional[Union[AuthConfig, Dict[str, Any]]] = Field(
        None, description="Authentication configuration"
    )
    timeout: Optional[int] = Field(30, ge=1, le=300, description="Request timeout in seconds")
    enabled: Optional[bool] = Field(True, description="Whether the tool is enabled")

    @field_validator("openapi")
    @classmethod
    def validate_openapi_version(cls, v: Optional[str]) -> Optional[str]:
        """Validate OpenAPI version format."""
        if v and not re.match(r"^\d+\.\d+(\.\d+)?$", v):
            raise ValueError("OpenAPI version must be in format X.Y or X.Y.Z")
        return v

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(cls, v: Optional[str]) -> Optional[str]:
        """Validate endpoint URL format."""
        if v and not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("Endpoint must be a valid HTTP(S) URL")
        return v

    @model_validator(mode="after")
    def validate_tool_requirements(self) -> ToolConfig:
        """Validate that required fields are present for each tool type."""
        # Convert auth dict to AuthConfig if needed
        if self.auth and isinstance(self.auth, dict):
            self.auth = AuthConfig.model_validate(self.auth)

        # Validate OpenAPI tools
        if self.openapi:
            if not self.paths:
                raise ValueError("OpenAPI tools require 'paths' field")

        # Validate custom tools
        if self.tool_type in ["curl", "script"]:
            if not self.name:
                raise ValueError(f"Tool type '{self.tool_type}' requires 'name' field")

        return self


# ============================================================================
# Prompt Configuration Model (Enhanced)
# ============================================================================


class PromptArgument(BaseConfig):
    """Prompt argument configuration.

    Attributes:
        name: Argument name
        type: Argument type (string, number, boolean, array, object)
        required: Whether argument is required
        description: Argument description
        default: Default value
        enum: Allowed values (for enum types)
        pattern: Regex pattern for validation
        min_length: Minimum length (for strings)
        max_length: Maximum length (for strings)
        minimum: Minimum value (for numbers)
        maximum: Maximum value (for numbers)

    Example:
        >>> arg = PromptArgument(
        ...     name="user_id",
        ...     type="string",
        ...     required=True,
        ...     description="User identifier",
        ...     pattern="^[a-zA-Z0-9-]+$"
        ... )
    """

    name: str = Field(..., description="Argument name", min_length=1, max_length=255)
    type: Literal["string", "number", "boolean", "array", "object"] = Field(
        ..., description="Argument type"
    )
    required: bool = Field(True, description="Whether argument is required")
    description: Optional[str] = Field(None, description="Argument description", max_length=1000)
    default: Optional[Any] = Field(None, description="Default value")
    enum: Optional[List[Any]] = Field(None, description="Allowed values")
    pattern: Optional[str] = Field(None, description="Regex pattern for validation")
    min_length: Optional[int] = Field(None, ge=0, description="Minimum length (for strings)")
    max_length: Optional[int] = Field(None, ge=1, description="Maximum length (for strings)")
    minimum: Optional[float] = Field(None, description="Minimum value (for numbers)")
    maximum: Optional[float] = Field(None, description="Maximum value (for numbers)")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate argument name format."""
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", v):
            raise ValueError("Argument name must be a valid identifier (start with letter/underscore)")
        return v

    @field_validator("pattern")
    @classmethod
    def validate_pattern(cls, v: Optional[str]) -> Optional[str]:
        """Validate that pattern is a valid regex."""
        if v:
            try:
                re.compile(v)
            except re.error as e:
                raise ValueError(f"Invalid regex pattern: {e}")
        return v


class PromptConfig(BaseConfig):
    """Enhanced prompt configuration with comprehensive validation.

    Attributes:
        name: Unique name for the prompt
        description: Prompt description
        template: Prompt template with placeholders
        arguments: Prompt arguments
        enabled: Whether the prompt is enabled
        tags: Tags for categorization
        version: Prompt version
        examples: Example usages

    Example:
        >>> prompt = PromptConfig(
        ...     name="user-greeting",
        ...     description="Generate a personalized greeting",
        ...     template="Hello {{name}}, welcome to {{service}}!",
        ...     arguments=[
        ...         PromptArgument(name="name", type="string", required=True),
        ...         PromptArgument(name="service", type="string", required=True)
        ...     ],
        ...     tags=["greeting", "user"]
        ... )
    """

    name: str = Field(..., description="Unique name for the prompt", min_length=1, max_length=255)
    description: str = Field(..., description="Prompt description", min_length=1, max_length=1000)
    template: str = Field(..., description="Prompt template", min_length=1)
    arguments: Optional[List[PromptArgument]] = Field(None, description="Prompt arguments")
    enabled: Optional[bool] = Field(True, description="Whether the prompt is enabled")
    tags: Optional[List[str]] = Field(None, description="Tags for categorization")
    version: Optional[str] = Field("1.0.0", description="Prompt version")
    examples: Optional[List[Dict[str, Any]]] = Field(None, description="Example usages")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate prompt name format."""
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError(
                "Prompt name must contain only alphanumeric characters, hyphens, and underscores"
            )
        return v

    @field_validator("template")
    @classmethod
    def validate_template(cls, v: str) -> str:
        """Validate that template contains valid placeholders."""
        # Check for balanced braces
        if v.count("{{") != v.count("}}"):
            raise ValueError("Template has unbalanced placeholder braces")
        return v

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Validate and normalize tags."""
        if v:
            return list(set(tag.strip() for tag in v if tag and tag.strip()))
        return v

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: Optional[str]) -> Optional[str]:
        """Validate version format (semver)."""
        if v and not re.match(r"^\d+\.\d+\.\d+(-[a-zA-Z0-9.-]+)?(\+[a-zA-Z0-9.-]+)?$", v):
            raise ValueError("Version must be in semver format")
        return v


# ============================================================================
# Resource Configuration Model (Enhanced)
# ============================================================================


class ResourceConfig(BaseConfig):
    """Enhanced resource configuration with comprehensive validation.

    Attributes:
        name: Unique name for the resource
        description: Resource description
        uri: Resource URI (for static resources)
        uri_template: Resource URI template (for dynamic resources)
        text: Resource content/text
        template: Template content (alias for text)
        mime_type: MIME type of the resource
        tags: Tags for categorization
        enabled: Whether the resource is enabled
        parameters: Template parameters
        cache_ttl: Cache time-to-live in seconds
        version: Resource version

    Example:
        >>> # Static resource
        >>> resource = ResourceConfig(
        ...     name="api-docs",
        ...     description="API documentation",
        ...     uri="resource://docs/api.md",
        ...     text="# API Documentation\\n...",
        ...     mime_type="text/markdown",
        ...     tags=["documentation"]
        ... )
        >>>
        >>> # Dynamic resource template
        >>> template_resource = ResourceConfig(
        ...     name="user-profile",
        ...     description="User profile template",
        ...     uri_template="resource://users/{user_id}/profile",
        ...     template="User: {{name}}\\nEmail: {{email}}",
        ...     parameters={"user_id": "string"},
        ...     mime_type="text/plain"
        ... )
    """

    name: str = Field(..., description="Unique name for the resource", min_length=1, max_length=255)
    description: Optional[str] = Field(None, description="Resource description", max_length=1000)
    uri: Optional[str] = Field(None, description="Resource URI (for static resources)")
    uri_template: Optional[str] = Field(None, description="Resource URI template (for dynamic resources)")
    text: Optional[str] = Field(None, description="Resource content/text")
    template: Optional[str] = Field(None, description="Template content (alias for text)")
    mime_type: Optional[str] = Field("text/plain", description="MIME type of the resource")
    tags: Optional[List[str]] = Field(None, description="Tags for categorization")
    enabled: Optional[bool] = Field(True, description="Whether the resource is enabled")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Template parameters")
    cache_ttl: Optional[int] = Field(None, ge=0, le=86400, description="Cache TTL in seconds")
    version: Optional[str] = Field("1.0.0", description="Resource version")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate resource name format."""
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError(
                "Resource name must contain only alphanumeric characters, hyphens, and underscores"
            )
        return v

    @field_validator("uri", "uri_template")
    @classmethod
    def validate_uri_fields(cls, v: Optional[str]) -> Optional[str]:
        """Validate URI format."""
        if v and not v.strip():
            raise ValueError("URI/URI template cannot be empty string")
        return v.strip() if v else None

    @field_validator("mime_type")
    @classmethod
    def validate_mime_type(cls, v: Optional[str]) -> Optional[str]:
        """Validate MIME type format."""
        if v and "/" not in v:
            raise ValueError("MIME type must be in format 'type/subtype' (e.g., 'text/plain')")
        return v

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Validate and normalize tags."""
        if v:
            return list(set(tag.strip() for tag in v if tag and tag.strip()))
        return v

    @model_validator(mode="after")
    def validate_resource_requirements(self) -> ResourceConfig:
        """Validate resource configuration requirements."""
        # Must have either uri or uri_template
        if not self.uri and not self.uri_template:
            # Auto-generate URI if not provided
            self.uri = f"resource://{self.name}"

        # Cannot have both uri and uri_template
        if self.uri and self.uri_template:
            raise ValueError("Resource cannot have both 'uri' and 'uri_template'")

        # If uri_template is used, parameters should be provided
        if self.uri_template and not self.parameters:
            # Extract parameters from template
            import re

            params = re.findall(r"\{([^}]+)\}", self.uri_template)
            if params:
                self.parameters = {param: "string" for param in params}

        return self


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    # Base
    "BaseConfig",
    # Enums
    "ServerType",
    "AuthStrategy",
    "DatabaseType",
    "MiddlewareMode",
    # Configuration models
    "AuthConfig",
    "OpenAPIConfig",
    "GraphQLConfig",
    "ServerConfig",
    "DatabaseConfig",
    "MiddlewareConfig",
    "ToolConfig",
    "PromptArgument",
    "PromptConfig",
    "ResourceConfig",
]

# Made with Bob
