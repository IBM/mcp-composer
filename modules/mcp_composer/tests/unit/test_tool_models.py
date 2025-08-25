"""Test module for tool.py models"""

import pytest
from pydantic import ValidationError
from mcp_composer.core.models.tool import ToolBuilderConfig, OpenApiToolAuthConfig
from mcp_composer.core.models.oauth import BearerAuth, DynamicBearerAuth, BasicAuth, APIkey


class TestToolBuilderConfig:
    """Test cases for ToolBuilderConfig model"""

    def test_tool_builder_config_creation_with_curl_config(self):
        """Test creating ToolBuilderConfig with curl_config"""
        config = ToolBuilderConfig(
            name="test-tool",
            tool_type="curl",
            description="A test tool",
            curl_config={
                "url": "https://api.example.com/data",
                "method": "GET",
                "headers": {"Authorization": "Bearer token"}
            }
        )
        
        assert config.name == "test-tool"
        assert config.tool_type == "curl"
        assert config.description == "A test tool"
        assert config.curl_config["url"] == "https://api.example.com/data"
        assert config.script_config is None
        assert config.permission is None

    def test_tool_builder_config_creation_with_script_config(self):
        """Test creating ToolBuilderConfig with script_config"""
        config = ToolBuilderConfig(
            name="test-tool",
            tool_type="python",
            description="A test tool",
            script_config={
                "function_name": "get_data",
                "code": "def get_data(): return 'data'"
            }
        )
        
        assert config.name == "test-tool"
        assert config.tool_type == "python"
        assert config.description == "A test tool"
        assert config.script_config["function_name"] == "get_data"
        assert config.curl_config is None
        assert config.permission is None

    def test_tool_builder_config_creation_with_permissions(self):
        """Test creating ToolBuilderConfig with permissions"""
        config = ToolBuilderConfig(
            name="test-tool",
            tool_type="curl",
            description="A test tool",
            curl_config={"url": "https://api.example.com/data"},
            permission={"admin": "read", "user": "execute"}
        )
        
        assert config.permission["admin"] == "read"
        assert config.permission["user"] == "execute"

    def test_tool_builder_config_missing_required_fields(self):
        """Test that missing required fields raise ValidationError"""
        with pytest.raises(ValidationError):
            ToolBuilderConfig()

    def test_tool_builder_config_missing_name(self):
        """Test that missing name raises ValidationError"""
        with pytest.raises(ValidationError):
            ToolBuilderConfig(
                tool_type="curl",
                description="A test tool",
                curl_config={"url": "https://api.example.com/data"}
            )

    def test_tool_builder_config_missing_tool_type(self):
        """Test that missing tool_type raises ValidationError"""
        with pytest.raises(ValidationError):
            ToolBuilderConfig(
                name="test-tool",
                description="A test tool",
                curl_config={"url": "https://api.example.com/data"}
            )

    def test_tool_builder_config_missing_description(self):
        """Test that missing description raises ValidationError"""
        with pytest.raises(ValidationError):
            ToolBuilderConfig(
                name="test-tool",
                tool_type="curl",
                curl_config={"url": "https://api.example.com/data"}
            )

    def test_tool_builder_config_missing_both_configs(self):
        """Test that missing both curl_config and script_config raises ValidationError"""
        with pytest.raises(ValidationError, match="Either 'curl_config' or 'script_config' must be provided."):
            ToolBuilderConfig(
                name="test-tool",
                tool_type="curl",
                description="A test tool"
            )

    def test_tool_builder_config_empty_curl_config_key(self):
        """Test that empty curl_config key raises ValidationError"""
        with pytest.raises(ValidationError, match="Curl config key cannot be empty or key should contain a value"):
            ToolBuilderConfig(
                name="test-tool",
                tool_type="curl",
                description="A test tool",
                curl_config={"": "value"}
            )

    def test_tool_builder_config_empty_curl_config_value(self):
        """Test that empty curl_config value raises ValidationError"""
        with pytest.raises(ValidationError, match="Curl config value for 'key' cannot be empty."):
            ToolBuilderConfig(
                name="test-tool",
                tool_type="curl",
                description="A test tool",
                curl_config={"key": ""}
            )

    def test_tool_builder_config_empty_script_config_key(self):
        """Test that empty script_config key raises ValidationError"""
        with pytest.raises(ValidationError, match="Python script config key cannot be empty or key should contain a value"):
            ToolBuilderConfig(
                name="test-tool",
                tool_type="python",
                description="A test tool",
                script_config={"": "value"}
            )

    def test_tool_builder_config_empty_script_config_value(self):
        """Test that empty script_config value raises ValidationError"""
        with pytest.raises(ValidationError, match="Python script value for 'key' cannot be empty."):
            ToolBuilderConfig(
                name="test-tool",
                tool_type="python",
                description="A test tool",
                script_config={"key": ""}
            )

    def test_tool_builder_config_whitespace_only_curl_config_key(self):
        """Test that whitespace-only curl_config key raises ValidationError"""
        with pytest.raises(ValidationError, match="Curl config key cannot be empty or key should contain a value"):
            ToolBuilderConfig(
                name="test-tool",
                tool_type="curl",
                description="A test tool",
                curl_config={"   ": "value"}
            )

    def test_tool_builder_config_whitespace_only_curl_config_value(self):
        """Test that whitespace-only curl_config value raises ValidationError"""
        with pytest.raises(ValidationError, match="Curl config value for 'key' cannot be empty."):
            ToolBuilderConfig(
                name="test-tool",
                tool_type="curl",
                description="A test tool",
                curl_config={"key": "   "}
            )

    def test_tool_builder_config_whitespace_only_script_config_key(self):
        """Test that whitespace-only script_config key raises ValidationError"""
        with pytest.raises(ValidationError, match="Python script config key cannot be empty or key should contain a value"):
            ToolBuilderConfig(
                name="test-tool",
                tool_type="python",
                description="A test tool",
                script_config={"   ": "value"}
            )

    def test_tool_builder_config_whitespace_only_script_config_value(self):
        """Test that whitespace-only script_config value raises ValidationError"""
        with pytest.raises(ValidationError, match="Python script value for 'key' cannot be empty."):
            ToolBuilderConfig(
                name="test-tool",
                tool_type="python",
                description="A test tool",
                script_config={"key": "   "}
            )

    def test_tool_builder_config_none_curl_config(self):
        """Test that None curl_config is allowed"""
        config = ToolBuilderConfig(
            name="test-tool",
            tool_type="python",
            description="A test tool",
            script_config={"function": "test"},
            curl_config=None
        )
        assert config.curl_config is None

    def test_tool_builder_config_none_script_config(self):
        """Test that None script_config is allowed"""
        config = ToolBuilderConfig(
            name="test-tool",
            tool_type="curl",
            description="A test tool",
            curl_config={"url": "https://api.example.com/data"},
            script_config=None
        )
        assert config.script_config is None


