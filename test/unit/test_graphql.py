"""Test module for graphql.py"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
import httpx
import json
from mcp_composer.core.tools.graphql import (
    fetch_graphql_schema,
    create_tools,
    GRAPHQL_INTROSPECTION_QUERY,
    config,
    http_client
)


class TestGraphQL:
    """Test cases for GraphQL functionality"""

    @pytest.fixture
    def mock_schema(self):
        """Mock GraphQL schema"""
        return {
            "queryType": {"name": "Query"},
            "types": [
                {
                    "name": "Query",
                    "kind": "OBJECT",
                    "fields": [
                        {
                            "name": "country",
                            "args": [
                                {
                                    "name": "code",
                                    "type": {"name": "String", "kind": "SCALAR"}
                                }
                            ],
                            "type": {"name": "Country", "kind": "OBJECT"}
                        },
                        {
                            "name": "countries",
                            "args": [],
                            "type": {"name": "Country", "kind": "LIST"}
                        }
                    ]
                },
                {
                    "name": "Country",
                    "kind": "OBJECT",
                    "fields": []
                }
            ]
        }

    @pytest.mark.asyncio
    async def test_fetch_graphql_schema_success(self):
        """Test successful schema fetching"""
        mock_response = Mock()
        mock_response.json.return_value = {"data": {"__schema": {"queryType": {"name": "Query"}}}}
        mock_response.raise_for_status.return_value = None

        with patch.object(http_client, 'post', return_value=mock_response):
            result = await fetch_graphql_schema()

            assert result == {"queryType": {"name": "Query"}}
            http_client.post.assert_called_once_with("", json={"query": GRAPHQL_INTROSPECTION_QUERY})

    @pytest.mark.asyncio
    async def test_fetch_graphql_schema_http_error(self):
        """Test schema fetching with HTTP error"""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError("404", request=Mock(), response=mock_response)

        with patch.object(http_client, 'post', return_value=mock_response):
            with pytest.raises(httpx.HTTPStatusError):
                await fetch_graphql_schema()

    @pytest.mark.asyncio
    async def test_create_tools_with_args(self, mock_schema):
        """Test creating tools with arguments"""
        mock_response = Mock()
        mock_response.json.return_value = {"data": {"country": {"__typename": "Country"}}}
        mock_response.raise_for_status.return_value = None

        with patch.object(http_client, 'post', return_value=mock_response):
            tools = await create_tools(mock_schema)

            assert len(tools) == 2

            # Test the first tool (country with args)
            country_tool = tools[0]
            assert country_tool.name == "country"
            assert "Query country" in country_tool.description

    @pytest.mark.asyncio
    async def test_create_tools_without_args(self, mock_schema):
        """Test creating tools without arguments"""
        mock_response = Mock()
        mock_response.json.return_value = {"data": {"countries": {"__typename": "Country"}}}
        mock_response.raise_for_status.return_value = None

        with patch.object(http_client, 'post', return_value=mock_response):
            tools = await create_tools(mock_schema)

            # Test the second tool (countries without args)
            countries_tool = tools[1]
            assert countries_tool.name == "countries"
            assert "Query countries" in countries_tool.description

    @pytest.mark.asyncio
    async def test_create_tools_http_error(self, mock_schema):
        """Test tool execution with HTTP error"""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError("500", request=Mock(), response=mock_response)

        with patch.object(http_client, 'post', return_value=mock_response):
            tools = await create_tools(mock_schema)
            country_tool = tools[0]

            # Test that executing the tool raises the HTTP error
            with pytest.raises(httpx.HTTPStatusError):
                await country_tool.run({"code": "CA"})

    def test_config_structure(self):
        """Test that config has expected structure"""
        assert "id" in config
        assert "type" in config
        assert "graphql" in config
        assert "auth_strategy" in config
        assert "auth" in config
        assert config["type"] == "graphql"
        assert config["auth_strategy"] == "none"

    def test_graphql_introspection_query_exists(self):
        """Test that introspection query is defined"""
        assert GRAPHQL_INTROSPECTION_QUERY is not None
        assert "IntrospectionQuery" in GRAPHQL_INTROSPECTION_QUERY
        assert "__schema" in GRAPHQL_INTROSPECTION_QUERY

    def test_http_client_initialization(self):
        """Test that HTTP client is properly initialized"""
        assert http_client is not None
        assert hasattr(http_client, 'base_url')
        assert hasattr(http_client, 'headers')

    @pytest.mark.asyncio
    async def test_tool_execution_with_args(self, mock_schema):
        """Test tool execution with arguments"""
        mock_response = Mock()
        mock_response.json.return_value = {"data": {"country": {"name": "Canada"}}}
        mock_response.raise_for_status.return_value = None

        with patch.object(http_client, 'post', return_value=mock_response):
            tools = await create_tools(mock_schema)
            country_tool = tools[0]

            # Execute the tool
            result = await country_tool.run({"code": "CA"})

            # Access the content from the ToolResult and parse JSON
            result_data = json.loads(result.content[0].text)
            assert result_data == {"data": {"country": {"name": "Canada"}}}
            http_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_tool_execution_without_args(self, mock_schema):
        """Test tool execution without arguments"""
        mock_response = Mock()
        mock_response.json.return_value = {"data": {"countries": [{"name": "Canada"}]}}
        mock_response.raise_for_status.return_value = None

        with patch.object(http_client, 'post', return_value=mock_response):
            tools = await create_tools(mock_schema)
            countries_tool = tools[1]

            # Execute the tool
            result = await countries_tool.run({})

            # Access the content from the ToolResult and parse JSON
            result_data = json.loads(result.content[0].text)
            assert result_data == {"data": {"countries": [{"name": "Canada"}]}}
            http_client.post.assert_called_once() 