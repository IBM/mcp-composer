"""
Tool Factory Pattern for MCP Composer

This module provides a unified factory pattern for creating and registering tools
across different types (OpenAPI, GraphQL, CLI, Specialized, etc.).

Key Features:
- Single entry point for all tool creation
- Strategy pattern for extensibility
- Consistent validation across tool types
- Backward compatible with existing code
- Easy to add new tool types

Usage:
    # Create any tool type with unified interface
    tool = await ToolFactory.create_tool("openapi", config)
    tool = await ToolFactory.create_tool("specialized", config)
    tool = await ToolFactory.create_tool("cli", config)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Type

if TYPE_CHECKING:
    pass

import uncurl
from fastmcp.tools import Tool
from mcp_composer.core.models.tool import OpenApiToolAuthConfig, ToolBuilderConfig
from mcp_composer.core.utils.auth_strategy import get_client
from mcp_composer.core.utils.custom_tool import DynamicToolGenerator, OpenApiTool
from mcp_composer.core.utils.exceptions import ToolGenerateError
from mcp_composer.core.utils.logger import LoggerFactory
from mcp_composer.core.utils.validator import AuthStrategy, ConfigKey
from pydantic import ValidationError

logger = LoggerFactory.get_logger()


class ToolRegistrationStrategy(ABC):
    """
    Abstract base class for tool registration strategies.

    Each tool type (OpenAPI, GraphQL, CLI, etc.) implements this interface
    to provide type-specific creation and validation logic.
    """

    @abstractmethod
    def validate_config(self, config: dict[str, Any]) -> bool:
        """
        Validate tool configuration.

        Args:
            config: Tool configuration dictionary

        Returns:
            True if valid

        Raises:
            ValueError: If configuration is invalid
        """
        pass

    @abstractmethod
    async def create_tool(self, config: dict[str, Any]) -> Tool | tuple[str, Any]:
        """
        Create tool instance from configuration.

        Args:
            config: Tool configuration dictionary

        Returns:
            Tool instance or tuple for mounting (OpenAPI case)

        Raises:
            ToolGenerateError: If tool creation fails
        """
        pass

    @abstractmethod
    def get_tool_type(self) -> str:
        """
        Get tool type identifier.

        Returns:
            Tool type string (e.g., 'openapi', 'cli', 'specialized')
        """
        pass


class OpenAPIRegistrationStrategy(ToolRegistrationStrategy):
    """Strategy for creating OpenAPI-based tools."""

    def validate_config(self, config: dict[str, Any]) -> bool:
        """Validate OpenAPI tool configuration."""
        required_fields = ["openapi_spec"]

        for field in required_fields:
            if field not in config:
                raise ValueError(f"Missing required field: {field}")

        spec = config["openapi_spec"]
        if not isinstance(spec, dict):
            raise ValueError("openapi_spec must be a dictionary")

        if "servers" not in spec or not spec["servers"]:
            raise ValueError("OpenAPI spec must have servers array")

        if "info" not in spec or "title" not in spec["info"]:
            raise ValueError("OpenAPI spec must have info.title")

        auth_config = config.get("auth_config")
        if auth_config:
            try:
                OpenApiToolAuthConfig(**auth_config)
            except ValidationError as e:
                raise ValueError(f"Invalid auth config: {e}")

        logger.debug("OpenAPI config validated successfully")
        return True

    async def create_tool(self, config: dict[str, Any]) -> tuple[str, Any]:
        """Create OpenAPI tool and return server name and client for mounting."""
        try:
            openapi_spec = config["openapi_spec"]
            auth_config = config.get("auth_config")

            server_url = openapi_spec["servers"][0]["url"]
            server_name = openapi_spec["info"]["title"].replace(" ", "_")

            OpenApiTool(
                server_name, openapi_spec, auth_config
            ).write_versioned_openapi()
            client = await get_client(server_url, auth_config)

            logger.info("Created OpenAPI tool: %s", server_name)
            return server_name, client

        except KeyError as e:
            logger.error("Failed to create OpenAPI tool - missing key: %s", e)
            raise ToolGenerateError(
                "Failed to generate tool from openapi: server url or title is missing"
            ) from e
        except Exception as e:
            logger.error("Failed to create OpenAPI tool: %s", e)
            raise ToolGenerateError(f"Failed to generate tool from openapi: {e}") from e

    def get_tool_type(self) -> str:
        return "openapi"


class GraphQLRegistrationStrategy(ToolRegistrationStrategy):
    """Strategy for creating GraphQL tools."""

    def validate_config(self, config: dict[str, Any]) -> bool:
        """Validate GraphQL tool configuration."""
        if "id" not in config:
            raise ValueError("id is required for GraphQL tools")

        if ConfigKey.GRAPHQL not in config:
            raise ValueError("graphql config is required")

        graphql_config = config[ConfigKey.GRAPHQL]
        if ConfigKey.ENDPOINT not in graphql_config:
            raise ValueError("graphql.endpoint is required")

        auth_strategy = config.get(ConfigKey.AUTH_STRATEGY, "none")
        if auth_strategy not in ["none", AuthStrategy.BEARER, "header"]:
            raise ValueError(f"Invalid auth_strategy: {auth_strategy}")

        logger.debug("GraphQL config validated successfully")
        return True

    async def create_tool(self, config: dict[str, Any]) -> Tool:
        """Create GraphQL tool instance."""
        try:
            from mcp_composer.core.tools.graphql_tool import GraphQLTool

            tool = GraphQLTool(config)
            logger.info("Created GraphQL tool: %s", config.get("id"))
            return tool

        except Exception as e:
            logger.error("Failed to create GraphQL tool: %s", e)
            raise ToolGenerateError(f"Failed to create GraphQL tool: {e}") from e

    def get_tool_type(self) -> str:
        return "graphql"


class CLIRegistrationStrategy(ToolRegistrationStrategy):
    """Strategy for creating CLI/curl-based tools."""

    def validate_config(self, config: dict[str, Any]) -> bool:
        """Validate CLI tool configuration."""
        try:
            script_model = ToolBuilderConfig(**config)
        except ValidationError as e:
            raise ValueError(f"Invalid CLI config: {e.errors()}")

        if not script_model.curl_config:
            raise ValueError("curl_config is required for CLI tools")

        try:
            uncurl.parse_context(script_model.curl_config["value"])
        except Exception as e:
            raise ValueError(f"Invalid curl command: {e}")

        logger.debug("CLI config validated successfully")
        return True

    async def create_tool(self, config: dict[str, Any]) -> Tool:
        """Create CLI tool from curl command."""
        try:
            script_model = ToolBuilderConfig(**config)

            if not script_model.curl_config:
                raise ValueError("curl_config is required")

            parsed = uncurl.parse_context(script_model.curl_config["value"])

            tool_data = {
                "_id": script_model.name,
                "id": script_model.name,
                "description": script_model.description,
                "headers": parsed.headers,
                "method": parsed.method,
                "body": parsed.data,
                "url": parsed.url,
            }

            DynamicToolGenerator.write_curl_to_file(tool_data)
            fn = DynamicToolGenerator.create_api_request(tool_data)

            logger.info("Created CLI tool: %s", script_model.name)
            return Tool.from_function(fn)

        except ValidationError as e:
            logger.error("Invalid CLI config: %s", e.errors())
            raise ToolGenerateError(f"Invalid input: {e.errors()}") from e
        except Exception as e:
            logger.error("Failed to create CLI tool: %s", e)
            raise ToolGenerateError(str(e)) from e

    def get_tool_type(self) -> str:
        return "cli"


class PythonScriptRegistrationStrategy(ToolRegistrationStrategy):
    """Strategy for creating tools from Python scripts."""

    def validate_config(self, config: dict[str, Any]) -> bool:
        """Validate Python script tool configuration."""
        try:
            script_model = ToolBuilderConfig(**config)
        except ValidationError as e:
            raise ValueError(f"Invalid script config: {e.errors()}")

        if not script_model.script_config:
            raise ValueError("script_config is required for Python script tools")

        logger.debug("Python script config validated successfully")
        return True

    async def create_tool(self, config: dict[str, Any]) -> Tool:
        """Create tool from Python script."""
        try:
            script_model = ToolBuilderConfig(**config)
            fn = DynamicToolGenerator().create_from_script(script_model)

            logger.info("Created Python script tool: %s", script_model.name)
            return Tool.from_function(fn)

        except ValidationError as e:
            logger.error("Invalid script config: %s", e.errors())
            raise ToolGenerateError(f"Invalid input: {e.errors()}") from e
        except Exception as e:
            logger.error("Failed to create Python script tool: %s", e)
            raise ToolGenerateError(str(e)) from e

    def get_tool_type(self) -> str:
        return "script"


class SpecializedToolRegistrationStrategy(ToolRegistrationStrategy):
    """Strategy for creating specialized tools (IBMDocumentSearchTool, ModelMeshTool, etc.)."""

    def __init__(self):
        self._tool_registry: dict[str, Type[Tool]] = {}
        self._register_default_tools()

    def _register_default_tools(self):
        """Register built-in specialized tools."""
        try:
            from mcp_composer.core.tools.ibm_document_search_tool import (
                IBMDocumentSearchTool,
            )

            self._tool_registry["IBMDocumentSearchTool"] = IBMDocumentSearchTool
        except ImportError:
            logger.warning("IBMDocumentSearchTool not available")

        try:
            from mcp_composer.core.tools.model_mesh_tool import ModelMeshTool

            self._tool_registry["ModelMeshTool"] = ModelMeshTool
        except ImportError:
            logger.warning("ModelMeshTool not available")

        # Note: SRETool and NVDTool may not exist yet
        # They can be registered later via register_tool_class()

        logger.debug("Registered %d specialized tool classes", len(self._tool_registry))

    def validate_config(self, config: dict[str, Any]) -> bool:
        """Validate specialized tool configuration."""
        if "tool_class" not in config:
            raise ValueError("tool_class is required for specialized tools")

        tool_class_name = config["tool_class"]
        if tool_class_name not in self._tool_registry:
            available = ", ".join(self._tool_registry.keys())
            raise ValueError(
                f"Unknown tool class: {tool_class_name}. Available: {available}"
            )

        tool_class = self._tool_registry[tool_class_name]
        if hasattr(tool_class, "validate_config") and callable(
            getattr(tool_class, "validate_config")
        ):
            tool_class.validate_config(config)  # type: ignore

        logger.debug("Specialized tool config validated: %s", tool_class_name)
        return True

    async def create_tool(self, config: dict[str, Any]) -> Tool:
        """Create specialized tool instance."""
        try:
            tool_class_name = config["tool_class"]
            tool_class = self._tool_registry[tool_class_name]

            # Specialized tools accept config parameter
            tool = tool_class(config=config)  # type: ignore
            logger.info("Created specialized tool: %s", tool_class_name)
            return tool

        except Exception as e:
            logger.error("Failed to create specialized tool: %s", e)
            raise ToolGenerateError(f"Failed to create specialized tool: {e}") from e

    def register_tool_class(self, name: str, tool_class: Type[Any]):
        """
        Register a custom specialized tool class.

        Args:
            name: Tool class name
            tool_class: Tool class type (must be compatible with Tool interface)
        """
        self._tool_registry[name] = tool_class  # type: ignore
        logger.info("Registered custom specialized tool class: %s", name)

    def get_tool_type(self) -> str:
        return "specialized"


class ToolFactory:
    """
    Central factory for creating all tool types.

    This factory provides a unified interface for creating tools across
    different types (OpenAPI, GraphQL, CLI, Specialized, etc.).

    Usage:
        # Initialize factory (done automatically on first use)
        ToolFactory.initialize()

        # Create tools with unified interface
        tool = await ToolFactory.create_tool("openapi", openapi_config)
        tool = await ToolFactory.create_tool("specialized", specialized_config)

        # Register custom strategies
        ToolFactory.register_strategy(MyCustomStrategy())

        # Get supported types
        types = ToolFactory.get_supported_types()
    """

    _strategies: dict[str, ToolRegistrationStrategy] = {}
    _initialized = False

    @classmethod
    def initialize(cls):
        """Initialize factory with default strategies."""
        if cls._initialized:
            return

        logger.info("Initializing ToolFactory with default strategies")

        cls.register_strategy(OpenAPIRegistrationStrategy())
        cls.register_strategy(GraphQLRegistrationStrategy())
        cls.register_strategy(CLIRegistrationStrategy())
        cls.register_strategy(PythonScriptRegistrationStrategy())
        cls.register_strategy(SpecializedToolRegistrationStrategy())

        cls._initialized = True
        logger.info("ToolFactory initialized with %d strategies", len(cls._strategies))

    @classmethod
    def register_strategy(cls, strategy: ToolRegistrationStrategy):
        """
        Register a tool registration strategy.

        Args:
            strategy: Strategy instance implementing ToolRegistrationStrategy
        """
        tool_type = strategy.get_tool_type()
        cls._strategies[tool_type] = strategy
        logger.debug("Registered strategy for tool type: %s", tool_type)

    @classmethod
    async def create_tool(
        cls, tool_type: str, config: dict[str, Any]
    ) -> Tool | tuple[str, Any]:
        """
        Create tool using appropriate strategy.

        Args:
            tool_type: Tool type identifier ('openapi', 'cli', 'specialized', etc.)
            config: Tool configuration dictionary

        Returns:
            Tool instance or tuple for mounting (OpenAPI case)

        Raises:
            ValueError: If tool type is unknown
            ToolGenerateError: If tool creation fails
        """
        cls.initialize()

        if tool_type not in cls._strategies:
            available = ", ".join(cls._strategies.keys())
            raise ValueError(f"Unknown tool type: {tool_type}. Available: {available}")

        strategy = cls._strategies[tool_type]

        logger.debug("Creating tool of type: %s", tool_type)
        strategy.validate_config(config)

        return await strategy.create_tool(config)

    @classmethod
    def get_supported_types(cls) -> list[str]:
        """
        Get list of supported tool types.

        Returns:
            List of tool type identifiers
        """
        cls.initialize()
        return list(cls._strategies.keys())

    @classmethod
    def get_strategy(cls, tool_type: str) -> ToolRegistrationStrategy:
        """
        Get strategy for a specific tool type.

        Args:
            tool_type: Tool type identifier

        Returns:
            Strategy instance

        Raises:
            ValueError: If tool type is unknown
        """
        cls.initialize()

        if tool_type not in cls._strategies:
            available = ", ".join(cls._strategies.keys())
            raise ValueError(f"Unknown tool type: {tool_type}. Available: {available}")

        return cls._strategies[tool_type]

    @classmethod
    def reset(cls):
        """Reset factory state (useful for testing)."""
        cls._strategies.clear()
        cls._initialized = False
        logger.debug("ToolFactory reset")
