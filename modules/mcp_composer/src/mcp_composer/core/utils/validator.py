from typing import Dict, Any, List
from enum import Enum
from mcp_composer.core.utils.logger import LoggerFactory

logger = LoggerFactory.get_logger()


class ConfigKey(str, Enum):
    """Keys used in the server configuration."""

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
    TOKEN_URL_WITH_ORG = "token_url_with_org"
    AUTH_HEADER = "Authorization"
    TOKEN = "token"
    AUTH_PREFIX = "auth_prefix"
    HEADERS = "headers"
    JSESSIONID = "JSESSIONID"
    USERNAME = "username"
    PASSWORD = "password"
    LOGIN_URL = "login_url"
    RETURN_URL = "return_url"
    TOKEN_TYPE = "token_type"
    TOKEN_GEN_AUTH_METHOD = "token_gen_auth_method"
    TOKEN_GEN_METHOD = "token_gen_method"
    SECRET = "secret"
    MEDIA_TYPE = "media_type"
    MEDIA_TYPE_JSON = "json"
    # OAuth configuration keys
    CLIENT_ID = "clientId"
    CLIENT_SECRET = "clientSecret"
    REFRESH_TOKEN = "refreshToken"
    SCOPE = "scope"
    GRAPHQL = "graphql"
    SCHEMA_FILEPATH = "schema_filepath"
    PROMPT_PATH = "prompt_path"
    COMMAND = "command"
    ARGS = "args"
    ENV = "env"
    CWD = "cwd"
    LAYERED = "layered"
    CERT_VALUE = "cert_private_key"
    CERT_URL = "cert_url"
    USER_EMAIL = "user_email"

    USER_PASSWORD = "user_password"




class MemberServerType(str, Enum):
    """Types of member servers."""

    OPENAPI = "openapi"
    CLIENT = "client"
    GRAPHQL = "graphql"
    LOCAL = "local"
    HTTP = "http"
    SSE = "sse"
    STDIO = "stdio"


class AuthStrategy(str, Enum):
    """Authentication strategies for member servers."""

    BASIC = "basic"
    OAUTH = "oauth2"
    APIKEY = "apikey"
    BEARER = "bearer"
    DYNAMIC_BEARER = "dynamic_bearer"
    APITOKEN = "apiToken"
    JSESSIONID = "jessionid"
    ASPERA_OAUTH_HANDLER = "aspera_oauth_handler"
    SOLIS_JWT_HANDLER = "solis_jwt_handler"



class ValidationError(Exception):
    """Custom exception for validation errors."""


