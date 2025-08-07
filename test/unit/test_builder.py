import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import httpx
from mcp_composer.core.member_servers.builder import MCPServerBuilder
from mcp_composer.core.utils.validator import MemberServerType, ConfigKey, AuthStrategy


@pytest.mark.asyncio
async def test_build_from_client_success():
    config = {
        ConfigKey.ID: "srv",
        ConfigKey.TYPE: MemberServerType.CLIENT,
        ConfigKey.ENDPOINT: "http://api",
    }
    builder = MCPServerBuilder(config)
    with (
        patch("mcp_composer.core.member_servers.builder.Client") as mock_client,
        patch("mcp_composer.core.member_servers.builder.FastMCP") as mock_fastmcp,
    ):
        mock_fastmcp.as_proxy.return_value = "proxy"
        result = await builder._build_from_client()
        assert result == "proxy"


@pytest.mark.asyncio
async def test_build_from_client_with_headers():
    config = {
        ConfigKey.ID: "srv",
        ConfigKey.TYPE: MemberServerType.CLIENT,
        ConfigKey.ENDPOINT: "http://api",
        ConfigKey.HEADERS: {"Authorization": "Bearer token"},
    }
    builder = MCPServerBuilder(config)
    with (
        patch("mcp_composer.core.member_servers.builder.StreamableHttpTransport") as mock_transport,
        patch("mcp_composer.core.member_servers.builder.Client") as mock_client,
        patch("mcp_composer.core.member_servers.builder.FastMCP") as mock_fastmcp,
    ):
        mock_fastmcp.as_proxy.return_value = "proxy"
        result = await builder._build_from_client()
        assert result == "proxy"


@pytest.mark.asyncio
async def test_build_from_client_exception():
    config = {
        ConfigKey.ID: "srv",
        ConfigKey.TYPE: MemberServerType.CLIENT,
        ConfigKey.ENDPOINT: "http://api",
    }
    builder = MCPServerBuilder(config)
    with (
        patch("mcp_composer.core.member_servers.builder.Client") as mock_client,
        patch("mcp_composer.core.member_servers.builder.FastMCP") as mock_fastmcp,
    ):
        mock_fastmcp.as_proxy.side_effect = Exception("Connection failed")
        with pytest.raises(RuntimeError, match="Failed to build member MCP server 'srv'"):
            await builder._build_from_client()


@pytest.mark.asyncio
async def test_build_from_transport_http():
    config = {
        ConfigKey.ID: "srv",
        ConfigKey.TYPE: MemberServerType.HTTP,
        ConfigKey.ENDPOINT: "http://api",
    }
    builder = MCPServerBuilder(config)
    with (
        patch(
            "mcp_composer.core.member_servers.builder.StreamableHttpTransport"
        ) as mock_transport,
        patch("mcp_composer.core.member_servers.builder.Client") as mock_client,
        patch("mcp_composer.core.member_servers.builder.FastMCP") as mock_fastmcp,
    ):
        mock_fastmcp.as_proxy.return_value = "proxy"
        result = await builder._build_from_transport(MemberServerType.HTTP)
        assert result == "proxy"


@pytest.mark.asyncio
async def test_build_from_transport_sse():
    config = {
        ConfigKey.ID: "srv",
        ConfigKey.TYPE: MemberServerType.SSE,
        ConfigKey.ENDPOINT: "http://api",
    }
    builder = MCPServerBuilder(config)
    with (
        patch("mcp_composer.core.member_servers.builder.SSETransport") as mock_transport,
        patch("mcp_composer.core.member_servers.builder.Client") as mock_client,
        patch("mcp_composer.core.member_servers.builder.FastMCP") as mock_fastmcp,
    ):
        mock_fastmcp.as_proxy.return_value = "proxy"
        result = await builder._build_from_transport(MemberServerType.SSE)
        assert result == "proxy"


