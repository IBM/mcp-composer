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
from mcp_composer.core.utils import LoggerFactory
from mcp_composer.core.composer import MCPComposer
from mcp_composer.core.auth_handler.oauth import ServerSettings, SimpleOAuthProvider

logger = LoggerFactory.get_logger()


def create_mcp_server(settings: ServerSettings) -> MCPComposer:
    oauth_provider = SimpleOAuthProvider(settings)
    gw = MCPComposer("composer", auth=oauth_provider)
    callback_path = urlparse(settings.callback_path).path

    @gw.custom_route(f"{callback_path}", methods=["GET"])
    async def callback_handler(request: Request) -> Response:
        """Handle OAuth callback."""
        code = request.query_params.get("code")
        state = request.query_params.get("state")

        if not code or not state:
            raise HTTPException(400, "Missing code or state parameter")

        try:
            redirect_uri = await oauth_provider.handle_callback(code, state)
            return RedirectResponse(status_code=302, url=redirect_uri)
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Unexpected error", exc_info=e)
            return JSONResponse(
                status_code=500,
                content={
                    "error": "server_error",
                    "error_description": "Unexpected error",
                },
            )

    @gw.tool()
    async def get_user_profile() -> dict[str, Any]:
        """
        This tool is just a stub to show you how to access token
        """
        auth_token = get_token().replace("auth_", "")
        payload = jwt.decode(auth_token, options={"verify_signature": False})

        return payload

    def get_token() -> str:
        """Get the token for the authenticated user."""
        access_token = get_access_token()
        if not access_token:
            raise ValueError("Not authenticated")

        # Get token from mapping
        auth_token = oauth_provider.token_mapping.get(access_token.token)

        if not auth_token:
            raise ValueError("No auth token found for user")

        return auth_token

    return gw


async def main():
    settings = ServerSettings()
    gw = create_mcp_server(settings)
    await gw.setup_member_servers()
    await gw.run_http_async(host="0.0.0.0", port=9000, log_level="debug", path="/mcp")


if __name__ == "__main__":
    asyncio.run(main())
