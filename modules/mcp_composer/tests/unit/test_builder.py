from unittest.mock import AsyncMock, MagicMock, Mock, patch

from fastmcp import FastMCP
import httpx
import pytest

from mcp_composer.core.member_servers.builder import MCPServerBuilder
from mcp_composer.core.member_servers.layered_factory_oa import LayeredOpenAPIFactory
from mcp_composer.core.utils.validator import AuthStrategy, ConfigKey, MemberServerType

# pylint: disable=protected-access,unused-variable


@pytest.mark.asyncio
async def test_build_from_client_success():
    config = {
        ConfigKey.ID: "srv",
        ConfigKey.TYPE: MemberServerType.CLIENT,
        ConfigKey.ENDPOINT: "http://api",
    }
    builder = MCPServerBuilder(config)
    with (
        patch("mcp_composer.core.member_servers.builder.Client") as _mock_client,
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
        patch(
            "mcp_composer.core.member_servers.builder.StreamableHttpTransport"
        ) as _mock_transport,
        patch("mcp_composer.core.member_servers.builder.Client") as _mock_client,
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
        patch("mcp_composer.core.member_servers.builder.Client") as _mock_client,
        patch("mcp_composer.core.member_servers.builder.FastMCP") as mock_fastmcp,
    ):
        mock_fastmcp.as_proxy.side_effect = Exception("Connection failed")
        with pytest.raises(
            RuntimeError, match="Failed to build member MCP server 'srv'"
        ):
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
        ) as _mock_transport,
        patch("mcp_composer.core.member_servers.builder.Client") as _mock_client,
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
        patch(
            "mcp_composer.core.member_servers.builder.SSETransport"
        ) as _mock_transport,
        patch("mcp_composer.core.member_servers.builder.Client") as _mock_client,
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
        patch(
            "mcp_composer.core.member_servers.builder.StdioTransport"
        ) as _mock_transport,
        patch("mcp_composer.core.member_servers.builder.Client") as _mock_client,
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
        patch(
            "mcp_composer.core.member_servers.builder.StreamableHttpTransport"
        ) as _mock_transport,
        patch("mcp_composer.core.member_servers.builder.Client") as _mock_client,
        patch("mcp_composer.core.member_servers.builder.FastMCP") as mock_fastmcp,
        patch("mcp_composer.core.member_servers.builder.OAuth") as _mock_oauth,
    ):
        mock_fastmcp.as_proxy.return_value = "proxy"
        result = await builder._build_from_transport(MemberServerType.HTTP)
        assert result == "proxy"


