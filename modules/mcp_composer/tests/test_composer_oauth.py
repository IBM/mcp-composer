import os
import sys
import asyncio
import jwt

from typing import Any
from urllib.parse import urlparse
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response
from mcp.server.auth.middleware.auth_context import get_access_token

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from mcp_composer.core.auth_handler.providers import OAuthProviderFactory
from mcp_composer.core.utils import LoggerFactory
from mcp_composer.core.composer import MCPComposer
from mcp_composer.core.auth_handler.oauth import ServerSettings

logger = LoggerFactory.get_logger()


def create_mcp_server(settings: ServerSettings) -> MCPComposer:
    filtered_settings = {
        key: value
        for key, value in settings.model_dump(exclude_none=True).items()
        if value != "" and value != b""
    }
    oauth_provider = OAuthProviderFactory(**filtered_settings).get_provider_instance()
    gw = MCPComposer("composer", auth=oauth_provider)
    return gw


async def main():
    settings = ServerSettings()
    logger.info("Starting MCP Composer with settings:%s", settings.dict())
    gw = create_mcp_server(settings)
    await gw.setup_member_servers()
    # await gw.run_stdio_async()
    # await gw.run_sse_async(host="localhost", port=9000, log_level="debug")
    await gw.run_http_async(host="localhost", port=9000, log_level="debug", path="/mcp")


if __name__ == "__main__":
    asyncio.run(main())
