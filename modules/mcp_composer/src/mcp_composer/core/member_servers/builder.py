"""loaders/builder.py"""

# pylint: disable=W0611
# pylint: disable=C0411
import json
import os
from typing import Any
import jsonref  # type: ignore[import-untyped]
import httpx
from fastmcp import FastMCP, Client
from fastmcp.client.auth import OAuth
from fastmcp.server import create_proxy
from fastmcp.client.transports import (
    StreamableHttpTransport,
    SSETransport,
    StdioTransport,
)
from mcp_composer.core.utils.logger import LoggerFactory
from mcp_composer.core.utils import ConfigKey, MemberServerType, AuthStrategy
from mcp_composer.core.utils import (
    load_custom_mappings_from_json,
    load_json,
    build_prompt_from_dict,
    load_spec_from_url,
)
from mcp_composer.core.auth_handler import (
    DynamicBearerAuth,
    DynamicTokenClient,
    DynamicTokenManager,
    OAuthRefreshClient,
    resolve_env_value,
)
from mcp_composer.core.tools.graphql_tool import GraphQLTool
from mcp_composer.core.member_servers.layered_factory_oa import LayeredOpenAPIFactory
from mcp_composer.core.member_servers.layered_factory_mcp import LayeredMCPFactory
from mcp_composer.core.member_servers.layered_constants import DEFAULT_EXCLUDE_CONFIG

logger = LoggerFactory.get_logger()


