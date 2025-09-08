"""
Test cases for LayeredOpenAPIFactory.

Tests the enhanced OpenAPI processing capabilities including:
- Schema resolution and reference handling
- Parameter schema extraction
- Request body schema processing
- Response schema processing
- Enhanced service information
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, List
import json
import os

from mcp_composer.core.member_servers.layered_factory_oa import LayeredOpenAPIFactory
from mcp_composer.core.member_servers.layered_constants import (
    SERVICE_KEYS, PARAMETER_KEYS, SCHEMA_KEYS, OPERATION_KEYS, DEFAULT_VALUES, RESPONSE_KEYS
)


class TestLayeredOpenAPIFactory:
    """Test cases for LayeredOpenAPIFactory class."""

    @pytest.fixture
    def mock_openapi_spec(self):
        """Create a mock OpenAPI specification for testing."""
        return {
            "openapi": "3.0.3",
            "info": {"title": "Test API", "version": "1.0.0"},
            "paths": {
                "/test/endpoint": {
                    "get": {
                        "operationId": "get_test_data",
                        "summary": "Get test data",
                        "description": "Retrieve test data from the API",
                        "parameters": [
                            {
                                "name": "id",
                                "in": "path",
                                "required": True,
                                "description": "Test ID",
                                "schema": {"type": "string"}
                            },
                            {
                                "name": "filter",
                                "in": "query",
                                "required": False,
                                "description": "Filter parameter",
                                "schema": {"type": "string"}
                            }
                        ],
                        "requestBody": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/TestRequest"
                                    }
                                }
                            }
                        },
                        "responses": {
                            "200": {
                                "description": "Success",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "$ref": "#/components/schemas/TestResponse"
                                        }
                                    }
                                }
                            },
                            "400": {
                                "description": "Bad Request"
                            }
                        },
                        "tags": ["test", "data"]
                    }
                }
            },
            "components": {
                "schemas": {
                    "TestRequest": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "value": {"type": "integer"}
                        },
                        "required": ["name"]
                    },
                    "TestResponse": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "data": {"type": "object"}
                        }
                    }
                }
            }
        }

    @pytest.fixture
    def mock_client(self):
        """Create a mock httpx client for testing."""
        return Mock()

    @pytest.fixture
    def layered_factory(self, mock_openapi_spec, mock_client):
        """Create a LayeredOpenAPIFactory instance for testing."""
        return LayeredOpenAPIFactory(mock_openapi_spec, mock_client)

    def test_layered_factory_initialization(self, layered_factory):
        """Test that LayeredOpenAPIFactory initializes correctly."""
        assert layered_factory.name == "Layered OpenAPI FastMCP"
        assert layered_factory.openapi_spec is not None
        assert layered_factory.client is not None
        assert len(layered_factory.tools) == 3

    def test_layered_factory_tools(self, layered_factory):
        """Test that LayeredOpenAPIFactory has the correct tools."""
        tool_names = [tool.name for tool in layered_factory.tools]
        assert "get_service_info" in tool_names
        assert "get_type_info" in tool_names
        assert "make_tool_call" in tool_names

    def test_resolve_schema_reference(self, layered_factory):
        """Test schema reference resolution."""
        # Test valid reference
        ref = "#/components/schemas/TestRequest"
        result = layered_factory._resolve_schema_reference(ref)
        assert result is not None
        assert "type" in result
        assert result["type"] == "object"

        # Test invalid reference
        invalid_ref = "#/components/schemas/NonExistent"
        result = layered_factory._resolve_schema_reference(invalid_ref)
        assert result == {}

        # Test non-reference
        result = layered_factory._resolve_schema_reference("not_a_ref")
        assert result == {}

    def test_extract_parameter_schemas(self, layered_factory):
        """Test parameter schema extraction."""
        parameters = [
            {
                "name": "test_param",
                "in": "query",
                "required": True,
                "schema": {"type": "string"}
            }
        ]
        
        result = layered_factory._extract_parameter_schemas(parameters)
        assert len(result) == 1
        assert result[0]["name"] == "test_param"
        assert result[0]["in"] == "query"
        assert result[0]["required"] is True

    def test_extract_request_body_schema(self, layered_factory):
        """Test request body schema extraction."""
        request_body = {
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"}
                        }
                    }
                }
            }
        }
        
        result = layered_factory._extract_request_body_schema(request_body)
        assert result is not None
        assert "type" in result

    def test_extract_response_schemas(self, layered_factory):
        """Test response schema extraction."""
        responses = {
            "200": {
                "description": "Success",
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object"
                        }
                    }
                }
            }
        }
        
        result = layered_factory._extract_response_schemas(responses)
        assert result is not None

    def test_build_service_metadata(self, layered_factory):
        """Test service metadata building."""
        services = layered_factory._build_service_metadata()
        assert "get_test_data" in services
        service = services["get_test_data"]
        assert service["operationId"] == "get_test_data"
        assert service["http_method"] == "GET"
        assert service["path"] == "/test/endpoint"

    def test_should_include_operation(self, layered_factory):
        """Test operation inclusion logic."""
        # Test with no custom routes (should include all)
        assert layered_factory._should_include_operation("GET", "/test/endpoint") is True

    def test_matches_pattern(self, layered_factory):
        """Test pattern matching."""
        # Test exact match
        assert layered_factory._matches_pattern("/test/endpoint", "/test/endpoint") is True
        
        # Test regex pattern
        assert layered_factory._matches_pattern("/test/endpoint", ".*endpoint") is True
        
        # Test non-match
        assert layered_factory._matches_pattern("/test/endpoint", "/other/path") is False

    def test_get_type_info(self, layered_factory):
        """Test get_type_info method."""
        result = layered_factory.get_type_info("get_test_data")
        assert result["service"] == "get_test_data"
        assert "parameters" in result
        assert "requestBody" in result
        assert "responses" in result

    def test_get_type_info_invalid_service(self, layered_factory):
        """Test get_type_info with invalid service."""
        result = layered_factory.get_type_info("invalid_service")
        assert "error" in result
        assert "available_services" in result

    def test_get_service_info_all(self, layered_factory):
        """Test get_service_info without service parameter."""
        result = layered_factory.get_service_info()
        assert "available_services" in result
        assert "total_services" in result
        assert "usage" in result
        assert result["total_services"] == 1

    def test_get_service_info_specific(self, layered_factory):
        """Test get_service_info with specific service."""
        result = layered_factory.get_service_info("get_test_data")
        assert result["service"] == "get_test_data"
        assert "parameters" in result
        assert "schema_summary" in result

    def test_get_service_info_invalid_service(self, layered_factory):
        """Test get_service_info with invalid service."""
        result = layered_factory.get_service_info("invalid_service")
        assert "error" in result
        assert "available_services" in result

    @pytest.mark.asyncio
    async def test_make_tool_call(self, layered_factory, mock_client):
        """Test make_tool_call method."""
        # Mock the client response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": "success"}
        mock_client.request.return_value = mock_response

        request = {
            "path_params": {"id": "123"},
            "query_params": {"filter": "test"},
            "body": {"name": "test", "value": 42}
        }

        result = await layered_factory.make_tool_call("get_test_data", request)
        assert result["success"] is True
        assert result["service"] == "get_test_data"
        assert result["status_code"] == 200
        assert "data" in result

    @pytest.mark.asyncio
    async def test_make_tool_call_invalid_service(self, layered_factory):
        """Test make_tool_call with invalid service."""
        result = await layered_factory.make_tool_call("invalid_service")
        assert "error" in result
        assert "available_services" in result

    @pytest.mark.asyncio
    async def test_make_tool_call_error(self, layered_factory, mock_client):
        """Test make_tool_call with client error."""
        mock_client.request.side_effect = Exception("Connection error")

        result = await layered_factory.make_tool_call("get_test_data")
        assert result["success"] is False
        assert "error" in result

    def test_layered_factory_with_custom_routes(self, mock_openapi_spec, mock_client):
        """Test LayeredOpenAPIFactory with custom routes."""
        from fastmcp.server.openapi import RouteMap, MCPType
        
        custom_routes = [
            RouteMap(
                methods=["GET"],
                pattern=".*",
                mcp_type=MCPType.TOOL
            )
        ]
        
        factory = LayeredOpenAPIFactory(
            mock_openapi_spec, 
            mock_client, 
            custom_routes=custom_routes
        )
        
        assert factory.custom_routes == custom_routes

    def test_layered_factory_instructions(self, layered_factory):
        """Test that LayeredOpenAPIFactory has correct instructions."""
        instructions = layered_factory.instructions
        assert "get_service_info" in instructions
        assert "get_type_info" in instructions
        assert "make_tool_call" in instructions
        assert "Layered Tool Pattern" in instructions or "three main capabilities" in instructions