@pytest.mark.asyncio
async def test_build_from_transport_stdio():
    config = {
        ConfigKey.ID: "srv",
        ConfigKey.TYPE: MemberServerType.STDIO,
        ConfigKey.COMMAND: "test-command",
        ConfigKey.ARGS: ["arg1", "arg2"],
        ConfigKey.ENV: {"ENV_VAR": "value"},
        ConfigKey.CWD: "/test/path",
    }
    builder = MCPServerBuilder(config)
    with (
        patch("mcp_composer.core.member_servers.builder.StdioTransport") as mock_transport,
        patch("mcp_composer.core.member_servers.builder.Client") as mock_client,
        patch("mcp_composer.core.member_servers.builder.FastMCP") as mock_fastmcp,
    ):
        mock_fastmcp.as_proxy.return_value = "proxy"
        result = await builder._build_from_transport(MemberServerType.STDIO)
        assert result == "proxy"


@pytest.mark.asyncio
async def test_build_from_transport_http_with_oauth():
    config = {
        ConfigKey.ID: "srv",
        ConfigKey.TYPE: MemberServerType.HTTP,
        ConfigKey.ENDPOINT: "http://api",
        ConfigKey.AUTH: {"token_url": "http://api/oauth"},
        ConfigKey.HEADERS: {"Content-Type": "application/json"},
    }
    builder = MCPServerBuilder(config)
    with (
        patch("mcp_composer.core.member_servers.builder.StreamableHttpTransport") as mock_transport,
        patch("mcp_composer.core.member_servers.builder.Client") as mock_client,
        patch("mcp_composer.core.member_servers.builder.FastMCP") as mock_fastmcp,
        patch("mcp_composer.core.member_servers.builder.OAuth") as mock_oauth,
        patch("mcp_composer.core.member_servers.builder.FileTokenStorage") as mock_storage,
    ):
        mock_fastmcp.as_proxy.return_value = "proxy"
        result = await builder._build_from_transport(MemberServerType.HTTP)
        assert result == "proxy"


@pytest.mark.asyncio
async def test_build_from_transport_invalid():
    config = {ConfigKey.ID: "srv", ConfigKey.TYPE: "invalid"}
    builder = MCPServerBuilder(config)
    with pytest.raises(ValueError, match="Unsupported MCP type: invalid"):
        await builder._build_from_transport("invalid")


@pytest.mark.asyncio
async def test_build_from_openapi_with_spec_url():
    config = {
        ConfigKey.ID: "srv",
        ConfigKey.TYPE: MemberServerType.OPENAPI,
        ConfigKey.OPEN_API: {
            ConfigKey.ENDPOINT: "http://api",
            ConfigKey.SPEC_URL: "http://api/openapi.json",
        },
        ConfigKey.AUTH_STRATEGY: AuthStrategy.BASIC,
        ConfigKey.AUTH: {
            ConfigKey.USERNAME: "user",
            ConfigKey.PASSWORD: "pass",
        },
        ConfigKey.HEADERS: {"Content-Type": "application/json"},
    }
    builder = MCPServerBuilder(config)
    with (
        patch("mcp_composer.core.member_servers.builder.load_spec_from_url") as mock_load_spec,
        patch("mcp_composer.core.member_servers.builder.load_custom_mappings_from_json") as mock_load_mappings,
        patch("mcp_composer.core.member_servers.builder.FastMCP") as mock_fastmcp,
        patch("mcp_composer.core.member_servers.builder.jsonref") as mock_jsonref,
        patch("mcp_composer.core.member_servers.builder.httpx.AsyncClient") as mock_client,
    ):
        mock_load_spec.return_value = {"openapi": "3.0.0"}
        mock_load_mappings.return_value = []
        mock_jsonref.loads.return_value = {"openapi": "3.0.0"}
        mock_fastmcp.from_openapi.return_value = "mcp_server"
        
        result = await builder._build_from_openapi()
        assert result == "mcp_server"