class ServerConfigValidator:
    """Validator for individual server configurations."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.server_id = config.get(ConfigKey.ID, "<unknown>")

    def validate(self) -> None:
        """Run all validation checks."""
        logger.info("Validating server '%s'", self.server_id)

        if ConfigKey.AUTH_STRATEGY in self.config:
            self._validate_auth_dependency()
        if self.config.get(ConfigKey.TYPE) == MemberServerType.OPENAPI:
            logger.info("Validating OpenAPI server '%s'", self.server_id)
            self._validate_openapi_requirements()
        elif self.config.get(ConfigKey.TYPE) in {
            MemberServerType.HTTP,
            MemberServerType.SSE,
        }:
            logger.info("Validating HTTP/SSE server '%s'", self.server_id)
            self._validate_client_requirements()
        elif self.config.get(ConfigKey.TYPE) == MemberServerType.STDIO:
            logger.info("Validating stdio server '%s'", self.server_id)
            self._validate_stdio_requirements()
        else:
            logger.warning(
                "Skipping validation for unsupported type: %s",
                self.config.get(ConfigKey.TYPE),
            )

    def _has_any_key(self, auth: Dict[str, Any], *keys: str) -> bool:
        """Check if any of the provided keys exist in auth dict."""
        return any(auth.get(key) for key in keys)

    def _validate_stdio_requirements(self) -> None:
        """Ensure required fields exist for stdio type."""

        if self.config.get(ConfigKey.TYPE) != MemberServerType.STDIO:
            return

        # Check for required fields: command and args
        missing = []
        if not self.config.get(ConfigKey.COMMAND):
            missing.append(ConfigKey.COMMAND)
        if not self.config.get(ConfigKey.ARGS):
            missing.append(ConfigKey.ARGS)
        if missing:
            raise ValidationError(
                f"Missing required field(s) for stdio server '{self.server_id}': {', '.join(missing)}"
            )

    def _validate_auth_dependency(self) -> None:
        """Ensure 'auth' exists if 'auth_strategy' is defined."""
        if ConfigKey.AUTH_STRATEGY in self.config and ConfigKey.AUTH not in self.config:
            raise ValidationError(
                f"Missing {ConfigKey.AUTH} for server with id '{self.server_id}'"
            )
        auth = self.config[ConfigKey.AUTH]
        strategy = self.config[ConfigKey.AUTH_STRATEGY].lower()

        required_auth_keys = {
            AuthStrategy.BASIC: ["basic"],
            AuthStrategy.APIKEY: ["apikey"],
            AuthStrategy.APITOKEN.lower(): ["token"],
            AuthStrategy.BEARER: ["token"],
            AuthStrategy.DYNAMIC_BEARER: ["apikey", "token_url", "id", "secret"],
            AuthStrategy.OAUTH: ["client_id", "client_secret", "token_url"],
            AuthStrategy.ASPERA_OAUTH_HANDLER: ["client_id", "secret", ConfigKey.CERT_VALUE, "token_url"],
            AuthStrategy.SOLIS_JWT_HANDLER: ["login_url", "return_url", "user_email", "password"],
        }

        # Check if strategy is supported
        if strategy not in required_auth_keys:
            raise ValidationError(
                f"Unsupported {ConfigKey.AUTH_STRATEGY} '{strategy}' for server '{self.server_id}'"
            )
        # Special logic for dynamic_bearer
        if strategy == AuthStrategy.DYNAMIC_BEARER:
            has_apikey = bool(auth.get(ConfigKey.APIKEY))
            has_id_secret = bool(auth.get("id")) and bool(auth.get("secret"))
            has_token_url = bool(auth.get(ConfigKey.Token_URL))
            if not has_token_url:
                missing = [ConfigKey.Token_URL]
            elif not (has_apikey or has_id_secret):
                missing = ["apikey or (id and secret)"]
            else:
                missing = []
        # Special logic for aspera_oauth_handler - check for clientId or client_id, and secret or clientSecret
        elif strategy == AuthStrategy.ASPERA_OAUTH_HANDLER:
            has_client_id = bool(auth.get(ConfigKey.CLIENT_ID) or auth.get("client_id"))
            has_secret = bool(
                auth.get(ConfigKey.SECRET)
                or auth.get("secret")
                or auth.get(ConfigKey.CLIENT_SECRET)
                or auth.get("clientSecret")
            )
            has_cert = bool(auth.get(ConfigKey.CERT_VALUE) )
            has_token_url = bool(auth.get(ConfigKey.Token_URL) )
            missing = []
            if not has_client_id:
                missing.append("clientId or client_id")
            if not has_secret:
                missing.append("secret or clientSecret")
            if not has_cert:
                missing.append(ConfigKey.CERT_VALUE)
            if not has_token_url:
                missing.append("token_url")
        elif strategy == AuthStrategy.SOLIS_JWT_HANDLER:
            missing = []

            # Check login_url (supports multiple case variations)
            if not self._has_any_key(auth, ConfigKey.LOGIN_URL):
                missing.append("login_url")

            # Check return_url (supports multiple case variations)
            if not self._has_any_key(auth, ConfigKey.RETURN_URL):
                missing.append("return_url")

            # Email can be provided directly or via email_var (for environment variable)
            # Support both USER_EMAIL and email for backward compatibility
            has_email = self._has_any_key(auth, ConfigKey.USER_EMAIL, "email")
            if not (has_email):
                missing.append("user_email (or email)")

            # Password can be provided directly or via password_var (for environment variable)
            # Support both USER_PASSWORD, PASSWORD, and password for backward compatibility
            has_password = self._has_any_key(
                auth, ConfigKey.USER_PASSWORD, ConfigKey.PASSWORD, "password"
            )
            if not (has_password):
                missing.append("user_password (or password)")
        else:
            missing = [
                key
                for key in required_auth_keys[strategy]
                if not auth.get(key) and strategy != AuthStrategy.BASIC
            ]

        if missing:
            raise ValidationError(
                f"Missing field(s) in {ConfigKey.AUTH} for '{strategy}' strategy on server "
                f"'{self.server_id}': {', '.join(missing)}"
            )

    def _validate_openapi_requirements(self) -> None:
        """Ensure 'endpoint' and 'openapi_url' exist if type is 'openapi'."""
        if self.config.get(ConfigKey.TYPE) != MemberServerType.OPENAPI:
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
                f"Exactly one of {ConfigKey.SPEC_URL} or {ConfigKey.SPEC_FILEPATH} must be "
                f"provided in {ConfigKey.OPEN_API}."
            )

    def _validate_client_requirements(self) -> None:
        """Ensure 'endpoint' exists if type is 'client'."""
        logger.debug("Validating client requirements for server '%s'", self.server_id)
        if (
            self.config.get(ConfigKey.TYPE) == MemberServerType.CLIENT
            and ConfigKey.ENDPOINT not in self.config
        ):
            raise ValidationError(
                f"Missing {ConfigKey.ENDPOINT} for {MemberServerType.CLIENT} type in server '{self.server_id}'"
            )

    def validate_graphql_config(self) -> None:
        """Ensure required fields exist if type is 'graphql'."""
        if self.config.get(ConfigKey.TYPE) != MemberServerType.GRAPHQL:
            return

        graphql_config = self.config.get(ConfigKey.GRAPHQL)
        if not graphql_config:
            raise ValidationError(
                f"Missing required {ConfigKey.GRAPHQL} section in config."
            )

        required_fields = [ConfigKey.ENDPOINT, ConfigKey.SCHEMA_FILEPATH]
        missing = [field for field in required_fields if not graphql_config.get(field)]
        if missing:
            raise ValidationError(
                f"Missing required field(s) in {ConfigKey.GRAPHQL}: {', '.join(missing)}"
            )



class AllServersValidator:
    """Validator for a list of server configurations."""

    def __init__(self, server: List[Dict[str, Any]]):
        self.server = server

    def validate_all(self) -> None:
        for config in self.server:
            validator = ServerConfigValidator(config)
            validator.validate()
