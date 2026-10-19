"""
Tests for Tool Factory Pattern

This module tests the ToolFactory and all registration strategies to ensure:
- Correct tool creation for all types
- Proper validation of configurations
- Backward compatibility
- Error handling
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastmcp.tools import Tool
from mcp_composer.core.tools.tool_factory import (
    CLIRegistrationStrategy,
    GraphQLRegistrationStrategy,
    OpenAPIRegistrationStrategy,
    SpecializedToolRegistrationStrategy,
    ToolFactory,
    ToolRegistrationStrategy,
)
from mcp_composer.core.utils.exceptions import ToolGenerateError


class TestToolFactory:
    """Test ToolFactory core functionality."""

    def setup_method(self):
        """Reset factory before each test."""
        ToolFactory.reset()

    def test_factory_initialization(self):
        """Test factory initializes with default strategies."""
        ToolFactory.initialize()

        assert ToolFactory._initialized is True
        assert len(ToolFactory._strategies) == 5
        assert "openapi" in ToolFactory._strategies
        assert "graphql" in ToolFactory._strategies
        assert "cli" in ToolFactory._strategies
        assert "script" in ToolFactory._strategies
        assert "specialized" in ToolFactory._strategies

    def test_get_supported_types(self):
        """Test getting list of supported tool types."""
        types = ToolFactory.get_supported_types()

        assert isinstance(types, list)
        assert len(types) == 5
        assert "openapi" in types
        assert "graphql" in types
        assert "cli" in types
        assert "script" in types
        assert "specialized" in types

    def test_register_custom_strategy(self):
        """Test registering a custom strategy."""

        class CustomStrategy(ToolRegistrationStrategy):
            def validate_config(self, config):
                return True

            async def create_tool(self, config):
                return Mock(spec=Tool)

            def get_tool_type(self):
                return "custom"

        ToolFactory.register_strategy(CustomStrategy())

        assert "custom" in ToolFactory.get_supported_types()

    def test_get_strategy(self):
        """Test getting a specific strategy."""
        strategy = ToolFactory.get_strategy("openapi")

        assert isinstance(strategy, OpenAPIRegistrationStrategy)

    def test_get_strategy_unknown_type(self):
        """Test getting unknown strategy raises error."""
        with pytest.raises(ValueError, match="Unknown tool type"):
            ToolFactory.get_strategy("unknown_type")

    @pytest.mark.asyncio
    async def test_create_tool_unknown_type(self):
        """Test creating tool with unknown type raises error."""
        with pytest.raises(ValueError, match="Unknown tool type"):
            await ToolFactory.create_tool("unknown_type", {})

    def test_factory_reset(self):
        """Test factory reset clears state."""
        ToolFactory.initialize()
        assert ToolFactory._initialized is True

        ToolFactory.reset()
        assert ToolFactory._initialized is False
        assert len(ToolFactory._strategies) == 0


class TestOpenAPIRegistrationStrategy:
    """Test OpenAPI tool registration strategy."""

    def setup_method(self):
        """Setup strategy for each test."""
        self.strategy = OpenAPIRegistrationStrategy()

    def test_get_tool_type(self):
        """Test strategy returns correct type."""
        assert self.strategy.get_tool_type() == "openapi"

    def test_validate_config_success(self):
        """Test validation with valid config."""
        config = {
            "openapi_spec": {
                "servers": [{"url": "https://api.example.com"}],
                "info": {"title": "Test API"},
            }
        }

        assert self.strategy.validate_config(config) is True

    def test_validate_config_missing_spec(self):
        """Test validation fails without openapi_spec."""
        config = {}

        with pytest.raises(ValueError, match="Missing required field: openapi_spec"):
            self.strategy.validate_config(config)

    def test_validate_config_invalid_spec(self):
        """Test validation fails with invalid spec structure."""
        config = {
            "openapi_spec": {
                "info": {"title": "Test API"}
                # Missing servers
            }
        }

        with pytest.raises(ValueError, match="must have servers"):
            self.strategy.validate_config(config)

    def test_validate_config_missing_title(self):
        """Test validation fails without title."""
        config = {
            "openapi_spec": {
                "servers": [{"url": "https://api.example.com"}],
                "info": {},  # Missing title
            }
        }

        with pytest.raises(ValueError, match="must have info.title"):
            self.strategy.validate_config(config)

    @pytest.mark.asyncio
    async def test_create_tool_success(self):
        """Test successful tool creation."""
        config = {
            "openapi_spec": {
                "servers": [{"url": "https://api.example.com"}],
                "info": {"title": "Test API"},
            }
        }

        with patch(
            "mcp_composer.core.tools.tool_factory.OpenApiTool"
        ) as mock_openapi_tool, patch(
            "mcp_composer.core.tools.tool_factory.get_client"
        ) as mock_get_client:
            mock_openapi_tool.return_value.write_versioned_openapi = Mock()
            mock_get_client.return_value = AsyncMock()

            server_name, client = await self.strategy.create_tool(config)

            assert server_name == "Test_API"
            assert client is not None


class TestGraphQLRegistrationStrategy:
    """Test GraphQL tool registration strategy."""

    def setup_method(self):
        """Setup strategy for each test."""
        self.strategy = GraphQLRegistrationStrategy()

    def test_get_tool_type(self):
        """Test strategy returns correct type."""
        assert self.strategy.get_tool_type() == "graphql"

    def test_validate_config_success(self):
        """Test validation with valid config."""
        config = {
            "id": "test_graphql",
            "graphql": {"endpoint": "https://api.example.com/graphql"},
        }

        assert self.strategy.validate_config(config) is True

    def test_validate_config_missing_id(self):
        """Test validation fails without id."""
        config = {"graphql": {"endpoint": "https://api.example.com/graphql"}}

        with pytest.raises(ValueError, match="id is required"):
            self.strategy.validate_config(config)

    def test_validate_config_missing_endpoint(self):
        """Test validation fails without endpoint."""
        config = {"id": "test_graphql", "graphql": {}}

        with pytest.raises(ValueError, match="endpoint is required"):
            self.strategy.validate_config(config)

    @pytest.mark.asyncio
    async def test_create_tool_success(self):
        """Test successful GraphQL tool creation."""
        config = {
            "id": "test_graphql",
            "graphql": {"endpoint": "https://api.example.com/graphql"},
        }

        with patch(
            "mcp_composer.core.tools.graphql_tool.GraphQLTool"
        ) as mock_graphql_tool:
            mock_tool = Mock(spec=Tool)
            mock_graphql_tool.return_value = mock_tool

            tool = await self.strategy.create_tool(config)

            assert tool == mock_tool
            mock_graphql_tool.assert_called_once_with(config)


class TestCLIRegistrationStrategy:
    """Test CLI/curl tool registration strategy."""

    def setup_method(self):
        """Setup strategy for each test."""
        self.strategy = CLIRegistrationStrategy()

    def test_get_tool_type(self):
        """Test strategy returns correct type."""
        assert self.strategy.get_tool_type() == "cli"

    def test_validate_config_success(self):
        """Test validation with valid config."""
        config = {
            "name": "test_cli",
            "description": "Test CLI tool",
            "tool_type": "curl",  # Required by ToolBuilderConfig
            "curl_config": {"value": "curl -X GET https://api.example.com/test"},
        }

        with patch(
            "mcp_composer.core.tools.tool_factory.uncurl.parse_context"
        ) as mock_parse:
            mock_parse.return_value = Mock()
            assert self.strategy.validate_config(config) is True

    def test_validate_config_missing_curl_config(self):
        """Test validation fails without curl_config."""
        config = {
            "name": "test_cli",
            "description": "Test CLI tool",
            "tool_type": "curl",  # Required by ToolBuilderConfig
        }

        # The error message will be about missing tool_type first, not curl_config
        with pytest.raises(ValueError):
            self.strategy.validate_config(config)


class TestSpecializedToolRegistrationStrategy:
    """Test specialized tool registration strategy."""

    def setup_method(self):
        """Setup strategy for each test."""
        self.strategy = SpecializedToolRegistrationStrategy()

    def test_get_tool_type(self):
        """Test strategy returns correct type."""
        assert self.strategy.get_tool_type() == "specialized"

    def test_default_tools_registered(self):
        """Test default specialized tools are registered."""
        # At least IBMDocumentSearchTool and ModelMeshTool should be registered
        assert len(self.strategy._tool_registry) >= 2

    def test_validate_config_success(self):
        """Test validation with valid config."""
        config = {"tool_class": "IBMDocumentSearchTool", "name": "test_doc_search"}

        assert self.strategy.validate_config(config) is True

    def test_validate_config_missing_tool_class(self):
        """Test validation fails without tool_class."""
        config = {"name": "test_tool"}

        with pytest.raises(ValueError, match="tool_class is required"):
            self.strategy.validate_config(config)

    def test_validate_config_unknown_tool_class(self):
        """Test validation fails with unknown tool_class."""
        config = {"tool_class": "UnknownTool", "name": "test_tool"}

        with pytest.raises(ValueError, match="Unknown tool class"):
            self.strategy.validate_config(config)

    def test_register_custom_tool_class(self):
        """Test registering a custom tool class."""

        class CustomTool(Tool):
            def __init__(self, config=None):
                super().__init__(
                    name="custom", description="Custom tool", parameters={}
                )

        self.strategy.register_tool_class("CustomTool", CustomTool)

        assert "CustomTool" in self.strategy._tool_registry

    @pytest.mark.asyncio
    async def test_create_tool_success(self):
        """Test successful specialized tool creation."""
        # Mock a specialized tool class
        mock_tool_class = Mock()
        mock_tool_instance = Mock(spec=Tool)
        mock_tool_class.return_value = mock_tool_instance

        self.strategy._tool_registry["TestTool"] = mock_tool_class

        config = {"tool_class": "TestTool", "name": "test_tool"}

        tool = await self.strategy.create_tool(config)

        assert tool == mock_tool_instance
        mock_tool_class.assert_called_once_with(config=config)


class TestBackwardCompatibility:
    """Test backward compatibility with existing code."""

    def setup_method(self):
        """Reset factory before each test."""
        ToolFactory.reset()

    @pytest.mark.asyncio
    async def test_openapi_tool_creation_compatible(self):
        """Test OpenAPI tool creation is compatible with old approach."""
        config = {
            "openapi_spec": {
                "servers": [{"url": "https://api.example.com"}],
                "info": {"title": "Test API"},
            }
        }

        with patch(
            "mcp_composer.core.tools.tool_factory.OpenApiTool"
        ) as mock_openapi_tool, patch(
            "mcp_composer.core.tools.tool_factory.get_client"
        ) as mock_get_client:
            mock_openapi_tool.return_value.write_versioned_openapi = Mock()
            mock_client = AsyncMock()
            mock_get_client.return_value = mock_client

            server_name, client = await ToolFactory.create_tool("openapi", config)

            # Should return tuple like old tool_from_open_api
            assert isinstance(server_name, str)
            assert client is not None

    @pytest.mark.asyncio
    async def test_cli_tool_creation_compatible(self):
        """Test CLI tool creation is compatible with old approach."""
        config = {
            "name": "test_cli",
            "description": "Test CLI tool",
            "tool_type": "curl",  # Required by ToolBuilderConfig
            "curl_config": {"value": "curl -X GET https://api.example.com/test"},
        }

        with patch(
            "mcp_composer.core.tools.tool_factory.uncurl.parse_context"
        ) as mock_parse, patch(
            "mcp_composer.core.tools.tool_factory.DynamicToolGenerator"
        ) as mock_generator, patch(
            "mcp_composer.core.tools.tool_factory.Tool.from_function"
        ) as mock_from_function:
            mock_parse.return_value = Mock(
                headers={}, method="GET", data=None, url="https://api.example.com/test"
            )
            mock_generator.write_curl_to_file = Mock()
            mock_generator.create_api_request = Mock(return_value=lambda: None)
            mock_tool = Mock(spec=Tool)
            mock_from_function.return_value = mock_tool

            tool = await ToolFactory.create_tool("cli", config)

            # Should return Tool instance like old tool_from_curl
            assert isinstance(tool, Mock)


class TestErrorHandling:
    """Test error handling in factory and strategies."""

    def setup_method(self):
        """Reset factory before each test."""
        ToolFactory.reset()

    @pytest.mark.asyncio
    async def test_validation_error_propagates(self):
        """Test validation errors are properly propagated."""
        config = {}  # Invalid config

        with pytest.raises(ValueError):
            await ToolFactory.create_tool("openapi", config)

    @pytest.mark.asyncio
    async def test_creation_error_wrapped(self):
        """Test creation errors are wrapped in ToolGenerateError."""
        config = {
            "openapi_spec": {
                "servers": [{"url": "https://api.example.com"}],
                "info": {"title": "Test API"},
            }
        }

        with patch(
            "mcp_composer.core.tools.tool_factory.OpenApiTool"
        ) as mock_openapi_tool:
            mock_openapi_tool.side_effect = Exception("Test error")

            with pytest.raises(ToolGenerateError):
                await ToolFactory.create_tool("openapi", config)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