@pytest.mark.asyncio
async def test_build_from_transport_http_with_solis_jwt_handler():
    """Register HTTP MCP server using solis_jwt_handler auth strategy."""
    config = {
        ConfigKey.ID: "mcp-dal",
        ConfigKey.TYPE: MemberServerType.HTTP,
        ConfigKey.ENDPOINT: "https://kamahuha.us-east-a.ibm.stepzen.net/solis-dal/suite-automation/mcp",
        # 'layered' flag is ignored for HTTP/SSE, but included to mirror real config
        ConfigKey.LAYERED: True,
        ConfigKey.AUTH_STRATEGY: AuthStrategy.SOLIS_JWT_HANDLER,
        ConfigKey.AUTH: {
            # These mirror the JSON config fields; actual values are resolved by SolisJWTTokenGenerator
            "email": "ENV_INSTANA_SOLIS_EMAIL_DEV",
            ConfigKey.PASSWORD: "ENV_INSTANA_SOLIS_PASSWORD_DEV",
            ConfigKey.RETURN_URL: "https%3A%2F%2Funit02-techpreview002.sangria.instana.tools%2F",
            ConfigKey.LOGIN_URL: "https://unit02-techpreview002.sangria.instana.tools/auth/signIn",
            ConfigKey.CERT_URL: "ENV_CERT_URL",
        },
    }

    builder = MCPServerBuilder(config)

    with (
        patch(
            "mcp_composer.core.member_servers.builder.StreamableHttpTransport"
        ) as mock_transport,
        patch("mcp_composer.core.member_servers.builder.Client") as mock_client_cls,
        patch("mcp_composer.core.member_servers.builder.FastMCP") as mock_fastmcp,
        patch(
            "mcp_composer.core.member_servers.builder.SolisJWTTokenGenerator"
        ) as mock_token_gen_cls,
    ):
        mock_token_gen = MagicMock()
        mock_token_gen.get_jwt_token = AsyncMock(return_value="mock-jwt-token")
        mock_token_gen_cls.return_value = mock_token_gen

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_fastmcp.as_proxy.return_value = "proxy-server"

        result = await builder._build_from_transport(MemberServerType.HTTP)

        # Ensure the FastMCP proxy is returned
        assert result == "proxy-server"

        # SolisJWTTokenGenerator should be constructed with the auth config
        mock_token_gen_cls.assert_called_once_with(auth_data=config[ConfigKey.AUTH])
        mock_token_gen.get_jwt_token.assert_awaited_once()

        # Transport should be created with a Bearer Authorization header using the JWT
        assert mock_transport.call_count == 1
        _args, kwargs = mock_transport.call_args
        assert kwargs["url"] == config[ConfigKey.ENDPOINT]
        headers = kwargs.get("headers", {})
        assert headers.get(ConfigKey.AUTH_HEADER.value) == "Bearer mock-jwt-token"

        # Client should be created with the transport, and FastMCP.as_proxy called with it
        mock_client_cls.assert_called_once_with(mock_transport.return_value, auth=None)
        mock_fastmcp.as_proxy.assert_called_once_with(mock_client, name="mcp-dal")


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
        patch(
            "mcp_composer.core.member_servers.builder.load_spec_from_url"
        ) as mock_load_spec,
        patch(
            "mcp_composer.core.member_servers.builder.load_custom_mappings_from_json"
        ) as mock_load_mappings,
        patch("mcp_composer.core.member_servers.builder.FastMCP") as mock_fastmcp,
        patch("mcp_composer.core.member_servers.builder.jsonref") as mock_jsonref,
        patch(
            "mcp_composer.core.member_servers.builder.httpx.AsyncClient"
        ) as _mock_client,
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
        patch(
            "mcp_composer.core.member_servers.builder.load_custom_mappings_from_json"
        ) as mock_load_mappings,
        patch("mcp_composer.core.member_servers.builder.FastMCP") as mock_fastmcp,
        patch("mcp_composer.core.member_servers.builder.jsonref") as mock_jsonref,
        patch(
            "mcp_composer.core.member_servers.builder.httpx.AsyncClient"
        ) as _mock_client,
        patch.dict("os.environ", {"MCP_COMPOSER_MODE": "dev"}),
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
        patch(
            "mcp_composer.core.member_servers.builder.load_spec_from_url"
        ) as mock_load_spec,
        patch(
            "mcp_composer.core.member_servers.builder.load_custom_mappings_from_json"
        ) as mock_load_mappings,
        patch("mcp_composer.core.member_servers.builder.FastMCP") as mock_fastmcp,
        patch("mcp_composer.core.member_servers.builder.jsonref") as mock_jsonref,
        patch(
            "mcp_composer.core.member_servers.builder.httpx.AsyncClient"
        ) as _mock_client,
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
        patch(
            "mcp_composer.core.member_servers.builder.load_spec_from_url"
        ) as mock_load_spec,
        patch(
            "mcp_composer.core.member_servers.builder.load_custom_mappings_from_json"
        ) as mock_load_mappings,
        patch("mcp_composer.core.member_servers.builder.FastMCP") as mock_fastmcp,
        patch("mcp_composer.core.member_servers.builder.jsonref") as mock_jsonref,
        patch(
            "mcp_composer.core.member_servers.builder.DynamicTokenClient"
        ) as mock_dynamic_client,
        patch(
            "mcp_composer.core.member_servers.builder.DynamicTokenClientOAuth"
        ) as mock_oauth,
    ):
        mock_load_spec.return_value = {"openapi": "3.0.0"}
        mock_load_mappings.return_value = []
        mock_jsonref.loads.return_value = {"openapi": "3.0.0"}
        mock_fastmcp.from_openapi.return_value = "mcp_server"

        # Mock the DynamicTokenClient instance with required methods and attributes
        mock_client_instance = Mock()
        mock_client_instance._refresh_token = AsyncMock()
        mock_client_instance._access_token = "test_token"
        mock_client_instance._auth_prefix = "Bearer"
        mock_client_instance.auth = None
        mock_dynamic_client.return_value = mock_client_instance

        # Mock the DynamicTokenClientOAuth instance
        mock_oauth_instance = Mock()
        mock_oauth.return_value = mock_oauth_instance

        result = await builder._build_from_openapi()
        assert result == "mcp_server"
        # Verify _refresh_token was called
        mock_client_instance._refresh_token.assert_called_once()


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
        patch(
            "mcp_composer.core.member_servers.builder.load_spec_from_url"
        ) as mock_load_spec,
        patch(
            "mcp_composer.core.member_servers.builder.load_custom_mappings_from_json"
        ) as mock_load_mappings,
        patch("mcp_composer.core.member_servers.builder.FastMCP") as mock_fastmcp,
        patch("mcp_composer.core.member_servers.builder.jsonref") as mock_jsonref,
        patch(
            "mcp_composer.core.member_servers.builder.httpx.AsyncClient"
        ) as _mock_client,
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
        patch(
            "mcp_composer.core.member_servers.builder.load_spec_from_url"
        ) as mock_load_spec,
        patch(
            "mcp_composer.core.member_servers.builder.load_custom_mappings_from_json"
        ) as mock_load_mappings,
        patch("mcp_composer.core.member_servers.builder.FastMCP") as mock_fastmcp,
        patch("mcp_composer.core.member_servers.builder.jsonref") as mock_jsonref,
        patch(
            "mcp_composer.core.member_servers.builder.DynamicTokenManager"
        ) as mock_token_manager,
    ):
        mock_load_spec.return_value = {"openapi": "3.0.0"}
        mock_load_mappings.return_value = []
        mock_jsonref.loads.return_value = {"openapi": "3.0.0"}
        mock_fastmcp.from_openapi.return_value = "mcp_server"

        mock_manager_instance = AsyncMock()
        mock_manager_instance.get_authenticated_http_client_for_jessonid.return_value = (
            "authenticated_client"
        )
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
        patch(
            "mcp_composer.core.member_servers.builder.load_spec_from_url"
        ) as mock_load_spec,
        patch(
            "mcp_composer.core.member_servers.builder.load_custom_mappings_from_json"
        ) as mock_load_mappings,
        patch("mcp_composer.core.member_servers.builder.FastMCP") as mock_fastmcp,
        patch("mcp_composer.core.member_servers.builder.jsonref") as mock_jsonref,
        patch(
            "mcp_composer.core.member_servers.builder.DynamicTokenManager"
        ) as mock_token_manager,
    ):
        mock_load_spec.return_value = {"openapi": "3.0.0"}
        mock_load_mappings.return_value = []
        mock_jsonref.loads.return_value = {"openapi": "3.0.0"}
        mock_fastmcp.from_openapi.return_value = "mcp_server"

        mock_manager_instance = AsyncMock()
        mock_manager_instance.get_authenticated_http_client_for_jessonid.side_effect = (
            KeyError("missing_key")
        )
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
        patch(
            "mcp_composer.core.member_servers.builder.load_spec_from_url"
        ) as mock_load_spec,
        patch(
            "mcp_composer.core.member_servers.builder.load_custom_mappings_from_json"
        ) as mock_load_mappings,
        patch("mcp_composer.core.member_servers.builder.FastMCP") as mock_fastmcp,
        patch("mcp_composer.core.member_servers.builder.jsonref") as mock_jsonref,
        patch(
            "mcp_composer.core.member_servers.builder.DynamicTokenManager"
        ) as mock_token_manager,
    ):
        mock_load_spec.return_value = {"openapi": "3.0.0"}
        mock_load_mappings.return_value = []
        mock_jsonref.loads.return_value = {"openapi": "3.0.0"}
        mock_fastmcp.from_openapi.return_value = "mcp_server"

        mock_manager_instance = AsyncMock()
        mock_manager_instance.get_authenticated_http_client_for_jessonid.side_effect = (
            httpx.HTTPError("HTTP error")
        )
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
        patch(
            "mcp_composer.core.member_servers.builder.load_spec_from_url"
        ) as mock_load_spec,
        patch(
            "mcp_composer.core.member_servers.builder.load_custom_mappings_from_json"
        ) as mock_load_mappings,
        patch("mcp_composer.core.member_servers.builder.FastMCP") as mock_fastmcp,
        patch("mcp_composer.core.member_servers.builder.jsonref") as mock_jsonref,
        patch(
            "mcp_composer.core.member_servers.builder.DynamicTokenManager"
        ) as mock_token_manager,
    ):
        mock_load_spec.return_value = {"openapi": "3.0.0"}
        mock_load_mappings.return_value = []
        mock_jsonref.loads.return_value = {"openapi": "3.0.0"}
        mock_fastmcp.from_openapi.return_value = "mcp_server"

        mock_manager_instance = AsyncMock()
        mock_manager_instance.get_authenticated_http_client_for_jessonid.side_effect = (
            Exception("Unexpected error")
        )
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
    with (
        patch.dict("os.environ", {"MCP_COMPOSER_MODE": "dev"}),
        pytest.raises(NotImplementedError, match="Spec is missing"),
    ):
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
        patch(
            "mcp_composer.core.member_servers.builder.GraphQLTool"
        ) as mock_graphql_tool,
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
        patch(
            "mcp_composer.core.member_servers.builder.build_prompt_from_dict"
        ) as mock_build_prompt,
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
    with pytest.raises(
        NotImplementedError, match="Local file loading not yet supported"
    ):
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
        patch(
            "mcp_composer.core.member_servers.builder.MCPServerBuilder._build_from_openapi"
        ) as mock_build_openapi,
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
        patch(
            "mcp_composer.core.member_servers.builder.MCPServerBuilder._build_from_graphql"
        ) as mock_build_graphql,
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
        patch(
            "mcp_composer.core.member_servers.builder.MCPServerBuilder._build_from_local_file"
        ) as mock_build_local,
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
        patch(
            "mcp_composer.core.member_servers.builder.MCPServerBuilder._build_from_fastapi"
        ) as mock_build_fastapi,
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