@pytest.mark.asyncio
async def test_build_from_openapi_with_spec_filepath():
    config = {
        ConfigKey.ID: "srv",
        ConfigKey.TYPE: MemberServerType.OPENAPI,
        ConfigKey.OPEN_API: {
            ConfigKey.ENDPOINT: "http://api",
            ConfigKey.SPEC_FILEPATH: "/path/to/spec.json",
        },
        ConfigKey.AUTH_STRATEGY: AuthStrategy.BEARER,
        ConfigKey.AUTH: {
            ConfigKey.TOKEN: "bearer_token",
        },
    }
    builder = MCPServerBuilder(config)
    with (
        patch("mcp_composer.core.member_servers.builder.load_json") as mock_load_json,
        patch("mcp_composer.core.member_servers.builder.load_custom_mappings_from_json") as mock_load_mappings,
        patch("mcp_composer.core.member_servers.builder.FastMCP") as mock_fastmcp,
        patch("mcp_composer.core.member_servers.builder.jsonref") as mock_jsonref,
        patch("mcp_composer.core.member_servers.builder.httpx.AsyncClient") as mock_client,
    ):
        mock_load_json.return_value = {"openapi": "3.0.0"}
        mock_load_mappings.return_value = []
        mock_jsonref.loads.return_value = {"openapi": "3.0.0"}
        mock_fastmcp.from_openapi.return_value = "mcp_server"
        
        result = await builder._build_from_openapi()
        assert result == "mcp_server"


@pytest.mark.asyncio
async def test_build_from_openapi_with_custom_routes():
    config = {
        ConfigKey.ID: "srv",
        ConfigKey.TYPE: MemberServerType.OPENAPI,
        ConfigKey.OPEN_API: {
            ConfigKey.ENDPOINT: "http://api",
            ConfigKey.SPEC_URL: "http://api/openapi.json",
            ConfigKey.CUSTOM_ROUTES: "/path/to/routes.json",
        },
        ConfigKey.AUTH_STRATEGY: AuthStrategy.APITOKEN,
        ConfigKey.AUTH: {
            ConfigKey.AUTH_PREFIX: "ApiKey",
            ConfigKey.TOKEN: "api_token",
        },
    }
    builder = MCPServerBuilder(config)
    with (
        patch("mcp_composer.core.member_servers.builder.load_spec_from_url") as mock_load_spec,
        patch("mcp_composer.core.member_servers.builder.load_custom_mappings_from_json") as mock_load_mappings,
        patch("mcp_composer.core.member_servers.builder.FastMCP") as mock_fastmcp,
        patch("mcp_composer.core.member_servers.builder.jsonref") as mock_jsonref,
        patch("mcp_composer.core.member_servers.builder.httpx.AsyncClient") as mock_client,
    ):
        mock_load_spec.return_value = {"openapi": "3.0.0"}
        mock_load_mappings.return_value = [{"route": "/custom", "method": "GET"}]
        mock_jsonref.loads.return_value = {"openapi": "3.0.0"}
        mock_fastmcp.from_openapi.return_value = "mcp_server"
        
        result = await builder._build_from_openapi()
        assert result == "mcp_server"


