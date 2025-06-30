from typing import Dict, Any, List
from enum import Enum


class ConfigKey(str, Enum):
    TYPE = "type"
    ENDPOINT = "endpoint"
    SPEC_URL = "spec_url"
    SPEC_FILEPATH = "spec_filepath"
    AUTH_STRATEGY = "auth_strategy"
    AUTH = "auth"
    APIKEY = "apikey"
    ID = "id"
    OPEN_API = "open_api"
    CUSTOM_ROUTES = "custom_routes"
    Token_URL = "token_url"
    AUTH_HEADER = "Authorization"
    TOKEN = "token"
    AUTH_PREFIX = "auth_prefix"
    HEADERS = "headers"
    JSESSIONID = "JSESSIONID"
    USERNAME = "username"
    PASSWORD = "password"
    LOGIN_URL = "login_url"
    TOKEN_TYPE = "token_type"


class MemberServerType(str, Enum):
    OpenAPI = "openapi"
    Client = "client"


class AuthStrategy(str, Enum):
    OAUTH = "oauth2"
    APIKEY = "apikey"
    BEARER = "bearer"
    DYNAMIC_BEARER = "dynamic_bearer"
    APITOKEN = "apiToken"
    JSESSIONID = "jessionid"


class ValidationError(Exception):
    """Custom exception for validation errors."""

    pass


class ServerConfigValidator:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.server_id = config.get(ConfigKey.ID, "<unknown>")

    def validate(self) -> None:
        """Run all validation checks."""
        if ConfigKey.AUTH_STRATEGY in self.config:
            self._validate_auth_dependency()
        if self.config.get(ConfigKey.TYPE) == MemberServerType.OpenAPI:
            self._validate_openapi_requirements()
        self._validate_client_requirements()

    def _validate_auth_dependency(self) -> None:
        """Ensure 'auth' exists if 'auth_strategy' is defined."""
        if ConfigKey.AUTH_STRATEGY in self.config and ConfigKey.AUTH not in self.config:
            raise ValidationError(
                f"Missing {ConfigKey.AUTH} for server with id '{self.server_id}'"
            )
        auth = self.config[ConfigKey.AUTH]
        strategy = self.config[ConfigKey.AUTH_STRATEGY].lower()

        required_auth_keys = {
            AuthStrategy.APIKEY: ["apikey"],
            AuthStrategy.BEARER: ["token"],
            AuthStrategy.DYNAMIC_BEARER: ["apikey", "token_url"],
            AuthStrategy.OAUTH: ["client_id", "client_secret", "token_url"],
        }

        # Check if strategy is supported
        if strategy not in required_auth_keys:
            raise ValidationError(
                f"Unsupported {ConfigKey.AUTH_STRATEGY} '{strategy}' for server '{self.server_id}'"
            )

        # Find missing keys
        missing = [key for key in required_auth_keys[strategy] if not auth.get(key)]
        if missing:
            raise ValidationError(
                f"Missing field(s) in {ConfigKey.AUTH} for '{strategy}' strategy on server '{self.server_id}': {', '.join(missing)}"
            )

    def _validate_openapi_requirements(self) -> None:
        """Ensure 'endpoint' and 'openapi_url' exist if type is 'openapi'."""
        if self.config.get(ConfigKey.TYPE) != MemberServerType.OpenAPI:
            return  # nothing to validate

        openapi_config = self.config.get(ConfigKey.OPEN_API, {})
        if not openapi_config:
            raise ValueError(
                f"Missing required {ConfigKey.OPEN_API} section in config."
            )

        # Required field: endpoint
        if not openapi_config.get(ConfigKey.ENDPOINT):
            raise ValueError(
                f"Missing required field: {ConfigKey.ENDPOINT} in {ConfigKey.OPEN_API}'"
            )

        # Must have exactly one of 'spec_url' or 'spec_filepath'
        spec_keys = [ConfigKey.SPEC_URL, ConfigKey.SPEC_FILEPATH]
        present_specs = [k for k in spec_keys if openapi_config.get(k)]
        if len(present_specs) != 1:
            raise ValueError(
                f"Exactly one of {ConfigKey.SPEC_URL} or {ConfigKey.SPEC_FILEPATH} must be provided in {ConfigKey.OPEN_API}."
            )

    def _validate_client_requirements(self) -> None:
        if (
            self.config.get(ConfigKey.TYPE) == MemberServerType.Client
            and ConfigKey.ENDPOINT not in self.config
        ):
            raise ValidationError(
                f"Missing {ConfigKey.ENDPOINT} for {MemberServerType.Client} type in server '{self.server_id}'"
            )


class AllServersValidator:
    def __init__(self, server: List[Dict[str, Any]]):
        self.server = server

    def validate_all(self) -> None:
        for config in self.server:
            validator = ServerConfigValidator(config)
            validator.validate()