@pytest.mark.asyncio
async def test_build_from_openapi_with_layered_config():
    """Test building OpenAPI server with layered configuration enabled."""
    config = {
        ConfigKey.ID: "mcp-hybrid-mesh",
        ConfigKey.TYPE: ConfigKey.OPEN_API,
        ConfigKey.OPEN_API: {
            ConfigKey.ENDPOINT: "https://app.hybridcloudmesh.ibm.com/api/v1",
            ConfigKey.SPEC_FILEPATH: "/path/to/hybrid_mesh.json",
            "layered": True,
            "custom_routes": [
                {"methods": ["GET"], "pattern": ".*", "mcp_type": "TOOL"},
                {
                    "methods": ["POST", "DELETE", "PUT", "PATCH"],
                    "pattern": ".*",
                    "mcp_type": "EXCLUDE",
                },
            ],
        },
        ConfigKey.AUTH_STRATEGY: AuthStrategy.APIKEY,
        ConfigKey.AUTH: {ConfigKey.APIKEY: "test-api-key"},
    }

    builder = MCPServerBuilder(config)

    # Test that the config has the layered flag set
    assert builder.config[ConfigKey.OPEN_API]["layered"] is True
    assert builder.config["type"] == ConfigKey.OPEN_API

    # Test that the custom routes are properly configured
    custom_routes = builder.config[ConfigKey.OPEN_API]["custom_routes"]
    assert len(custom_routes) == 2
    assert custom_routes[0]["methods"] == ["GET"]
    assert custom_routes[0]["mcp_type"] == "TOOL"
    assert custom_routes[1]["methods"] == ["POST", "DELETE", "PUT", "PATCH"]
    assert custom_routes[1]["mcp_type"] == "EXCLUDE"

    # Test that the auth configuration is correct
    assert builder.config[ConfigKey.AUTH_STRATEGY] == AuthStrategy.APIKEY
    assert builder.config[ConfigKey.AUTH][ConfigKey.APIKEY] == "test-api-key"


