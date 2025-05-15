# loaders/builder.py

from typing import Dict
from fastmcp import FastMCP, Client
from fastmcp.client.transports import StreamableHttpTransport, SSETransport
import httpx
from mcp_gateway.utils.logger import LoggerFactory
from mcp_gateway.utils import ServerConfigValidator, ValidationError
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
        logger.info(f"Builing new { self.mcp_type} Server")
            
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

        headers = self.config.get("headers")
        if transport_type == 'http':
            transport = StreamableHttpTransport(
                url=self.config["endpoint"],
                headers=headers
            )
        elif transport_type == 'sse':
            transport = SSETransport(
                url=self.config["endpoint"], headers=headers
            )
        else:
            raise ValueError(f"Unsupported MCP type: {self.mcp_type}")
        client = Client(transport)
        return FastMCP.from_client(client, name=self.mcp_id)

    
    async def _build_from_client(self) -> FastMCP:
        # auth = build_auth_strategy(self.config["auth_strategy"], self.config.get("auth", {}))
        # headers = await auth.get_headers()
        
        client = Client(self.config["endpoint"])
        
        headers = self.config.get("headers")
        if headers:
            transport = StreamableHttpTransport(
                url=self.config["endpoint"],
                headers= headers
            )
            client = Client(transport)
        try:
            return FastMCP.from_client(client, name=self.mcp_id)
        except Exception as e:
            logger.exception(f"Failed to build member MCP server '{self.config.get('id')}': {e}")
            raise RuntimeError(f"Failed to build member MCP server '{self.mcp_id}'") from e
    
    async def _build_from_openapi(self) -> FastMCP:
        # auth = build_auth_strategy(self.config["auth_strategy"], self.config.get("auth", {}))
        # headers = await auth.get_headers()
        # client=httpx.AsyncClient(base_url=self.config["endpoint"], auth=auth, headers=headers),
        
        async with httpx.AsyncClient(base_url=self.config["endpoint"]) as client:
            response = await client.get(self.config["openapi_url"])
            response.raise_for_status()
            spec = response.json()

        return FastMCP.from_openapi(
            openapi_spec=spec,
            client=httpx.AsyncClient(base_url=self.config["endpoint"]),
            name=self.mcp_id
        )

    def _build_from_fastapi(self) -> FastMCP:
        raise NotImplementedError("Local file loading not yet supported.")

    def _build_from_local_file(self) -> FastMCP:
        raise NotImplementedError("Local file loading not yet supported.")