@pytest.mark.asyncio
async def test_build_from_openapi_with_dynamic_bearer():
    config = {
        ConfigKey.ID: "srv",
        ConfigKey.TYPE: MemberServerType.OPENAPI,
        ConfigKey.OPEN_API: {
            ConfigKey.ENDPOINT: "http://api",
            ConfigKey.SPEC_URL: "http://api/openapi.json",
        },
        ConfigKey.AUTH_STRATEGY: AuthStrategy.DYNAMIC_BEARER,
        ConfigKey.AUTH: {
            ConfigKey.Token_URL: "http://api/token",
            ConfigKey.APIKEY: "api_key",
            ConfigKey.MEDIA_TYPE: "application/json",
        },
    }
    builder = MCPServerBuilder(config)
    with (
        patch("mcp_composer.core.member_servers.builder.load_spec_from_url") as mock_load_spec,
        patch("mcp_composer.core.member_servers.builder.load_custom_mappings_from_json") as mock_load_mappings,
        patch("mcp_composer.core.member_servers.builder.FastMCP") as mock_fastmcp,
        patch("mcp_composer.core.member_servers.builder.jsonref") as mock_jsonref,
        patch("mcp_composer.core.member_servers.builder.DynamicTokenClient") as mock_dynamic_client,
    ):
        mock_load_spec.return_value = {"openapi": "3.0.0"}
        mock_load_mappings.return_value = []
        mock_jsonref.loads.return_value = {"openapi": "3.0.0"}
        mock_fastmcp.from_openapi.return_value = "mcp_server"
        mock_dynamic_client.return_value = "dynamic_client"
        
        result = await builder._build_from_openapi()
        assert result == "mcp_server"


@pytest.mark.asyncio
async def test_build_from_openapi_with_apikey():
    config = {
        ConfigKey.ID: "srv",
        ConfigKey.TYPE: MemberServerType.OPENAPI,
        ConfigKey.OPEN_API: {
            ConfigKey.ENDPOINT: "http://api",
            ConfigKey.SPEC_URL: "http://api/openapi.json",
        },
        ConfigKey.AUTH_STRATEGY: AuthStrategy.APIKEY,
        ConfigKey.AUTH: {
            ConfigKey.AUTH_PREFIX: "X-API-Key",
            ConfigKey.APIKEY: "api_key_value",
        },
    }
    builder = MCPServerBuilder(config)
    with (
        patch("mcp_composer.core.member_servers.builder.load_spec_from_url") as mock_load_spec,
        patch("mcp_composer.core.member_servers.builder.load_custom_mappings_from_json") as mock_load_mappings,
        patch("mcp_composer.core.member_servers.builder.FastMCP") as mock_fastmcp,
        patch("mcp_composer.core.member_servers.builder.jsonref") as mock_jsonref,
        patch("mcp_composer.core.member_servers.builder.httpx.AsyncClient") as mock_client,
    ):
        mock_load_spec.return_value = {"openapi": "3.0.0"}
        mock_load_mappings.return_value = []
        mock_jsonref.loads.return_value = {"openapi": "3.0.0"}
        mock_fastmcp.from_openapi.return_value = "mcp_server"
        
        result = await builder._build_from_openapi()
        assert result == "mcp_server"


@pytest.mark.asyncio
async def test_build_from_openapi_with_jsessionid_success():
    config = {
        ConfigKey.ID: "srv",
        ConfigKey.TYPE: MemberServerType.OPENAPI,
        ConfigKey.OPEN_API: {
            ConfigKey.ENDPOINT: "http://api",
            ConfigKey.SPEC_URL: "http://api/openapi.json",
        },
        ConfigKey.AUTH_STRATEGY: AuthStrategy.JSESSIONID.value,
        ConfigKey.AUTH: {
            ConfigKey.LOGIN_URL: "http://api/login",
            ConfigKey.USERNAME: "user",
            ConfigKey.PASSWORD: "pass",
        },
    }
    builder = MCPServerBuilder(config)
    with (
        patch("mcp_composer.core.member_servers.builder.load_spec_from_url") as mock_load_spec,
        patch("mcp_composer.core.member_servers.builder.load_custom_mappings_from_json") as mock_load_mappings,
        patch("mcp_composer.core.member_servers.builder.FastMCP") as mock_fastmcp,
        patch("mcp_composer.core.member_servers.builder.jsonref") as mock_jsonref,
        patch("mcp_composer.core.member_servers.builder.DynamicTokenManager") as mock_token_manager,
    ):
        mock_load_spec.return_value = {"openapi": "3.0.0"}
        mock_load_mappings.return_value = []
        mock_jsonref.loads.return_value = {"openapi": "3.0.0"}
        mock_fastmcp.from_openapi.return_value = "mcp_server"
        
        mock_manager_instance = AsyncMock()
        mock_manager_instance.get_authenticated_http_client_for_jessonid.return_value = "authenticated_client"
        mock_token_manager.return_value = mock_manager_instance
        
        result = await builder._build_from_openapi()
        assert result == "mcp_server"