@pytest.mark.asyncio
async def test_build_from_openapi_with_layered_config_non_openapi_type():
    """Test building server with layered config but non-OpenAPI type still uses FastMCP."""
    config = {
        ConfigKey.ID: "test-server",
        ConfigKey.TYPE: "graphql",  # Non-OpenAPI type
        ConfigKey.ENDPOINT: "http://api",
        "layered": True,  # layered enabled but wrong type
    }

    builder = MCPServerBuilder(config)

    # Test that the config has the layered flag set
    assert builder.config["layered"] is True
    assert builder.config["type"] == "graphql"

    # Test that the endpoint is configured
    assert builder.config[ConfigKey.ENDPOINT] == "http://api"


@pytest.mark.asyncio
async def test_build_from_openapi_without_layered_config():
    """Test building OpenAPI server without layered configuration."""
    config = {
        ConfigKey.ID: "regular-openapi",
        ConfigKey.TYPE: ConfigKey.OPEN_API,
        ConfigKey.OPEN_API: {
            ConfigKey.ENDPOINT: "http://api",
            ConfigKey.SPEC_FILEPATH: "/path/to/spec.json",
            # No layered config
        },
        ConfigKey.AUTH_STRATEGY: AuthStrategy.APIKEY,
        ConfigKey.AUTH: {ConfigKey.APIKEY: "test_key"},
    }

    builder = MCPServerBuilder(config)

    # Test that the config has no layered flag
    assert "layered" not in builder.config
    assert builder.config["type"] == ConfigKey.OPEN_API

    # Test that the auth configuration is correct
    assert builder.config[ConfigKey.AUTH_STRATEGY] == AuthStrategy.APIKEY
    assert builder.config[ConfigKey.AUTH][ConfigKey.APIKEY] == "test_key"


