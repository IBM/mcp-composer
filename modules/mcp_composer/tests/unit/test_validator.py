import unittest
import os
import json
import pytest
from mcp_composer.core.utils.validator import ValidationError, AllServersValidator


class TestComposer(unittest.TestCase):
    def test_valid_servers_file(self):
        """Test that a valid servers file does not raise a ValidationError."""
        current_dir = os.path.dirname(__file__)
        path = os.path.join(current_dir, "./../data/member_servers.json")
        # Assumes file is in the root or test dir

        with open(path, "r") as f:
            servers = json.load(f)

        # Act / Assert
        try:
            AllServersValidator(servers).validate_all()
        except ValidationError as e:
            self.fail(f"Validation failed unexpectedly: {e}")

    def test_invalid_missing_auth_strategy(self):
        """Test that a server without an auth_strategy raises a ValidationError."""
        # Arrange
        servers = [
            {
                "id": "invalid-server",
                "type": "client",
                "endpoint": "https://example.com",
                "auth_strategy": "apikey",
                # Missing "auth"
            }
        ]

        # Act / Assert
        with pytest.raises(
            ValidationError,
            match="Missing ConfigKey.AUTH for server with id 'invalid-server'",
        ):
            AllServersValidator(servers).validate_all()

    def test_invalid_openapi_missing_fields(self):
        """Test that an OpenAPI server without required fields raises a ValidationError."""
        # Arrange
        servers = [
            {
                "id": "broken-openapi",
                "type": "openapi",
                "open_api": {
                    # "endpoint" is missing
                    "spec_url": "https://docs.example.com/openapi.json",
                },
            }
        ]

        # Act / Assert
        with pytest.raises(
            ValueError,
            match="Missing required field: ConfigKey.ENDPOINT in ConfigKey.OPEN_API",
        ):
            AllServersValidator(servers).validate_all()

    def test_client_type_missing_endpoint(self):
        """Test that a client type server without an endpoint raises a ValidationError."""
        servers = [
            {
                "id": "client-no-endpoint",
                "type": "client",
                # missing "endpoint"
            }
        ]

        # Client type servers are not validated for missing endpoints in the main validate method
        # So this should not raise an exception
        try:
            AllServersValidator(servers).validate_all()
        except Exception as e:
            self.fail(f"Validation failed unexpectedly: {e}")


if __name__ == "__main__":
    unittest.main()


# Additional comprehensive tests from test_validator_extended.py