@pytest.mark.asyncio
async def test_build_from_openapi_with_jsessionid_keyerror():
    config = {
        ConfigKey.ID: "srv",
        ConfigKey.TYPE: MemberServerType.OPENAPI,
        ConfigKey.OPEN_API: {
            ConfigKey.ENDPOINT: "http://api",
            ConfigKey.SPEC_URL: "http://api/openapi.json",
        },
        ConfigKey.AUTH_STRATEGY: AuthStrategy.JSESSIONID.value,
        ConfigKey.AUTH: {
            # Missing required config
        },
    }
    builder = MCPServerBuilder(config)
    with (
        patch("mcp_composer.core.member_servers.builder.load_spec_from_url") as mock_load_spec,
        patch("mcp_composer.core.member_servers.builder.load_custom_mappings_from_json") as mock_load_mappings,
        patch("mcp_composer.core.member_servers.builder.FastMCP") as mock_fastmcp,
        patch("mcp_composer.core.member_servers.builder.jsonref") as mock_jsonref,
        patch("mcp_composer.core.member_servers.builder.DynamicTokenManager") as mock_token_manager,
    ):
        mock_load_spec.return_value = {"openapi": "3.0.0"}
        mock_load_mappings.return_value = []
        mock_jsonref.loads.return_value = {"openapi": "3.0.0"}
        mock_fastmcp.from_openapi.return_value = "mcp_server"
        
        mock_manager_instance = AsyncMock()
        mock_manager_instance.get_authenticated_http_client_for_jessonid.side_effect = KeyError("missing_key")
        mock_token_manager.return_value = mock_manager_instance
        
        result = await builder._build_from_openapi()
        assert result == "mcp_server"


@pytest.mark.asyncio
async def test_build_from_openapi_with_jsessionid_httperror():
    config = {
        ConfigKey.ID: "srv",
        ConfigKey.TYPE: MemberServerType.OPENAPI,
        ConfigKey.OPEN_API: {
            ConfigKey.ENDPOINT: "http://api",
            ConfigKey.SPEC_URL: "http://api/openapi.json",
        },
        ConfigKey.AUTH_STRATEGY: AuthStrategy.JSESSIONID.value,
        ConfigKey.AUTH: {
            ConfigKey.LOGIN_URL: "http://api/login",
            ConfigKey.USERNAME: "user",
            ConfigKey.PASSWORD: "pass",
        },
    }
    builder = MCPServerBuilder(config)
    with (
        patch("mcp_composer.core.member_servers.builder.load_spec_from_url") as mock_load_spec,
        patch("mcp_composer.core.member_servers.builder.load_custom_mappings_from_json") as mock_load_mappings,
        patch("mcp_composer.core.member_servers.builder.FastMCP") as mock_fastmcp,
        patch("mcp_composer.core.member_servers.builder.jsonref") as mock_jsonref,
        patch("mcp_composer.core.member_servers.builder.DynamicTokenManager") as mock_token_manager,
    ):
        mock_load_spec.return_value = {"openapi": "3.0.0"}
        mock_load_mappings.return_value = []
        mock_jsonref.loads.return_value = {"openapi": "3.0.0"}
        mock_fastmcp.from_openapi.return_value = "mcp_server"
        
        mock_manager_instance = AsyncMock()
        mock_manager_instance.get_authenticated_http_client_for_jessonid.side_effect = httpx.HTTPError("HTTP error")
        mock_token_manager.return_value = mock_manager_instance
        
        result = await builder._build_from_openapi()
        assert result == "mcp_server"