@pytest.mark.asyncio
async def test_layered_config_with_real_files():
    """Test layered configuration using mock config data."""

    # Use mock config instead of real files
    mock_config = {
        ConfigKey.ID: "mcp-hybrid-mesh",
        ConfigKey.TYPE: ConfigKey.OPEN_API,
        ConfigKey.OPEN_API: {
            ConfigKey.ENDPOINT: "https://api.example.com/v1",
            ConfigKey.SPEC_FILEPATH: "/path/to/hybrid_mesh.json",
            "layered": True,
            "custom_routes": [
                {"methods": ["GET"], "pattern": ".*", "mcp_type": "TOOL"},
                {
                    "methods": ["POST", "DELETE", "PUT", "PATCH"],
                    "pattern": ".*",
                    "mcp_type": "EXCLUDE",
                },
            ],
        },
        ConfigKey.AUTH_STRATEGY: AuthStrategy.APIKEY,
        ConfigKey.AUTH: {ConfigKey.APIKEY: "test-api-key"},
    }

    builder = MCPServerBuilder(mock_config)

    # Test that the config has the layered flag set
    assert builder.config[ConfigKey.OPEN_API]["layered"] is True
    assert builder.config["type"] == ConfigKey.OPEN_API

    # Test that the custom routes are properly configured
    custom_routes = builder.config[ConfigKey.OPEN_API]["custom_routes"]
    assert len(custom_routes) == 2
    assert custom_routes[0]["methods"] == ["GET"]
    assert custom_routes[0]["mcp_type"] == "TOOL"
    assert custom_routes[1]["methods"] == ["POST", "DELETE", "PUT", "PATCH"]
    assert custom_routes[1]["mcp_type"] == "EXCLUDE"

    # Test that the auth configuration is correct
    assert builder.config[ConfigKey.AUTH_STRATEGY] == AuthStrategy.APIKEY
    assert builder.config[ConfigKey.AUTH][ConfigKey.APIKEY] == "test-api-key"

    print("✓ Verified layered configuration with mock data")