class TestOpenApiToolAuthConfig:
    """Test cases for OpenApiToolAuthConfig model"""

    def test_openapi_tool_auth_config_bearer(self):
        """Test creating OpenApiToolAuthConfig with bearer auth"""
        config = OpenApiToolAuthConfig(
            auth_strategy="bearer",
            auth={"token": "test-token"}
        )
        
        assert config.auth_strategy == "bearer"
        assert isinstance(config.auth, BearerAuth)
        assert config.auth.token == "test-token"

    def test_openapi_tool_auth_config_dynamic_bearer(self):
        """Test creating OpenApiToolAuthConfig with dynamic_bearer auth"""
        config = OpenApiToolAuthConfig(
            auth_strategy="dynamic_bearer",
            auth={"token_url": "https://auth.example.com/token", "apikey": "test-key"}
        )
        
        assert config.auth_strategy == "dynamic_bearer"
        assert isinstance(config.auth, DynamicBearerAuth)
        assert config.auth.token_url == "https://auth.example.com/token"
        assert config.auth.apikey == "test-key"

    def test_openapi_tool_auth_config_basic(self):
        """Test creating OpenApiToolAuthConfig with basic auth"""
        config = OpenApiToolAuthConfig(
            auth_strategy="basic",
            auth={"username": "user", "password": "pass"}
        )
        
        assert config.auth_strategy == "basic"
        assert isinstance(config.auth, BasicAuth)
        assert config.auth.username == "user"
        assert config.auth.password == "pass"

    def test_openapi_tool_auth_config_api_key(self):
        """Test creating OpenApiToolAuthConfig with api_key auth"""
        config = OpenApiToolAuthConfig(
            auth_strategy="api_key",
            auth={"apikey": "api-key", "value": "key-value"}
        )
        
        assert config.auth_strategy == "api_key"
        assert isinstance(config.auth, APIkey)
        assert config.auth.apikey == "api-key"
        assert config.auth.value == "key-value"

    def test_openapi_tool_auth_config_missing_auth_strategy(self):
        """Test that missing auth_strategy raises ValidationError"""
        with pytest.raises(ValidationError, match="Both 'auth_strategy' and 'auth' must be provided."):
            OpenApiToolAuthConfig(
                auth={"token": "test-token"}
            )

    def test_openapi_tool_auth_config_missing_auth(self):
        """Test that missing auth raises ValidationError"""
        with pytest.raises(ValidationError, match="Both 'auth_strategy' and 'auth' must be provided."):
            OpenApiToolAuthConfig(
                auth_strategy="bearer"
            )

    def test_openapi_tool_auth_config_unsupported_strategy(self):
        """Test that unsupported auth_strategy raises ValidationError"""
        with pytest.raises(ValidationError, match="Unsupported auth_strategy: invalid"):
            OpenApiToolAuthConfig(
                auth_strategy="invalid",
                auth={"token": "test-token"}
            )

    def test_openapi_tool_auth_config_invalid_literal(self):
        """Test that invalid literal auth_strategy raises ValidationError"""
        with pytest.raises(ValidationError):
            OpenApiToolAuthConfig(
                auth_strategy="invalid_strategy",
                auth={"token": "test-token"}
            )

    def test_openapi_tool_auth_config_field_descriptions(self):
        """Test that field descriptions are properly set"""
        # Get field info
        auth_strategy_field = OpenApiToolAuthConfig.model_fields['auth_strategy']
        auth_field = OpenApiToolAuthConfig.model_fields['auth']
        
        assert auth_strategy_field is not None
        assert auth_field is not None

    def test_openapi_tool_auth_config_json_serialization(self):
        """Test JSON serialization and deserialization"""
        config = OpenApiToolAuthConfig(
            auth_strategy="bearer",
            auth={"token": "test-token"}
        )
        
        # Serialize to dict
        config_dict = config.model_dump()
        
        assert config_dict["auth_strategy"] == "bearer"
        assert config_dict["auth"]["token"] == "test-token"
        
        # Deserialize from dict
        config_from_dict = OpenApiToolAuthConfig(**config_dict)
        assert config_from_dict.auth_strategy == config.auth_strategy
        assert config_from_dict.auth.token == config.auth.token 