# loaders/builder.py

from typing import Dict
from fastmcp import FastMCP, Client
from fastmcp.client.auth import OAuth
from fastmcp.client.transports import StreamableHttpTransport, SSETransport
from fastmcp.client.auth.oauth import FileTokenStorage

import httpx
from mcp_composer.utils.logger import LoggerFactory
from mcp_composer.utils import *
from mcp_composer.auth_handler import DynamicTokenClient


logger = LoggerFactory.get_logger()

import sys


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
        logger.info(f"Builing new {self.mcp_type} Server")

        if self.mcp_type == "client":
            return await self._build_from_client()

        elif self.mcp_type in {"http", "sse"}:
            return await self._build_from_transport(transport_type=self.mcp_type)

        elif self.mcp_type == "openapi":
            return await self._build_from_openapi()

        elif self.mcp_type == "fastapi":
            return self._build_from_fastapi()

        elif self.mcp_type == "local":
            return self._build_from_local_file()

        else:
            raise ValueError(f"Unsupported MCP type: {self.mcp_type}")

    async def _build_from_transport(self, transport_type=None) -> FastMCP:
        # auth = build_auth_strategy(self.config["auth_strategy"], self.config.get("auth", {}))
        # headers = await auth.get_headers()

        config = self.config
        endpoint = config["endpoint"]
        headers = config.get("headers")
        oauth = config.get("auth")

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
        TransportClass = transport_classes.get(transport_type)
        if not TransportClass:
            raise ValueError(f"Unsupported MCP type: {transport_type}")

        transport = TransportClass(url=endpoint, headers=headers, auth=auth)

        # Create the client and wrap it with FastMCP
        client = Client(transport, auth=auth)
        return FastMCP.from_client(client, name=self.mcp_id)

    async def _build_from_client(self) -> FastMCP:
        # auth = build_auth_strategy(self.config["auth_strategy"], self.config.get("auth", {}))
        # headers = await auth.get_headers()

        client = Client(self.config["endpoint"])

        headers = self.config.get("headers")
        if headers:
            transport = StreamableHttpTransport(
                url=self.config["endpoint"], headers=headers
            )
            client = Client(transport)
        try:
            return FastMCP.from_client(client, name=self.mcp_id)
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

        headers = {}
        http_client = httpx.AsyncClient(base_url=openapi_config[ConfigKey.ENDPOINT])

        if self.config[ConfigKey.AUTH_STRATEGY] == AuthStrategy.DYNAMIC_BEARER:
            http_client = DynamicTokenClient(
                base_url=openapi_config[ConfigKey.ENDPOINT],
                token_url=self.config[ConfigKey.AUTH][ConfigKey.Token_URL],
                api_key=self.config[ConfigKey.AUTH][ConfigKey.APIKEY],
            )

        if self.config[ConfigKey.AUTH_STRATEGY] == AuthStrategy.BEARER:
            logger.info("Setting up header and client for bearer")
            headers[ConfigKey.AUTH_HEADRR] = (
                f"Bearer {self.config[ConfigKey.AUTH][ConfigKey.TOKEN]}"
            )
            http_client = httpx.AsyncClient(
                base_url=openapi_config[ConfigKey.ENDPOINT], headers=headers
            )

        mcp = FastMCP.from_openapi(spec, client=http_client, route_maps=custom_mappings)

        return mcp

    def _build_from_fastapi(self) -> FastMCP:
        raise NotImplementedError("Local file loading not yet supported.")

    def _build_from_local_file(self) -> FastMCP:
        raise NotImplementedError("Local file loading not yet supported.")