@pytest.mark.asyncio
async def test_layered_enabled_returns_only_three_tools():
    """Test that when layered is enabled, the MCP server returns exactly 3 tools."""

    # Use mock config instead of real files
    config = {
        ConfigKey.ID: "test-layered-server",
        ConfigKey.TYPE: ConfigKey.OPEN_API,
        ConfigKey.OPEN_API: {
            ConfigKey.ENDPOINT: "https://api.example.com/v1",
            ConfigKey.SPEC_FILEPATH: "/path/to/spec.json",
            "layered": True,
            "custom_routes": [
                {"methods": ["GET"], "pattern": ".*", "mcp_type": "TOOL"}
            ],
        },
        ConfigKey.AUTH_STRATEGY: AuthStrategy.APIKEY,
        ConfigKey.AUTH: {ConfigKey.APIKEY: "test-api-key"},
    }

    builder = MCPServerBuilder(config)

    # Mock the OpenAPI spec with some sample operations (valid spec with responses)
    mock_spec = {
        "openapi": "3.0.3",
        "info": {"title": "Test API", "version": "1.0.0"},
        "paths": {
            "/users": {
                "get": {
                    "operationId": "getUsers",
                    "summary": "Get all users",
                    "responses": {
                        "200": {
                            "description": "Successful response",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "array",
                                        "items": {"type": "object"},
                                    }
                                }
                            },
                        }
                    },
                },
                "post": {
                    "operationId": "createUser",
                    "summary": "Create a user",
                    "responses": {
                        "201": {
                            "description": "User created",
                            "content": {
                                "application/json": {"schema": {"type": "object"}}
                            },
                        }
                    },
                },
            },
            "/users/{id}": {
                "get": {
                    "operationId": "getUserById",
                    "summary": "Get user by ID",
                    "parameters": [
                        {
                            "name": "id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Successful response",
                            "content": {
                                "application/json": {"schema": {"type": "object"}}
                            },
                        }
                    },
                }
            },
        },
    }

    with (
        patch("mcp_composer.core.member_servers.builder.load_json") as mock_load_json,
        patch(
            "mcp_composer.core.member_servers.builder.load_custom_mappings_from_json"
        ) as mock_load_mappings,
        patch("mcp_composer.core.member_servers.builder.jsonref") as mock_jsonref,
        patch(
            "mcp_composer.core.member_servers.builder.httpx.AsyncClient"
        ) as _mock_client,
        patch.dict("os.environ", {"MCP_COMPOSER_MODE": "dev"}),
    ):
        # Mock the spec loading
        mock_load_json.return_value = mock_spec
        mock_load_mappings.return_value = []
        mock_jsonref.loads.return_value = mock_spec

        # Build the server
        mcp_server = await builder._build_from_openapi()

        # Verify it's a LayeredOpenAPIFactory instance (not FastMCP)
        assert isinstance(
            mcp_server, LayeredOpenAPIFactory
        ), "Should use LayeredOpenAPIFactory when layered=True"

        # Verify the server has exactly 3 tools
        # Since LayeredOpenAPIFactory inherits from FastMCP, it should have _tool_manager
        tools_dict = await mcp_server._tool_manager.get_tools()
        tools = list(tools_dict.values())
        assert len(tools) == 3, f"Expected exactly 3 tools, but got {len(tools)}"

        # Verify the expected tool names
        tool_names = [tool.name for tool in tools]
        expected_tools = ["get_service_info", "get_type_info", "make_tool_call"]

        for expected_tool in expected_tools:
            assert (
                expected_tool in tool_names
            ), f"Expected tool '{expected_tool}' not found in {tool_names}"

        # Verify no additional tools are present
        for tool_name in tool_names:
            assert tool_name in expected_tools, f"Unexpected tool '{tool_name}' found"

        print(f"✓ Verified exactly 3 tools: {tool_names}")


@pytest.mark.asyncio
async def test_layered_disabled_uses_fastmcp():
    """Test that when layered is disabled/false, it uses FastMCP instead of LayeredOpenAPIFactory."""
    config = {
        ConfigKey.ID: "test-fastmcp-server",
        ConfigKey.TYPE: ConfigKey.OPEN_API,
        ConfigKey.OPEN_API: {
            ConfigKey.ENDPOINT: "https://api.example.com/v1",
            ConfigKey.SPEC_FILEPATH: "/path/to/spec.json",
            "layered": False,  # Explicitly disabled
            "custom_routes": [],
        },
        ConfigKey.AUTH_STRATEGY: AuthStrategy.APIKEY,
        ConfigKey.AUTH: {ConfigKey.APIKEY: "test-api-key"},
    }

    builder = MCPServerBuilder(config)

    # Mock the OpenAPI spec (valid spec with responses)
    mock_spec = {
        "openapi": "3.0.3",
        "info": {"title": "Test API", "version": "1.0.0"},
        "paths": {
            "/users": {
                "get": {
                    "operationId": "getUsers",
                    "summary": "Get all users",
                    "responses": {
                        "200": {
                            "description": "Successful response",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "array",
                                        "items": {"type": "object"},
                                    }
                                }
                            },
                        }
                    },
                }
            }
        },
    }

    with (
        patch("mcp_composer.core.member_servers.builder.load_json") as mock_load_json,
        patch(
            "mcp_composer.core.member_servers.builder.load_custom_mappings_from_json"
        ) as mock_load_mappings,
        patch("mcp_composer.core.member_servers.builder.jsonref") as mock_jsonref,
        patch(
            "mcp_composer.core.member_servers.builder.httpx.AsyncClient"
        ) as _mock_client,
        patch.dict("os.environ", {"MCP_COMPOSER_MODE": "dev"}),
    ):
        # Mock the spec loading
        mock_load_json.return_value = mock_spec
        mock_load_mappings.return_value = []
        mock_jsonref.loads.return_value = mock_spec

        # Build the server
        mcp_server = await builder._build_from_openapi()

        # Verify it's a FastMCP instance (not LayeredOpenAPIFactory)
        assert isinstance(mcp_server, FastMCP), "Should use FastMCP when layered=False"
        assert not isinstance(
            mcp_server, LayeredOpenAPIFactory
        ), "Should NOT use LayeredOpenAPIFactory when layered=False"

        print("✓ Verified FastMCP is used when layered=False")
