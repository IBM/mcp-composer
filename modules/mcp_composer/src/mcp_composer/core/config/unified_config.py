"""Unified configuration schema for MCP Composer."""

from typing import Any
from pydantic import BaseModel, Field, field_validator, ConfigDict
from enum import Enum


class ConfigSection(str, Enum):
    """Configuration sections that can be loaded."""

    SERVERS = "servers"
    MIDDLEWARE = "middleware"
    PROMPTS = "prompts"
    TOOLS = "tools"
    RESOURCES = "resources"
    ALL = "all"


class ServerConfig(BaseModel):
    """Server configuration schema."""

    id: str = Field(..., description="Unique identifier for the server")
    type: str = Field(..., description="Server type (http, sse, openapi, stdio, etc.)")
    endpoint: str | None = Field(None, description="Server endpoint URL")
    open_api: dict[str, Any] | None = Field(None, description="OpenAPI configuration")
    auth_strategy: str | None = Field(None, description="Authentication strategy")
    auth: dict[str, Any] | None = Field(
        None, description="Authentication configuration"
    )
    command: str | None = Field(None, description="Command for stdio servers")
    args: list[str] | None = Field(
        None, description="Command arguments for stdio servers"
    )
    env: dict[str, str] | None = Field(None, description="Environment variables")
    cwd: str | None = Field(None, description="Working directory")
    label: str | None = Field(None, description="Human-readable label")
    tags: list[str] | None = Field(None, description="Tags for categorization")

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Server ID cannot be empty")
        return v.strip()

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        valid_types = ["http", "sse", "openapi", "stdio", "graphql", "local", "client"]
        if v not in valid_types:
            raise ValueError(
                f"Invalid server type '{v}'. Must be one of: {', '.join(valid_types)}"
            )
        return v


class MiddlewareConfig(BaseModel):
    """Middleware configuration schema."""

    name: str = Field(..., description="Unique name for the middleware")
    kind: str = Field(..., description="Python import path to middleware class")
    mode: str = Field("enabled", description="Middleware mode (enabled/disabled)")
    priority: int = Field(100, ge=0, le=10000, description="Execution priority")
    applied_hooks: list[str] = Field(
        ..., description="Hooks where middleware is applied"
    )
    config: dict[str, Any] | None = Field(
        None, description="Middleware-specific configuration"
    )
    description: str | None = Field(None, description="Middleware description")
    version: str | None = Field("0.0.0", description="Middleware version")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Middleware name cannot be empty")
        return v.strip()

    @field_validator("kind")
    @classmethod
    def validate_kind(cls, v: str) -> str:
        if "." not in v:
            raise ValueError("Kind must be 'module.Class' (import path + class name)")
        return v

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        if v not in ["enabled", "disabled"]:
            raise ValueError("Mode must be 'enabled' or 'disabled'")
        return v


class PromptArgument(BaseModel):
    """Prompt argument schema."""

    name: str = Field(..., description="Argument name")
    type: str = Field(..., description="Argument type")
    required: bool = Field(True, description="Whether argument is required")
    description: str | None = Field(None, description="Argument description")