class MCPServerBuilder:
    """
    Builds a FastMCP server from a config block.
    Supported types: openapi, client, fastapi, http/sse, local
    """

    def __init__(self, config: dict[str, object]):
        logger.debug("Building Member Server with config: %s", config)
        self.config = config
        self.mcp_id = config["id"]
        self.mcp_type = config["type"]

    async def build(self) -> FastMCP:
        """Build the server based on the mcp server type"""
        logger.info("Building new '%s' Server", self.mcp_type)

        if self.mcp_type == MemberServerType.CLIENT:  # pylint: disable=R1705
            return await self._build_from_client()

        elif self.mcp_type in {
            MemberServerType.HTTP,
            MemberServerType.SSE,
            MemberServerType.STDIO,
        }:
            # For HTTP/SSE/STDIO, we need to build the transport first
            logger.info("Building MCP server with transport type: %s", self.mcp_type)
            return await self._build_from_transport(transport_type=self.mcp_type)

        elif self.mcp_type == MemberServerType.OPENAPI:
            return await self._build_from_openapi()

        elif self.mcp_type == MemberServerType.GRAPHQL:
            return await self._build_from_graphql()

        elif self.mcp_type == "fastapi":
            return self._build_from_fastapi()

        elif self.mcp_type == MemberServerType.LOCAL:
            return await self._build_from_local_file()

        else:
            raise ValueError(f"Unsupported MCP type: {self.mcp_type}")

    async def _build_from_transport(self, transport_type=None) -> FastMCP:
        logger.info("Building MCP server with transport type: %s", transport_type)
        # Map transport types to their corresponding classes
        transport_classes = {
            "http": StreamableHttpTransport,
            "sse": SSETransport,
            "stdio": StdioTransport,
        }

        # Choose and instantiate the appropriate transport
        TransportClass = transport_classes.get(transport_type)  # type: ignore
        if not TransportClass:
            raise ValueError(f"Unsupported MCP type: {transport_type}")

        config = self.config
        headers = config.get(ConfigKey.HEADERS, {})
        auth_token = config.get(ConfigKey.AUTH, {})
        auth_strategy = config.get(ConfigKey.AUTH_STRATEGY)
        transport = None
        if transport_type in {
            MemberServerType.HTTP,
            MemberServerType.SSE,
        }:  # pylint: disable=R1705
            endpoint = config[ConfigKey.ENDPOINT]
            auth = None

            # Check if layered mode is enabled for native MCP protocol
            layered_enabled = config.get(ConfigKey.LAYERED, False)
            if layered_enabled:
                logger.info("Building layered MCP protocol server from HTTP transport")
                return await self._build_layered_mcp_from_transport(
                    endpoint, headers, auth_strategy, auth_token  # type: ignore[arg-type]
                )

            # Set up authentication for the transport
            headers, auth = await self._setup_auth_for_transport(
                endpoint, headers, auth_strategy, auth_token  # type: ignore[arg-type]
            )

            transport = TransportClass(url=endpoint, headers=headers, auth=auth)
            from mcp_composer.core.utils.log_redaction import redact_headers

            logger.debug("transport headers keys/values: %s", redact_headers(headers))
            # Set up authentication if provided
            client = Client(transport, auth=auth)
            return create_proxy(client, name=f"proxy_{self.mcp_id}")

        if transport_type == MemberServerType.STDIO:
            from mcp_composer.core.utils.stdio_allowlist import (
                assert_stdio_command_allowed,
            )

            # For stdio, command must be an allowlisted absolute path
            command = assert_stdio_command_allowed(
                str(config.get(ConfigKey.COMMAND) or "")
            )
            args = config.get(ConfigKey.ARGS, [])
            env = config.get(ConfigKey.ENV, None)
            cwd = config.get(ConfigKey.CWD, None)
            transport = StdioTransport(command=command, args=args, env=env, cwd=cwd)  # type: ignore[arg-type]
            # Set up authentication if provided
            client = Client(transport)
            return create_proxy(client)

        raise ValueError(f"Unsupported transport type: {transport_type}")

    async def _setup_auth_for_transport(
        self,
        endpoint: str,
        headers: dict[str, str],
        auth_strategy: str | None,
        auth_config: dict[str, object],
    ) -> tuple[dict[str, str], Any]:
        """
        Set up authentication for HTTP/SSE transport.
        Returns tuple of (updated_headers, auth_object).
        """
        auth = None

        if auth_strategy == AuthStrategy.OAUTH:
            auth = OAuth(mcp_url=endpoint)

        elif auth_strategy == AuthStrategy.BEARER:
            logger.info("Setting up header for bearer")
            headers[ConfigKey.AUTH_HEADER.value] = (
                f"Bearer {auth_config.get(ConfigKey.TOKEN)}"
            )

        elif auth_strategy == AuthStrategy.DYNAMIC_BEARER:
            logger.info("Setting up dynamic bearer token client")
            dynamic_client = DynamicTokenClient(
                base_url=endpoint,
                auth_data=auth_config,
            )
            await dynamic_client.ensure_token()
            auth = DynamicBearerAuth(dynamic_client)  # type: ignore[assignment]

        return headers, auth

    async def _build_layered_mcp_from_transport(
        self,
        endpoint: str,
        headers: dict[str, str],
        auth_strategy: str | None,
        auth_config: dict[str, object],
    ) -> FastMCP:
        """
        Build a layered MCP protocol server from HTTP transport configuration.
        This provides a discovery layer on top of native MCP servers without OpenAPI specs.
        """
        logger.info(
            "Building layered MCP protocol server from HTTP transport with endpoint: %s",
            endpoint,
        )

        # Set up authentication for the transport
        headers, auth = await self._setup_auth_for_transport(
            endpoint, headers, auth_strategy, auth_config
        )

        # Create the transport and client
        transport = StreamableHttpTransport(url=endpoint, headers=headers, auth=auth)
        client = Client(transport, auth=auth)

        # Get optional tool descriptions
        tool_descriptions = self.config.get("tool_description", {}) or {}  # type: ignore[attr-defined]

        product_id = self.config.get("productId", None)  # type: ignore[attr-defined]

        # Create LayeredMCPFactory instance (which extends FastMCP)
        mcp = LayeredMCPFactory(
            client=client,
            server_id=self.mcp_id,  # type: ignore[arg-type]  # Pass server_id for authorization
            product_id=product_id,  # type: ignore[arg-type]  # Pass productId for authorization matching
            tool_descriptions=tool_descriptions,  # type: ignore[arg-type]
        )

        logger.info(
            "Successfully built layered MCP protocol server from HTTP transport"
        )
        return mcp

    async def _build_from_client(self) -> FastMCP:
        client = Client(self.config[ConfigKey.ENDPOINT])  # type: ignore[call-overload]

        headers = self.config.get(ConfigKey.HEADERS)
        if headers:
            transport = StreamableHttpTransport(
                url=self.config[ConfigKey.ENDPOINT], headers=headers  # type: ignore[arg-type]
            )
            client = Client(transport)
        try:
            return FastMCP.as_proxy(client, name=self.mcp_id)
        except Exception as e:
            logger.exception(
                "Failed to build member MCP server '%s': %s", self.config.get("id"), e
            )
            raise RuntimeError(
                f"Failed to build member MCP server '{self.mcp_id}'"
            ) from e

    async def _build_from_openapi(self) -> FastMCP:
        openapi_config = self.config[ConfigKey.OPEN_API]
        custom_mappings = []
        if ConfigKey.CUSTOM_ROUTES in openapi_config:  # type: ignore[operator]
            custom_mappings = await load_custom_mappings_from_json(
                openapi_config[ConfigKey.CUSTOM_ROUTES]  # type: ignore[index]
            )
        spec = {}

        # Enforce dev/prod rules here as well so build paths that skip validation still honor mode
        mode = os.getenv("MCP_COMPOSER_MODE", "prod").strip().lower()
        if mode not in {"dev", "prod"}:
            logger.warning(
                "Unknown MCP_COMPOSER_MODE '%s'; defaulting to 'prod' rules.", mode
            )
            mode = "prod"

        if mode == "prod":
            # Production: require spec_url only
            if openapi_config.get(ConfigKey.SPEC_FILEPATH):  # type: ignore[attr-defined]
                raise ValueError(
                    "In production mode, 'spec_filepath' is not allowed; use 'spec_url'."
                )
            if not openapi_config.get(ConfigKey.SPEC_URL):  # type: ignore[attr-defined]
                raise ValueError(
                    "In production mode, 'spec_url' is required in 'open_api'."
                )
            spec = await load_spec_from_url(
                openapi_config[ConfigKey.ENDPOINT], openapi_config[ConfigKey.SPEC_URL]  # type: ignore[index]
            )
        else:
            # Dev: prefer spec_url if present, else spec_filepath
            if openapi_config.get(ConfigKey.SPEC_URL):  # type: ignore[attr-defined]
                spec = await load_spec_from_url(
                    openapi_config[ConfigKey.ENDPOINT],  # type: ignore[index]
                    openapi_config[ConfigKey.SPEC_URL],  # type: ignore[index]
                )
            elif openapi_config.get(ConfigKey.SPEC_FILEPATH):  # type: ignore[attr-defined]
                spec = await load_json(openapi_config[ConfigKey.SPEC_FILEPATH])  # type: ignore[index]
            else:
                raise NotImplementedError(
                    "Spec is missing (provide spec_url or spec_filepath)"
                )

        headers = self.config.get(ConfigKey.HEADERS, {})
        logger.info("the headers are '%s'", headers)
        auth_strategy = self.config.get(ConfigKey.AUTH_STRATEGY, "")
        auth_config = self.config.get(ConfigKey.AUTH, {})
        base_url = openapi_config[ConfigKey.ENDPOINT]  # type: ignore[index]
        http_client = httpx.AsyncClient(base_url=base_url)

        match auth_strategy:
            case AuthStrategy.BASIC:
                logger.info("Setting up client for basic auth")
                username = resolve_env_value(auth_config.get(ConfigKey.USERNAME))  # type: ignore[attr-defined]
                password = resolve_env_value(auth_config.get(ConfigKey.PASSWORD))  # type: ignore[attr-defined]
                http_client = httpx.AsyncClient(
                    base_url=base_url,
                    auth=httpx.BasicAuth(username, password),
                    headers=headers,  # type: ignore[arg-type]
                )

            case AuthStrategy.DYNAMIC_BEARER:
                logger.info("Setting up dynamic bearer token client")
                http_client = DynamicTokenClient(
                    base_url=base_url,
                    auth_data=auth_config,  # type: ignore[arg-type]
                    headers=headers,  # type: ignore[arg-type]
                )
                await http_client._refresh_token()
                # TODO: remove this code as its for the bug of not refreshing the token when the token is expired

                # dynamic_token_client_oauth = DynamicTokenClientOAuth(
                #    access_token=http_client._access_token,
                #    auth_prefix=http_client._auth_prefix,
                # )
                # http_client.auth = dynamic_token_client_oauth

            case AuthStrategy.OAUTH:
                logger.info("Setting up OAuth client with auto-refresh")
                # Use the generic resolve_env_value function to handle ENV_* values
                client_id = resolve_env_value(auth_config.get(ConfigKey.OAUTH_CLIENT))  # type: ignore[attr-defined]
                client_secret = resolve_env_value(
                    auth_config.get(ConfigKey.OAUTH_PROOF)  # type: ignore[attr-defined]
                )
                token_url = auth_config.get(ConfigKey.Token_URL)  # type: ignore[attr-defined]
                scope = auth_config.get(ConfigKey.SCOPE)  # type: ignore[attr-defined]
                refresh_token_value = resolve_env_value(
                    auth_config.get(ConfigKey.OAUTH_REFRESH)  # type: ignore[attr-defined]
                )

                if not all([client_id, client_secret, token_url, refresh_token_value]):
                    raise RuntimeError(
                        "Missing required OAuth configuration: client_id, client_secret, token_url, refresh_token"
                    )

                http_client = OAuthRefreshClient(
                    base_url=base_url,
                    token_url=token_url,
                    client_id=client_id,
                    client_secret=client_secret,
                    refresh_token=refresh_token_value,
                    scope=scope,
                )

            case AuthStrategy.BEARER:
                logger.info("Setting up header and client for bearer")
                headers[ConfigKey.AUTH_HEADER.value] = (  # type: ignore[index]
                    f"Bearer {auth_config.get(ConfigKey.TOKEN)}"  # type: ignore[attr-defined]
                )
                http_client = httpx.AsyncClient(base_url=base_url, headers=headers)  # type: ignore[arg-type]

            case AuthStrategy.APITOKEN:
                logger.info("Setting up header and client for apiToken")
                headers[ConfigKey.AUTH_HEADER.value] = (  # type: ignore[index]
                    f"{auth_config.get(ConfigKey.AUTH_PREFIX)} {resolve_env_value(auth_config.get(ConfigKey.TOKEN))}"  # type: ignore[attr-defined]
                )
                logger.info(
                    "the headers are updated '%s' and the url is '%s'",
                    headers,
                    base_url,
                )
                http_client = httpx.AsyncClient(base_url=base_url, headers=headers)  # type: ignore[arg-type]

            case AuthStrategy.APIKEY:
                logger.info("Setting up header and client for apikey")
                auth_header = " ".join(
                    filter(
                        None,
                        [
                            auth_config.get(ConfigKey.AUTH_PREFIX),  # type: ignore[attr-defined]
                            resolve_env_value(auth_config.get(ConfigKey.APIKEY)),  # type: ignore[attr-defined]
                        ],
                    )
                )
                headers[ConfigKey.AUTH_HEADER.value] = f"{auth_header}"  # type: ignore[index]
                logger.info("the url is %s", base_url)
                http_client = httpx.AsyncClient(base_url=base_url, headers=headers)  # type: ignore[arg-type]

            case AuthStrategy.JSESSIONID.value:
                logger.info("Setting up header and client for jessionid")
                try:
                    token_manager = DynamicTokenManager(
                        base_url=base_url,
                        auth_strategy=self.config[ConfigKey.AUTH_STRATEGY],
                        login_url=auth_config.get(ConfigKey.LOGIN_URL),  # type: ignore[attr-defined]
                        username=auth_config.get(ConfigKey.USERNAME),  # type: ignore[attr-defined]
                        password=resolve_env_value(auth_config.get(ConfigKey.PASSWORD)),  # type: ignore[attr-defined]
                    )

                    http_client = await token_manager.get_authenticated_http_client_for_jessonid()  # type: ignore[assignment]
                except KeyError as e:
                    # Required config missing
                    logger.error("Missing configuration key: %s", e)

                except httpx.HTTPError as e:
                    # Any HTTP-related error from httpx
                    logger.error("HTTP error during authentication: %s", e)

                except Exception as e:
                    # Catch-all for unexpected errors
                    logger.error("Unexpected error: %s", e)

            case _:
                # Default/fallback client
                if headers:
                    logger.info("Setting up default client with headers")
                    http_client = httpx.AsyncClient(base_url=base_url, headers=headers)  # type: ignore[arg-type]
                else:
                    logger.info("Setting up default client without headers")
                    http_client = httpx.AsyncClient(base_url=base_url)

        # QUICK FIX TO SCHEMA UNRAVELING ISSUE BELOW
        spec = jsonref.loads(json.dumps(spec), load_on_repr=True)

        # Check if layered is enabled in the OPEN_API configuration
        if openapi_config.get(ConfigKey.LAYERED, False):  # type: ignore[attr-defined]
            exclude_all_route = await load_custom_mappings_from_json(
                DEFAULT_EXCLUDE_CONFIG
            )
            # Ensure spec is a dict and http_client is not None
            if not isinstance(spec, dict):
                raise ValueError("OpenAPI spec must be a dictionary")
            if http_client is None:
                raise ValueError("HTTP client cannot be None")

            # Optional per-tool descriptions for layered tools
            tool_descriptions = openapi_config.get("tool_description", {}) or {}  # type: ignore[attr-defined]

            product_id = self.config.get("productId", None)  # type: ignore[attr-defined]

            mcp = LayeredOpenAPIFactory(
                openapi_spec=spec,
                client=http_client,
                server_id=self.mcp_id,  # type: ignore[arg-type]  # Pass server_id for authorization
                product_id=product_id,  # type: ignore[arg-type]  # Pass productId for authorization matching
                custom_routes=custom_mappings,
                custom_routes_exclude_all=exclude_all_route,
                tool_descriptions=tool_descriptions,
            )
        else:
            # Default behavior when layered is not enabled
            mcp = FastMCP.from_openapi(spec, client=http_client, route_maps=custom_mappings)  # type: ignore
        return mcp

    async def _build_from_graphql(self) -> FastMCP:
        logger.info("Setting up Graphql MCP Server %s", self.config)
        tool = GraphQLTool(self.config)
        mcp = FastMCP(self.config.get(ConfigKey.ID, ""))  # type: ignore[arg-type]
        mcp.add_tool(tool)
        return mcp

    async def _build_from_local_file(self) -> FastMCP:
        mcp = FastMCP(self.config.get(ConfigKey.ID, ""))  # type: ignore[arg-type]
        data = await load_json(self.config[ConfigKey.PROMPT_PATH])
        for entry in data:
            prompt = build_prompt_from_dict(entry)
            logger.info("Prompt: %s", prompt)
            mcp.add_prompt(prompt)
        return mcp

    def _build_from_fastapi(self) -> FastMCP:
        raise NotImplementedError("Local file loading not yet supported.")
