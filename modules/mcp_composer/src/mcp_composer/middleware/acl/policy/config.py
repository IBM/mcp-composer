"""
Configuration settings for MCP Composer Policy Enforcement using pydantic-settings.

All settings can be configured via environment variables with sensible defaults.
Inspired by permit-fastmcp's comprehensive configuration approach.
"""

from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from enum import Enum


class IdentityMode(str, Enum):
    """Identity extraction modes."""

    jwt = "jwt"
    fixed = "fixed"
    header = "header"
    source = "source"
    api_key = "api_key"


class PolicyMode(str, Enum):
    """Policy enforcement modes."""

    file = "file"
    vault = "vault"
    opa = "opa"
    jwt = "jwt"
    permit = "permit"
    optimized = "optimized"


class Settings(BaseSettings):
    """Configuration settings for MCP Composer Policy Enforcement.

    All settings can be configured via environment variables with the prefix MCP_POLICY_.
    """

    model_config = SettingsConfigDict(
        env_prefix="MCP_POLICY_",
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="allow",
    )

    # Policy enforcement mode
    mode: PolicyMode = PolicyMode.optimized

    # Methods recognized for resource/action mapping
    known_methods: List[str] = [
        "tools/list",
        "prompts/list",
        "resources/list",
        "tools/call",
        "resources/read",
        "prompts/get",
    ]

    # Methods that bypass authorization checks
    bypassed_methods: List[str] = [
        "initialize",
        "ping",
        "notifications/*",
        "health/*",
    ]

    # Prefix for action mapping
    action_prefix: str = ""
    # Prefix for resource mapping
    resource_prefix: str = "mcp_"

    # Name of the MCP server, used as resource name for tool calls
    mcp_server_name: str = "mcp_composer"

    # Enable or disable audit logging
    enable_audit_logging: bool = True
    # Enable or disable metrics collection
    enable_metrics: bool = True

    # Identity extraction mode
    identity_mode: IdentityMode = IdentityMode.fixed
    # Header to extract identity from (for 'jwt' and 'header' modes)
    identity_header: str = r"[Aa]uthorization (.+)"  # "Authorization/authorization "
    # Regex to extract token from header (for 'jwt' mode)
    identity_header_regex: str = r"[Bb]earer (.+)"
    # JWT secret or public key (for 'jwt' mode)
    identity_jwt_secret: str = ""
    # JWT field to use as identity (for 'jwt' mode)
    identity_jwt_field: str = "sub"
    # Fixed identity value (for 'fixed' mode)
    identity_fixed_value: str = "client"
    # API key header (for 'api_key' mode)
    api_key_header: str = "X-API-Key"

    # Allowed JWT algorithms (for 'jwt' mode)
    jwt_algorithms: List[str] = ["HS256", "RS256"]

    # Whether to prefix resources with the MCP server name
    prefix_resource_with_server_name: bool = True

    # Whether to flatten tool arguments as individual attributes with prefix
    flatten_tool_arguments: bool = True
    # Prefix for flattened tool argument attributes
    tool_argument_prefix: str = "arg_"

    # Policy file path (for 'file' mode)
    policy_file_path: str = "policy.json"
    # Policy directory path (for 'file' mode)
    policy_directory_path: str = "policies/"

    # Vault configuration (for 'vault' mode)
    vault_url: str = "http://localhost:8200"
    vault_token: str = ""
    vault_mount_point: str = "secret"
    vault_policy_path: str = "mcp-policies"

    # OPA configuration (for 'opa' mode)
    opa_url: str = "http://localhost:8181"
    opa_policy_path: str = "mcp/allow"
    opa_timeout: float = 10.0
    opa_verify_ssl: bool = True

    # Permit.io configuration (for 'permit' mode)
    permit_url: str = "https://cloud.permit.io"
    permit_api_key: str = ""

    # Default user role when no role is found
    default_user_role: str = "user"

    # Cache settings
    enable_policy_caching: bool = True
    policy_cache_ttl: int = 300  # seconds

    # Rate limiting settings
    enable_rate_limiting: bool = False
    rate_limit_requests: int = 100
    rate_limit_window: int = 3600  # seconds

    # Logging settings
    log_level: str = "INFO"
    log_format: str = "json"

    # Performance settings
    max_concurrent_evaluations: int = 100
    evaluation_timeout: float = 5.0  # seconds


# Global settings instance
SETTINGS = Settings()