class PromptConfig(BaseModel):
    """Prompt configuration schema."""

    name: str = Field(..., description="Unique name for the prompt")
    description: str = Field(..., description="Prompt description")
    template: str = Field(..., description="Prompt template")
    arguments: list[PromptArgument] | None = Field(None, description="Prompt arguments")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Prompt name cannot be empty")
        return v.strip()

    @field_validator("template")
    @classmethod
    def validate_template(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Prompt template cannot be empty")
        return v.strip()


class ToolConfig(BaseModel):
    """Tool configuration schema."""

    model_config = ConfigDict(extra="allow")

    openapi: str | None = Field(None, description="OpenAPI specification version")
    info: dict[str, Any] | None = Field(None, description="API information")
    servers: list[dict[str, Any]] | None = Field(None, description="API servers")
    paths: dict[str, Any] | None = Field(None, description="API paths")


class ResourceConfig(BaseModel):
    """Resource configuration schema."""

    name: str = Field(..., description="Unique name for the resource")
    description: str | None = Field(default=None, description="Resource description")
    uri: str | None = Field(
        default=None, description="Resource URI (for static resources)"
    )
    uri_template: str | None = Field(
        default=None, description="Resource URI template (for dynamic resources)"
    )
    text: str | None = Field(default=None, description="Resource content/text")
    template: str | None = Field(
        default=None, description="Template content (alias for text)"
    )
    mime_type: str | None = Field(
        default="text/plain", description="MIME type of the resource"
    )
    tags: list[str] | None = Field(default=None, description="Tags for categorization")
    enabled: bool | None = Field(
        default=True, description="Whether the resource is enabled"
    )
    parameters: dict[str, Any] | None = Field(
        default=None, description="Template parameters"
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Resource name cannot be empty")
        return v.strip()

    @field_validator("uri", "uri_template")
    @classmethod
    def validate_uri_fields(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("URI/URI template cannot be empty string")
        return v.strip() if v else None

    def model_post_init(self, __context) -> None:
        """Validate that either uri or uri_template is provided."""
        if not self.uri and not self.uri_template:
            # Auto-generate URI if not provided
            self.uri = f"resource://{self.name}"


class UnifiedConfig(BaseModel):
    """Unified configuration schema for MCP Composer."""

    servers: list[ServerConfig] | None = Field(
        None, description="List of server configurations"
    )
    middleware: list[MiddlewareConfig] | None = Field(
        None, description="List of middleware configurations"
    )
    prompts: list[PromptConfig] | None = Field(
        None, description="List of prompt configurations"
    )
    tools: dict[str, ToolConfig] | None = Field(
        None, description="Dictionary of tool configurations"
    )
    resources: list[ResourceConfig] | None = Field(
        None, description="List of resource configurations"
    )

    @field_validator("servers")
    @classmethod
    def validate_servers(
        cls, v: list[ServerConfig] | None
    ) -> list[ServerConfig] | None:
        if v is not None:
            # Check for duplicate server IDs
            server_ids = [server.id for server in v]
            if len(server_ids) != len(set(server_ids)):
                raise ValueError("Duplicate server IDs found")
        return v

    @field_validator("middleware")
    @classmethod
    def validate_middleware(
        cls, v: list[MiddlewareConfig] | None
    ) -> list[MiddlewareConfig] | None:
        if v is not None:
            # Check for duplicate middleware names
            middleware_names = [mw.name for mw in v]
            if len(middleware_names) != len(set(middleware_names)):
                raise ValueError("Duplicate middleware names found")
        return v

    @field_validator("prompts")
    @classmethod
    def validate_prompts(
        cls, v: list[PromptConfig] | None
    ) -> list[PromptConfig] | None:
        if v is not None:
            # Check for duplicate prompt names
            prompt_names = [prompt.name for prompt in v]
            if len(prompt_names) != len(set(prompt_names)):
                raise ValueError("Duplicate prompt names found")
        return v

    @field_validator("resources")
    @classmethod
    def validate_resources(
        cls, v: list[ResourceConfig] | None
    ) -> list[ResourceConfig] | None:
        if v is not None:
            # Check for duplicate resource names
            resource_names = [resource.name for resource in v]
            if len(resource_names) != len(set(resource_names)):
                raise ValueError("Duplicate resource names found")
        return v


class ConfigValidationError(Exception):
    """Exception raised when configuration validation fails."""

    pass


class UnifiedConfigValidator:
    """Validator for unified configuration."""

    def __init__(self, config: dict[str, Any] | UnifiedConfig):
        if isinstance(config, dict):
            self.config = UnifiedConfig.model_validate(config)
        else:
            self.config = config

    def validate(self) -> None:
        """Validate the unified configuration."""
        try:
            # Pydantic validation is already done in __init__
            # Additional custom validations can be added here
            self._validate_servers()
            self._validate_middleware()
            self._validate_prompts()
            self._validate_tools()
            self._validate_resources()
        except Exception as e:
            raise ConfigValidationError(
                f"Configuration validation failed: {str(e)}"
            ) from e

    def _validate_servers(self) -> None:
        """Validate server configurations."""
        if not self.config.servers:
            return

        for server in self.config.servers:
            # Validate required fields based on server type
            if server.type in ["http", "sse"]:
                if not server.endpoint:
                    raise ConfigValidationError(
                        f"Server '{server.id}' of type '{server.type}' requires 'endpoint' field"
                    )
            elif server.type == "openapi":
                if not server.open_api:
                    raise ConfigValidationError(
                        f"Server '{server.id}' of type 'openapi' requires 'open_api' field"
                    )
                if not server.open_api.get("endpoint"):
                    raise ConfigValidationError(
                        f"Server '{server.id}' of type 'openapi' requires 'endpoint' in 'open_api' field"
                    )
            elif server.type == "stdio":
                if not server.command:
                    raise ConfigValidationError(
                        f"Server '{server.id}' of type 'stdio' requires 'command' field"
                    )

    def _validate_middleware(self) -> None:
        """Validate middleware configurations."""
        if not self.config.middleware:
            return

        for middleware in self.config.middleware:
            if not middleware.applied_hooks:
                raise ConfigValidationError(
                    f"Middleware '{middleware.name}' requires 'applied_hooks' field"
                )

    def _validate_prompts(self) -> None:
        """Validate prompt configurations."""
        if not self.config.prompts:
            return

        for prompt in self.config.prompts:
            if not prompt.description:
                raise ConfigValidationError(
                    f"Prompt '{prompt.name}' requires 'description' field"
                )

    def _validate_tools(self) -> None:
        """Validate tool configurations."""
        if not self.config.tools:
            return

        for tool_name, tool_config in self.config.tools.items():
            if not tool_name or not tool_name.strip():
                raise ConfigValidationError("Tool names cannot be empty")

            # Additional tool-specific validation can be added here
            if hasattr(tool_config, "openapi") and tool_config.openapi:
                if not hasattr(tool_config, "paths") or not tool_config.paths:
                    raise ConfigValidationError(
                        f"Tool '{tool_name}' with OpenAPI specification requires 'paths' field"
                    )

    def _validate_resources(self) -> None:
        """Validate resource configurations."""
        if not self.config.resources:
            return

        for resource in self.config.resources:
            # Handle both dict and object formats
            if isinstance(resource, dict):
                resource_uri = resource.get("uri")
                resource_uri_template = resource.get("uri_template")
                resource_name = resource.get("name", "unknown")
                resource_mime_type = resource.get("mime_type")
            else:
                resource_uri = getattr(resource, "uri", None)
                resource_uri_template = getattr(resource, "uri_template", None)
                resource_name = getattr(resource, "name", "unknown")
                resource_mime_type = getattr(resource, "mime_type", None)

            # Validate that resource has either uri or uri_template
            if not resource_uri and not resource_uri_template:
                raise ConfigValidationError(
                    f"Resource '{resource_name}' must have either 'uri' or 'uri_template' field"
                )

            # Validate that resource doesn't have both uri and uri_template
            if resource_uri and resource_uri_template:
                raise ConfigValidationError(
                    f"Resource '{resource_name}' cannot have both 'uri' and 'uri_template' fields"
                )

            # Validate mime_type format
            if resource_mime_type and "/" not in resource_mime_type:
                raise ConfigValidationError(
                    f"Resource '{resource_name}' has invalid mime_type '{resource_mime_type}'. "
                    "Expected format: 'type/subtype' (e.g., 'text/plain', 'application/json')"
                )