@pytest.mark.asyncio
async def test_build_from_openapi_with_jsessionid_general_exception():
    config = {
        ConfigKey.ID: "srv",
        ConfigKey.TYPE: MemberServerType.OPENAPI,
        ConfigKey.OPEN_API: {
            ConfigKey.ENDPOINT: "http://api",
            ConfigKey.SPEC_URL: "http://api/openapi.json",
        },
        ConfigKey.AUTH_STRATEGY: AuthStrategy.JSESSIONID.value,
        ConfigKey.AUTH: {
            ConfigKey.LOGIN_URL: "http://api/login",
            ConfigKey.USERNAME: "user",
            ConfigKey.PASSWORD: "pass",
        },
    }
    builder = MCPServerBuilder(config)
    with (
        patch("mcp_composer.core.member_servers.builder.load_spec_from_url") as mock_load_spec,
        patch("mcp_composer.core.member_servers.builder.load_custom_mappings_from_json") as mock_load_mappings,
        patch("mcp_composer.core.member_servers.builder.FastMCP") as mock_fastmcp,
        patch("mcp_composer.core.member_servers.builder.jsonref") as mock_jsonref,
        patch("mcp_composer.core.member_servers.builder.DynamicTokenManager") as mock_token_manager,
    ):
        mock_load_spec.return_value = {"openapi": "3.0.0"}
        mock_load_mappings.return_value = []
        mock_jsonref.loads.return_value = {"openapi": "3.0.0"}
        mock_fastmcp.from_openapi.return_value = "mcp_server"
        
        mock_manager_instance = AsyncMock()
        mock_manager_instance.get_authenticated_http_client_for_jessonid.side_effect = Exception("Unexpected error")
        mock_token_manager.return_value = mock_manager_instance
        
        result = await builder._build_from_openapi()
        assert result == "mcp_server"


@pytest.mark.asyncio
async def test_build_from_openapi_no_spec():
    config = {
        ConfigKey.ID: "srv",
        ConfigKey.TYPE: MemberServerType.OPENAPI,
        ConfigKey.OPEN_API: {
            ConfigKey.ENDPOINT: "http://api",
            # Missing both SPEC_URL and SPEC_FILEPATH
        },
    }
    builder = MCPServerBuilder(config)
    with pytest.raises(NotImplementedError, match="Spec is missing"):
        await builder._build_from_openapi()


@pytest.mark.asyncio
async def test_build_from_graphql():
    config = {
        ConfigKey.ID: "graphql_server",
        ConfigKey.TYPE: MemberServerType.GRAPHQL,
        ConfigKey.ENDPOINT: "http://graphql-api",
    }
    builder = MCPServerBuilder(config)
    with (
        patch("mcp_composer.core.member_servers.builder.GraphQLTool") as mock_graphql_tool,
        patch("mcp_composer.core.member_servers.builder.FastMCP") as mock_fastmcp,
    ):
        mock_tool_instance = MagicMock()
        mock_graphql_tool.return_value = mock_tool_instance
        mock_mcp_instance = MagicMock()
        mock_fastmcp.return_value = mock_mcp_instance
        
        result = await builder._build_from_graphql()
        assert result == mock_mcp_instance
        mock_graphql_tool.assert_called_once_with(config)
        mock_mcp_instance.add_tool.assert_called_once_with(mock_tool_instance)


