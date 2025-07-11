# loaders/builder.py
import jsonref
import json

from typing import Dict
from fastmcp import FastMCP, Client
from fastmcp.client.auth import OAuth
from fastmcp.client.transports import StreamableHttpTransport, SSETransport
from fastmcp.client.auth.oauth import FileTokenStorage

import httpx
from mcp_composer.utils.logger import LoggerFactory
from mcp_composer.utils import ConfigKey, MemberServerType, AuthStrategy
from mcp_composer.utils import (
    load_custom_mappings_from_json, load_json, 
    build_prompt_from_dict,load_spec_from_url)
from mcp_composer.auth_handler import DynamicTokenClient, DynamicTokenManager
from mcp_composer.tools.graphql_tool import GraphQLTool

logger = LoggerFactory.get_logger()


class MCPServerBuilder:
    """
    Builds a FastMCP server from a config block.
    Supported types: openapi, client, fastapi, http/sse, local
    """

    def __init__(self, config: Dict):
        logger.info(f"Building Member Server with config {config}")
        self.config = config
        self.mcp_id = config["id"]
        self.mcp_type = config["type"]

    async def build(self) -> FastMCP:
        logger.info(f"Building new {self.mcp_type} Server")

        if self.mcp_type == MemberServerType.CLIENT:
            return await self._build_from_client()

        elif self.mcp_type in {"http", "sse"}:
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
        # auth = build_auth_strategy(self.config["auth_strategy"], self.config.get("auth", {}))
        # headers = await auth.get_headers()

        config = self.config
        endpoint = config[ConfigKey.ENDPOINT]
        headers = config.get(ConfigKey.HEADERS)
        oauth = config.get(ConfigKey.AUTH)

        # Set up authentication if provided
        auth = None
        if oauth:
            FileTokenStorage.clear_all()
            auth = OAuth(mcp_url=endpoint)

        # Map transport types to their corresponding classes
        transport_classes = {
            "http": StreamableHttpTransport,
            "sse": SSETransport,
        }

        # Choose and instantiate the appropriate transport
        TransportClass = transport_classes.get(transport_type) # type: ignore
        if not TransportClass:
            raise ValueError(f"Unsupported MCP type: {transport_type}")

        transport = TransportClass(url=endpoint, headers=headers, auth=auth)

        # Create the client and wrap it with FastMCP
        client = Client(transport, auth=auth)
        return FastMCP.as_proxy(client, name=self.mcp_id)

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
                f"Failed to build member MCP server '{self.config.get('id')}': {e}"
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
        logger.info(f"the headers are {headers}")
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
                    headers=headers
                )

            case AuthStrategy.DYNAMIC_BEARER:
                http_client = DynamicTokenClient(
                    base_url=base_url,
                    token_url=auth_config.get(ConfigKey.Token_URL),
                    api_key=auth_config.get(ConfigKey.APIKEY),
                    media_type=auth_config.get(ConfigKey.MEDIA_TYPE, "")
                )
            case AuthStrategy.BEARER:
                logger.info("Setting up header and client for bearer")
                headers[ConfigKey.AUTH_HEADER.value] = f"Bearer {auth_config.get(ConfigKey.TOKEN)}"
                http_client = httpx.AsyncClient(base_url=base_url, headers=headers)

            case AuthStrategy.APITOKEN:
                logger.info("Setting up header and client for apiToken")
                headers[ConfigKey.AUTH_HEADER.value] = (
                    f"{auth_config.get(ConfigKey.AUTH_PREFIX)} {auth_config.get(ConfigKey.TOKEN)}"
                )
                logger.info(f"the headers are updated {headers} and the url is {base_url}")
                http_client = httpx.AsyncClient(base_url=base_url, headers=headers)

            case AuthStrategy.APIKEY:
                logger.info("Setting up header and client for apikey")
                headers[ConfigKey.AUTH_HEADER.value] = (
                    f"{auth_config.get(ConfigKey.AUTH_PREFIX)} {auth_config.get(ConfigKey.APIKEY)}"
                )
                logger.info(f"the headers are updated {headers} and the url is {base_url}")
                http_client = httpx.AsyncClient(base_url=base_url, headers=headers)

            case AuthStrategy.JSESSIONID.value:
                logger.info("Setting up header and client for jessionid")
                try:
                    token_manager = DynamicTokenManager(base_url=base_url,auth_strategy=self.config[ConfigKey.AUTH_STRATEGY],
                                                        login_url=auth_config.get(ConfigKey.LOGIN_URL),
                                                        username=auth_config.get(ConfigKey.USERNAME), 
                                                        password=auth_config.get(ConfigKey.PASSWORD))
                    
                    http_client = await token_manager.get_authenticated_http_client_for_jessonid()
                except KeyError as e:
                    # Required config missing
                    logger.error(f"Missing configuration key: {e}")
                

                except httpx.HTTPError as e:
                    # Any HTTP-related error from httpx
                    logger.error(f"HTTP error during authentication: {e}")
                 

                except Exception as e:
                    # Catch-all for unexpected errors
                    logger.error(f"Unexpected error: {e}")
                         
            case _:
                # Default/fallback client
                http_client = httpx.AsyncClient(base_url=base_url)

        #QUICK FIX TO SCHEMA UNRAVELING ISSUE BELOW
        spec = jsonref.loads(json.dumps(spec), load_on_repr=True)
        mcp = FastMCP.from_openapi(spec, client=http_client, route_maps=custom_mappings)
        return mcp
        
    async def _build_from_graphql(self) -> FastMCP:
        logger.info("Setting up Graphql MCP Server %s", self.config)
        tool = GraphQLTool(self.config)
        mcp = FastMCP(self.config.get(ConfigKey.ID,""))
        mcp.add_tool(tool)
        return mcp
            

    def _build_from_fastapi(self) -> FastMCP:
        raise NotImplementedError("Local file loading not yet supported.")

    async def _build_from_local_file(self) -> FastMCP:
        mcp = FastMCP(self.config.get(ConfigKey.ID,""))
        data = await load_json(self.config[ConfigKey.PROMPT_PATH])
        for entry in data:
            prompt = await build_prompt_from_dict(entry)
            logger.info("Prompt: %s", prompt)
            mcp.add_prompt(prompt)
        return mcp