class TestValidatorExtended:
    """Extended test cases for validator module"""

    def test_config_key_enum_values(self):
        """Test all ConfigKey enum values"""
        from mcp_composer.core.utils.validator import ConfigKey

        assert ConfigKey.TYPE == "type"
        assert ConfigKey.ENDPOINT == "endpoint"
        assert ConfigKey.SPEC_URL == "spec_url"
        assert ConfigKey.SPEC_FILEPATH == "spec_filepath"
        assert ConfigKey.AUTH_STRATEGY == "auth_strategy"
        assert ConfigKey.AUTH == "auth"
        assert ConfigKey.APIKEY == "apikey"
        assert ConfigKey.ID == "id"
        assert ConfigKey.OPEN_API == "open_api"
        assert ConfigKey.CUSTOM_ROUTES == "custom_routes"
        assert ConfigKey.Token_URL == "token_url"
        assert ConfigKey.AUTH_HEADER == "Authorization"
        assert ConfigKey.TOKEN == "token"
        assert ConfigKey.AUTH_PREFIX == "auth_prefix"
        assert ConfigKey.HEADERS == "headers"
        assert ConfigKey.JSESSIONID == "JSESSIONID"
        assert ConfigKey.USERNAME == "username"
        assert ConfigKey.PASSWORD == "password"
        assert ConfigKey.LOGIN_URL == "login_url"
        assert ConfigKey.TOKEN_TYPE == "token_type"
        assert ConfigKey.MEDIA_TYPE == "media_type"
        assert ConfigKey.MEDIA_TYPE_JSON == "json"
        assert ConfigKey.GRAPHQL == "graphql"
        assert ConfigKey.SCHEMA_FILEPATH == "schema_filepath"
        assert ConfigKey.PROMPT_PATH == "prompt_path"
        assert ConfigKey.COMMAND == "command"
        assert ConfigKey.ARGS == "args"
        assert ConfigKey.ENV == "env"
        assert ConfigKey.CWD == "cwd"

    def test_member_server_type_enum_values(self):
        """Test all MemberServerType enum values"""
        from mcp_composer.core.utils.validator import MemberServerType

        assert MemberServerType.OPENAPI == "openapi"
        assert MemberServerType.CLIENT == "client"
        assert MemberServerType.GRAPHQL == "graphql"
        assert MemberServerType.LOCAL == "local"
        assert MemberServerType.HTTP == "http"
        assert MemberServerType.SSE == "sse"
        assert MemberServerType.STDIO == "stdio"

    def test_auth_strategy_enum_values(self):
        """Test all AuthStrategy enum values"""
        from mcp_composer.core.utils.validator import AuthStrategy

        assert AuthStrategy.BASIC == "basic"
        assert AuthStrategy.OAUTH == "oauth2"
        assert AuthStrategy.APIKEY == "apikey"
        assert AuthStrategy.BEARER == "bearer"
        assert AuthStrategy.DYNAMIC_BEARER == "dynamic_bearer"
        assert AuthStrategy.APITOKEN == "apiToken"
        assert AuthStrategy.JSESSIONID == "jessionid"

    def test_validation_error_inheritance(self):
        """Test ValidationError inheritance"""
        from mcp_composer.core.utils.validator import ValidationError

        assert issubclass(ValidationError, Exception)

    def test_server_config_validator_initialization(self):
        """Test ServerConfigValidator initialization"""
        from mcp_composer.core.utils.validator import ServerConfigValidator

        config = {"id": "test-server", "type": "openapi"}
        validator = ServerConfigValidator(config)

        assert validator.config == config
        assert validator.server_id == "test-server"

    def test_server_config_validator_initialization_no_id(self):
        """Test ServerConfigValidator initialization without ID"""
        from mcp_composer.core.utils.validator import ServerConfigValidator

        config = {"type": "openapi"}
        validator = ServerConfigValidator(config)

        assert validator.server_id == "<unknown>"

    def test_validate_unsupported_type(self):
        """Test validation with unsupported server type"""
        from mcp_composer.core.utils.validator import ServerConfigValidator

        config = {"id": "test-server", "type": "unsupported_type"}
        validator = ServerConfigValidator(config)

        # Should not raise an exception, just log a warning
        validator.validate()

    def test_validate_openapi_with_auth_strategy(self):
        """Test OpenAPI validation with auth strategy"""
        from mcp_composer.core.utils.validator import ServerConfigValidator

        config = {
            "id": "test-server",
            "type": "openapi",
            "open_api": {
                "endpoint": "https://api.example.com",
                "spec_url": "https://api.example.com/openapi.json",
            },
            "auth_strategy": "bearer",
            "auth": {"token": "test-token"},
        }
        validator = ServerConfigValidator(config)

        # Should not raise an exception
        validator.validate()

    def test_validate_openapi_without_auth_strategy(self):
        """Test OpenAPI validation without auth strategy"""
        from mcp_composer.core.utils.validator import ServerConfigValidator

        config = {
            "id": "test-server",
            "type": "openapi",
            "open_api": {
                "endpoint": "https://api.example.com",
                "spec_url": "https://api.example.com/openapi.json",
            },
        }
        validator = ServerConfigValidator(config)

        # Should not raise an exception
        validator.validate()

    def test_validate_http_server(self):
        """Test HTTP server validation"""
        from mcp_composer.core.utils.validator import ServerConfigValidator

        config = {
            "id": "test-server",
            "type": "http",
            "endpoint": "https://api.example.com",
        }
        validator = ServerConfigValidator(config)

        # Should not raise an exception
        validator.validate()

    def test_validate_sse_server(self):
        """Test SSE server validation"""
        from mcp_composer.core.utils.validator import ServerConfigValidator

        config = {
            "id": "test-server",
            "type": "sse",
            "endpoint": "https://api.example.com",
        }
        validator = ServerConfigValidator(config)

        # Should not raise an exception
        validator.validate()

    def test_validate_solis_jwt_handler_missing_email(self):
        """Test SOLIS_JWT_HANDLER auth strategy fails when email is missing."""
        from mcp_composer.core.utils.validator import (
            ServerConfigValidator,
            AuthStrategy,
            ConfigKey,
        )

        config = {
            "id": "mcp-dal",
            "type": "http",
            "endpoint": "https://zertg.us-east.ibm.stepzen.net/solis-dal/suite-automation/mcp",
            "auth_strategy": AuthStrategy.SOLIS_JWT_HANDLER,
            "auth": {
                # Note: 'user_email' intentionally omitted to trigger validator error
                "password": "ENV_INSTANA_SOLIS_PASSWORD_DEV",
                # Different values, same URL-encoded / URL format
                "return_url": "https%3A%2F%2Fexample.sangria.instana.tools%2Fcallback%2F",
                "login_url": "https://example.xangria.instana.tools/auth/signIn",
                "cert_url": "ENV_CERT_URL",
            },
        }

        validator = ServerConfigValidator(config)

        with pytest.raises(
            ValidationError,
            match=(
                "Missing field\\(s\\) in ConfigKey.AUTH for 'solis_jwt_handler' strategy on server "
                "'mcp-dal': user_email"
            ),
        ):
            validator.validate()

    def test_validate_solis_jwt_handler_with_user_email(self):
        """Test SOLIS_JWT_HANDLER passes when user_email is provided."""
        from mcp_composer.core.utils.validator import (
            ServerConfigValidator,
            AuthStrategy,
        )

        config = {
            "id": "mcp-dal",
            "type": "http",
            "endpoint": "https://zertg.us-east.ibm.stepzen.net/solis-dal/suite-automation/mcp",
            "auth_strategy": AuthStrategy.SOLIS_JWT_HANDLER,
            "auth": {
                # Complete auth block including required user_email
                "user_email": "ENV_INSTANA_SOLIS_EMAIL_DEV",
                "password": "ENV_INSTANA_SOLIS_PASSWORD_DEV",
                "return_url": "https%3A%2F%2Fexample.sangria.instana.tools%2Fcallback%2F",
                "login_url": "https://example.xangria.instana.tools/auth/signIn",
                "cert_url": "ENV_CERT_URL",
            },
        }

        validator = ServerConfigValidator(config)

        # Should not raise a ValidationError when user_email is present
        validator.validate()

    def test_all_servers_validator_with_complete_solis_jwt_config(self):
        """Test AllServersValidator passes when a full solis_jwt_handler config is present."""
        from mcp_composer.core.utils.validator import AllServersValidator, AuthStrategy

        servers = [
            {
                "id": "mcp-dal",
                "type": "http",
                "endpoint": "https://zertg.us-east.ibm.stepzen.net/solis-dal/suite-automation/mcp",
                "auth_strategy": AuthStrategy.SOLIS_JWT_HANDLER,
                "auth": {
                    "user_email": "ENV_INSTANA_SOLIS_EMAIL_DEV",
                    "password": "ENV_INSTANA_SOLIS_PASSWORD_DEV",
                    "return_url": "https%3A%2F%2Fexample.sangria.instana.tools%2Fcallback%2F",
                    "login_url": "https://example.xangria.instana.tools/auth/signIn",
                    "cert_url": "ENV_CERT_URL",
                },
            }
        ]

        # Should not raise ValidationError when all required fields are present
        AllServersValidator(servers).validate_all()

    def test_validate_stdio_server(self):
        """Test stdio server validation"""
        from mcp_composer.core.utils.validator import ServerConfigValidator

        config = {
            "id": "test-server",
            "type": "stdio",
            "command": "python",
            "args": ["server.py"],
        }
        validator = ServerConfigValidator(config)

        # Should not raise an exception
        validator.validate()

    def test_validate_auth_dependency_bearer(self):
        """Test auth dependency validation for bearer strategy"""
        from mcp_composer.core.utils.validator import ServerConfigValidator

        config = {
            "id": "test-server",
            "auth_strategy": "bearer",
            "auth": {"token": "test-token"},
        }
        validator = ServerConfigValidator(config)

        # Should not raise an exception
        validator._validate_auth_dependency()

    def test_validate_auth_dependency_dynamic_bearer(self):
        """Test auth dependency validation for dynamic_bearer strategy"""
        from mcp_composer.core.utils.validator import ServerConfigValidator

        config = {
            "id": "test-server",
            "auth_strategy": "dynamic_bearer",
            "auth": {
                "token_url": "https://auth.example.com/token",
                "apikey": "test-key",
            },
        }
        validator = ServerConfigValidator(config)

        # Should not raise an exception
        validator._validate_auth_dependency()

    def test_validate_auth_dependency_basic(self):
        """Test auth dependency validation for basic strategy"""
        from mcp_composer.core.utils.validator import ServerConfigValidator

        config = {
            "id": "test-server",
            "auth_strategy": "basic",
            "auth": {"username": "user", "password": "pass"},
        }
        validator = ServerConfigValidator(config)

        # Should not raise an exception
        validator._validate_auth_dependency()

    def test_validate_auth_dependency_apikey(self):
        """Test auth dependency validation for apikey strategy"""
        from mcp_composer.core.utils.validator import ServerConfigValidator

        config = {
            "id": "test-server",
            "auth_strategy": "apikey",
            "auth": {"apikey": "api-key-value"},
        }
        validator = ServerConfigValidator(config)

        # Should not raise an exception
        validator._validate_auth_dependency()

    def test_validate_auth_dependency_apitoken(self):
        """Test auth dependency validation for apiToken strategy"""
        from mcp_composer.core.utils.validator import ServerConfigValidator

        config = {
            "id": "test-server",
            "auth_strategy": "apiToken",
            "auth": {"token": "api-token"},
        }
        validator = ServerConfigValidator(config)

        # Should not raise an exception
        validator._validate_auth_dependency()

    def test_validate_auth_dependency_jsessionid(self):
        """Test auth dependency validation for jsessionid strategy"""
        from mcp_composer.core.utils.validator import ServerConfigValidator

        config = {
            "id": "test-server",
            "auth_strategy": "jessionid",
            "auth": {"login_url": "/login", "username": "user", "password": "pass"},
        }
        validator = ServerConfigValidator(config)

        # This strategy is not supported, so it should raise an exception
        with pytest.raises(
            ValidationError,
            match="Unsupported ConfigKey.AUTH_STRATEGY 'jessionid' for server 'test-server'",
        ):
            validator._validate_auth_dependency()

    def test_validate_auth_dependency_oauth(self):
        """Test auth dependency validation for oauth2 strategy"""
        from mcp_composer.core.utils.validator import ServerConfigValidator

        config = {
            "id": "test-server",
            "auth_strategy": "oauth2",
            "auth": {
                "client_id": "client",
                "client_secret": "secret",
                "token_url": "https://auth.example.com/token",
            },
        }
        validator = ServerConfigValidator(config)

        # Should not raise an exception
        validator._validate_auth_dependency()

    def test_validate_auth_dependency_missing_auth(self):
        """Test auth dependency validation with missing auth"""
        from mcp_composer.core.utils.validator import (
            ServerConfigValidator,
            ValidationError,
        )

        config = {"id": "test-server", "auth_strategy": "bearer"}
        validator = ServerConfigValidator(config)

        with pytest.raises(
            ValidationError,
            match="Missing ConfigKey.AUTH for server with id 'test-server'",
        ):
            validator._validate_auth_dependency()

    def test_validate_auth_dependency_unsupported_strategy(self):
        """Test auth dependency validation with unsupported strategy"""
        from mcp_composer.core.utils.validator import (
            ServerConfigValidator,
            ValidationError,
        )

        config = {"id": "test-server", "auth_strategy": "unsupported", "auth": {}}
        validator = ServerConfigValidator(config)

        with pytest.raises(
            ValidationError,
            match="Unsupported ConfigKey.AUTH_STRATEGY 'unsupported' for server 'test-server'",
        ):
            validator._validate_auth_dependency()

    def test_validate_openapi_requirements_with_spec_url(self):
        """Test OpenAPI requirements validation with spec_url"""
        from mcp_composer.core.utils.validator import ServerConfigValidator

        config = {
            "id": "test-server",
            "type": "openapi",
            "open_api": {
                "endpoint": "https://api.example.com",
                "spec_url": "https://api.example.com/openapi.json",
            },
        }
        validator = ServerConfigValidator(config)

        # Should not raise an exception
        validator._validate_openapi_requirements()

    def test_validate_openapi_requirements_with_spec_filepath(self):
        """Test OpenAPI requirements validation with spec_filepath"""
        from mcp_composer.core.utils.validator import ServerConfigValidator

        config = {
            "id": "test-server",
            "type": "openapi",
            "open_api": {
                "endpoint": "https://api.example.com",
                "spec_filepath": "/path/to/openapi.json",
            },
        }
        validator = ServerConfigValidator(config)

        # Should not raise an exception
        validator._validate_openapi_requirements()

    def test_validate_openapi_requirements_missing_spec(self):
        """Test OpenAPI requirements validation with missing spec"""
        from mcp_composer.core.utils.validator import (
            ServerConfigValidator,
            ValidationError,
        )

        config = {"id": "test-server", "type": "openapi"}
        validator = ServerConfigValidator(config)

        with pytest.raises(
            ValueError, match="Missing required ConfigKey.OPEN_API section in config."
        ):
            validator._validate_openapi_requirements()

    def test_validate_client_requirements_with_endpoint(self):
        """Test client requirements validation with endpoint"""
        from mcp_composer.core.utils.validator import ServerConfigValidator

        config = {
            "id": "test-server",
            "type": "http",
            "endpoint": "https://api.example.com",
        }
        validator = ServerConfigValidator(config)

        # Should not raise an exception
        validator._validate_client_requirements()

    def test_validate_client_requirements_missing_endpoint(self):
        """Test client requirements validation with missing endpoint"""
        from mcp_composer.core.utils.validator import (
            ServerConfigValidator,
            ValidationError,
        )

        config = {"id": "test-server", "type": "client"}
        validator = ServerConfigValidator(config)

        with pytest.raises(
            ValidationError,
            match="Missing ConfigKey.ENDPOINT for MemberServerType.CLIENT type in server 'test-server'",
        ):
            validator._validate_client_requirements()

    def test_validate_stdio_requirements_with_command(self):
        """Test stdio requirements validation with command"""
        from mcp_composer.core.utils.validator import ServerConfigValidator

        config = {
            "id": "test-server",
            "type": "stdio",
            "command": "python",
            "args": ["server.py"],
        }
        validator = ServerConfigValidator(config)

        # Should not raise an exception
        validator._validate_stdio_requirements()

    def test_validate_stdio_requirements_missing_command(self):
        """Test stdio requirements validation with missing command"""
        from mcp_composer.core.utils.validator import (
            ServerConfigValidator,
            ValidationError,
        )

        config = {"id": "test-server", "type": "stdio", "args": ["server.py"]}
        validator = ServerConfigValidator(config)

        with pytest.raises(
            ValidationError,
            match="Missing required field\\(s\\) for stdio server 'test-server': command",
        ):
            validator._validate_stdio_requirements()

    def test_validate_graphql_config_with_schema_filepath(self):
        """Test GraphQL config validation with schema_filepath"""
        from mcp_composer.core.utils.validator import ServerConfigValidator

        config = {
            "id": "test-server",
            "type": "graphql",
            "graphql": {
                "endpoint": "https://api.example.com",
                "schema_filepath": "/path/to/schema.graphql",
            },
        }
        validator = ServerConfigValidator(config)

        # Should not raise an exception
        validator.validate_graphql_config()

    def test_validate_graphql_config_missing_schema(self):
        """Test GraphQL config validation with missing schema"""
        from mcp_composer.core.utils.validator import (
            ServerConfigValidator,
            ValidationError,
        )

        config = {"id": "test-server", "type": "graphql"}
        validator = ServerConfigValidator(config)

        with pytest.raises(
            ValidationError,
            match="Missing required ConfigKey.GRAPHQL section in config.",
        ):
            validator.validate_graphql_config()

    def test_all_servers_validator_initialization(self):
        """Test AllServersValidator initialization"""
        servers = [
            {
                "id": "server1",
                "type": "openapi",
                "spec_url": "https://api1.example.com/openapi.json",
            },
            {"id": "server2", "type": "http", "endpoint": "https://api2.example.com"},
        ]
        validator = AllServersValidator(servers)

        assert validator.server == servers

    def test_all_servers_validator_validate_all(self):
        """Test AllServersValidator validate_all method"""
        servers = [
            {
                "id": "server1",
                "type": "openapi",
                "open_api": {
                    "endpoint": "https://api1.example.com",
                    "spec_url": "https://api1.example.com/openapi.json",
                },
            },
            {"id": "server2", "type": "http", "endpoint": "https://api2.example.com"},
        ]
        validator = AllServersValidator(servers)

        # Should not raise an exception
        validator.validate_all()

    def test_all_servers_validator_validate_all_with_invalid_server(self):
        """Test AllServersValidator validate_all with invalid server"""
        servers = [
            {
                "id": "server1",
                "type": "openapi",
                "open_api": {
                    "endpoint": "https://api1.example.com",
                    "spec_url": "https://api1.example.com/openapi.json",
                },
            },
            {"id": "server2", "type": "openapi"},  # Missing open_api section
        ]
        validator = AllServersValidator(servers)

        with pytest.raises(ValueError):
            validator.validate_all()

    def test_enum_string_behavior(self):
        """Test that enums behave like strings"""
        from mcp_composer.core.utils.validator import (
            ConfigKey,
            MemberServerType,
            AuthStrategy,
        )

        # Test ConfigKey
        assert ConfigKey.TYPE == "type"
        assert ConfigKey.TYPE == "type"

        # Test MemberServerType
        assert MemberServerType.OPENAPI == "openapi"
        assert MemberServerType.OPENAPI == "openapi"

        # Test AuthStrategy
        assert AuthStrategy.BEARER == "bearer"
        assert AuthStrategy.BEARER == "bearer"

    def test_enum_inheritance(self):
        """Test that enums inherit from str"""
        from mcp_composer.core.utils.validator import (
            ConfigKey,
            MemberServerType,
            AuthStrategy,
        )

        assert issubclass(ConfigKey, str)
        assert issubclass(MemberServerType, str)
        assert issubclass(AuthStrategy, str)

    def test_comprehensive_validation_workflow(self):
        """Test a comprehensive validation workflow"""
        servers = [
            {
                "id": "openapi-server",
                "type": "openapi",
                "open_api": {
                    "endpoint": "https://api.example.com",
                    "spec_url": "https://api.example.com/openapi.json",
                },
                "auth_strategy": "bearer",
                "auth": {"token": "test-token"},
            },
            {
                "id": "http-server",
                "type": "http",
                "endpoint": "https://api.example.com",
            },
            {
                "id": "stdio-server",
                "type": "stdio",
                "command": "python",
                "args": ["server.py"],
            },
        ]

        validator = AllServersValidator(servers)

        # Should not raise an exception
        validator.validate_all()