@pytest.mark.asyncio
async def test_build_from_local_file():
    config = {
        ConfigKey.ID: "local_server",
        ConfigKey.TYPE: MemberServerType.LOCAL,
        ConfigKey.PROMPT_PATH: "/path/to/prompts.json",
    }
    builder = MCPServerBuilder(config)
    with (
        patch("mcp_composer.core.member_servers.builder.load_json") as mock_load_json,
        patch("mcp_composer.core.member_servers.builder.build_prompt_from_dict") as mock_build_prompt,
        patch("mcp_composer.core.member_servers.builder.FastMCP") as mock_fastmcp,
    ):
        mock_load_json.return_value = [
            {"name": "prompt1", "content": "test prompt 1"},
            {"name": "prompt2", "content": "test prompt 2"},
        ]
        mock_prompt1 = MagicMock()
        mock_prompt2 = MagicMock()
        mock_build_prompt.side_effect = [mock_prompt1, mock_prompt2]
        mock_mcp_instance = MagicMock()
        mock_fastmcp.return_value = mock_mcp_instance
        
        result = await builder._build_from_local_file()
        assert result == mock_mcp_instance
        assert mock_mcp_instance.add_prompt.call_count == 2
        mock_mcp_instance.add_prompt.assert_any_call(mock_prompt1)
        mock_mcp_instance.add_prompt.assert_any_call(mock_prompt2)


def test_build_from_fastapi():
    config = {
        ConfigKey.ID: "fastapi_server",
        ConfigKey.TYPE: "fastapi",
    }
    builder = MCPServerBuilder(config)
    with pytest.raises(NotImplementedError, match="Local file loading not yet supported"):
        builder._build_from_fastapi()


@pytest.mark.asyncio
async def test_build_openapi():
    config = {
        ConfigKey.ID: "srv",
        ConfigKey.TYPE: MemberServerType.OPENAPI,
        ConfigKey.OPEN_API: {
            ConfigKey.ENDPOINT: "http://api",
            ConfigKey.SPEC_URL: "http://api/openapi.json",
        },
    }
    builder = MCPServerBuilder(config)
    with (
        patch("mcp_composer.core.member_servers.builder.MCPServerBuilder._build_from_openapi") as mock_build_openapi,
    ):
        mock_build_openapi.return_value = "mcp_server"
        result = await builder.build()
        assert result == "mcp_server"


@pytest.mark.asyncio
async def test_build_graphql():
    config = {
        ConfigKey.ID: "srv",
        ConfigKey.TYPE: MemberServerType.GRAPHQL,
    }
    builder = MCPServerBuilder(config)
    with (
        patch("mcp_composer.core.member_servers.builder.MCPServerBuilder._build_from_graphql") as mock_build_graphql,
    ):
        mock_build_graphql.return_value = "mcp_server"
        result = await builder.build()
        assert result == "mcp_server"


@pytest.mark.asyncio
async def test_build_local():
    config = {
        ConfigKey.ID: "srv",
        ConfigKey.TYPE: MemberServerType.LOCAL,
        ConfigKey.PROMPT_PATH: "/path/to/prompts.json",
    }
    builder = MCPServerBuilder(config)
    with (
        patch("mcp_composer.core.member_servers.builder.MCPServerBuilder._build_from_local_file") as mock_build_local,
    ):
        mock_build_local.return_value = "mcp_server"
        result = await builder.build()
        assert result == "mcp_server"


@pytest.mark.asyncio
async def test_build_fastapi():
    config = {
        ConfigKey.ID: "srv",
        ConfigKey.TYPE: "fastapi",
    }
    builder = MCPServerBuilder(config)
    with (
        patch("mcp_composer.core.member_servers.builder.MCPServerBuilder._build_from_fastapi") as mock_build_fastapi,
    ):
        mock_build_fastapi.return_value = "mcp_server"
        result = await builder.build()
        assert result == "mcp_server"


@pytest.mark.asyncio
async def test_build_invalid_type():
    config = {ConfigKey.ID: "srv", ConfigKey.TYPE: "invalid"}
    builder = MCPServerBuilder(config)
    with pytest.raises(ValueError, match="Unsupported MCP type: invalid"):
        await builder.build()


def test_mcpserver_builder_initialization():
    config = {
        ConfigKey.ID: "test_server",
        ConfigKey.TYPE: MemberServerType.HTTP,
        ConfigKey.ENDPOINT: "http://test-api",
    }
    builder = MCPServerBuilder(config)
    assert builder.config == config
    assert builder.mcp_id == "test_server"
    assert builder.mcp_type == MemberServerType.HTTP
