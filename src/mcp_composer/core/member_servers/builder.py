"""loaders/builder.py"""

# pylint: disable=W0611
# pylint: disable=C0411
import json
from typing import Dict
import jsonref
import httpx
import mcp_composer.core.utils.patch_openapi_tool
from fastmcp import FastMCP, Client
from fastmcp.client.auth import OAuth
from fastmcp.client.transports import (
    StreamableHttpTransport,
    SSETransport,
    StdioTransport,
)
from fastmcp.client.auth.oauth import FileTokenStorage

from mcp_composer.core.utils.logger import LoggerFactory
from mcp_composer.core.utils import ConfigKey, MemberServerType, AuthStrategy
from mcp_composer.core.utils import (
    load_custom_mappings_from_json,
    load_json,
    build_prompt_from_dict,
    load_spec_from_url,
)
from mcp_composer.core.auth_handler import DynamicTokenClient, DynamicTokenManager
from mcp_composer.core.tools.graphql_tool import GraphQLTool

logger = LoggerFactory.get_logger()


class MCPServerBuilder:
    """
    Builds a FastMCP server from a config block.
    Supported types: openapi, client, fastapi, http/sse, local
    """

    def __init__(self, config: Dict):
        logger.info("Building Member Server with config: %s", config)
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
        headers = config.get(ConfigKey.HEADERS)
        oauth = config.get(ConfigKey.AUTH)
        transport = None
        if transport_type in {
            MemberServerType.HTTP,
            MemberServerType.SSE,
        }:  # pylint: disable=R1705
            endpoint = config[ConfigKey.ENDPOINT]
            auth = None
            if oauth:
                FileTokenStorage.clear_all()
                auth = OAuth(mcp_url=endpoint)
            transport = TransportClass(url=endpoint, headers=headers, auth=auth)
            # Set up authentication if provided
            client = Client(transport, auth=auth)
            return FastMCP.as_proxy(client, name=self.mcp_id)

        elif transport_type == MemberServerType.STDIO:
            # For stdio, we need to pass the command and args
            command = config.get(ConfigKey.COMMAND, "mcp-composer")
            args = config.get(ConfigKey.ARGS, [])
            env = config.get(ConfigKey.ENV, None)
            cwd = config.get(ConfigKey.CWD, None)
            transport = StdioTransport(command=command, args=args, env=env, cwd=cwd)
            # Set up authentication if provided
            client = Client(transport)
            return FastMCP.as_proxy(client, name=self.mcp_id)
        else:
            raise ValueError(f"Unsupported transport type: {transport_type}")

    async def _build_from_client(self) -> FastMCP:
        # auth = build_auth_strategy(self.config["auth_strategy"], self.config.get("auth", {}))
        # headers = await auth.get_headers()

        client = Client(self.config[ConfigKey.ENDPOINT])

        headers = self.config.get(ConfigKey.HEADERS)
        if headers:
            transport = StreamableHttpTransport(
                url=self.config[ConfigKey.ENDPOINT], headers=headers
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
        if ConfigKey.CUSTOM_ROUTES in openapi_config:
            custom_mappings = await load_custom_mappings_from_json(
                openapi_config[ConfigKey.CUSTOM_ROUTES]
            )
        spec = {}
        if ConfigKey.SPEC_URL in openapi_config:
            spec = await load_spec_from_url(
                openapi_config[ConfigKey.ENDPOINT], openapi_config[ConfigKey.SPEC_URL]
            )
        elif ConfigKey.SPEC_FILEPATH in openapi_config:
            spec = await load_json(openapi_config[ConfigKey.SPEC_FILEPATH])
        else:
            raise NotImplementedError("Spec is missing")

        headers = self.config.get(ConfigKey.HEADERS, {})
        logger.info("the headers are '%s'", headers)
        auth_strategy = self.config[ConfigKey.AUTH_STRATEGY]
        auth_config = self.config.get(ConfigKey.AUTH, {})
        base_url = openapi_config[ConfigKey.ENDPOINT]
        http_client = httpx.AsyncClient(base_url=base_url)

        match auth_strategy:
            case AuthStrategy.BASIC:
                logger.info("Setting up client for basic auth")
                username = auth_config.get(ConfigKey.USERNAME)
                password = auth_config.get(ConfigKey.PASSWORD)
                http_client = httpx.AsyncClient(
                    base_url=base_url,
                    auth=httpx.BasicAuth(username, password),
                    headers=headers,
                )

            case AuthStrategy.DYNAMIC_BEARER:
                http_client = DynamicTokenClient(
                    base_url=base_url,
                    token_url=auth_config.get(ConfigKey.Token_URL),
                    api_key=auth_config.get(ConfigKey.APIKEY),
                    media_type=auth_config.get(ConfigKey.MEDIA_TYPE, ""),
                )
            case AuthStrategy.BEARER:
                logger.info("Setting up header and client for bearer")
                headers[ConfigKey.AUTH_HEADER.value] = (
                    f"Bearer {auth_config.get(ConfigKey.TOKEN)}"
                )
                http_client = httpx.AsyncClient(base_url=base_url, headers=headers)

            case AuthStrategy.APITOKEN:
                logger.info("Setting up header and client for apiToken")
                headers[ConfigKey.AUTH_HEADER.value] = (
                    f"{auth_config.get(ConfigKey.AUTH_PREFIX)} {auth_config.get(ConfigKey.TOKEN)}"
                )
                logger.info(
                    "the headers are updated '%s' and the url is '%s'",
                    headers,
                    base_url,
                )
                http_client = httpx.AsyncClient(base_url=base_url, headers=headers)

            case AuthStrategy.APIKEY:
                logger.info("Setting up header and client for apikey")
                auth_header = " ".join(filter(None, [
                    auth_config.get(ConfigKey.AUTH_PREFIX),
                    auth_config.get(ConfigKey.APIKEY)
                ]))
                headers[ConfigKey.AUTH_HEADER.value] = (
                    f"{auth_header}"
                )
                logger.info(
                    "the url is '%s'",
                    base_url,
                )
                http_client = httpx.AsyncClient(base_url=base_url, headers=headers)

            case AuthStrategy.JSESSIONID.value:
                logger.info("Setting up header and client for jessionid")
                try:
                    token_manager = DynamicTokenManager(
                        base_url=base_url,
                        auth_strategy=self.config[ConfigKey.AUTH_STRATEGY],
                        login_url=auth_config.get(ConfigKey.LOGIN_URL),
                        username=auth_config.get(ConfigKey.USERNAME),
                        password=auth_config.get(ConfigKey.PASSWORD),
                    )

                    http_client = (
                        await token_manager.get_authenticated_http_client_for_jessonid()
                    )
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
                http_client = httpx.AsyncClient(base_url=base_url)

        # QUICK FIX TO SCHEMA UNRAVELING ISSUE BELOW
        spec = jsonref.loads(json.dumps(spec), load_on_repr=True)
        mcp = FastMCP.from_openapi(spec, client=http_client, route_maps=custom_mappings)  # type: ignore
        return mcp

    async def _build_from_graphql(self) -> FastMCP:
        logger.info("Setting up Graphql MCP Server %s", self.config)
        tool = GraphQLTool(self.config)
        mcp = FastMCP(self.config.get(ConfigKey.ID, ""))
        mcp.add_tool(tool)
        return mcp

    async def _build_from_local_file(self) -> FastMCP:
        mcp = FastMCP(self.config.get(ConfigKey.ID, ""))
        data = await load_json(self.config[ConfigKey.PROMPT_PATH])
        for entry in data:
            prompt = build_prompt_from_dict(entry)
            logger.info("Prompt: %s", prompt)
            mcp.add_prompt(prompt)
        return mcp

    def _build_from_fastapi(self) -> FastMCP:
        raise NotImplementedError("Local file loading not yet supported.")
