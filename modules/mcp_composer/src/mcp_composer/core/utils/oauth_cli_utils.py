import asyncio
import base64
import hashlib
import secrets
import webbrowser
from typing import Any
from urllib.parse import urlparse, urlunparse

import jwt
from aiohttp import web
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import (
    AuthorizationParams,
)
from mcp.shared.auth import OAuthClientInformationFull
from pydantic import AnyUrl, TypeAdapter

from mcp_composer import MCPComposer
from mcp_composer.core.auth_handler.oauth import ServerSettings, SimpleOAuthProvider
from mcp_composer.core.utils.logger import LoggerFactory

logger = LoggerFactory.get_logger()


def generate_pkce_pair():
    # Step 1: Generate a secure random code_verifier (43-128 characters)
    code_verifier = secrets.token_urlsafe(64)
    # Step 2: Create the code_challenge (SHA256, base64url, no '=' padding)
    code_challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest())
        .rstrip(b"=")
        .decode("ascii")
    )
    return code_verifier, code_challenge


# Usage


def sanitize_url(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("Invalid URL")
    return urlunparse(parsed)


async def wait_for_callback(expected_path, listen_port=9000, timeout=120):
    """Runs a local aiohttp server to listen for the callback, returns code and state."""
    result = {}

    async def handle_callback(request):
        params = request.rel_url.query
        result["code"] = params.get("code")
        result["state"] = params.get("state")
        # Simple HTML response for the browser
        return web.Response(text="Authentication complete. You may close this window.")

    app = web.Application()
    app.router.add_get(expected_path, handle_callback)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "localhost", listen_port)
    await site.start()

    # Wait until callback received or timeout
    try:
        for _ in range(timeout * 10):
            await asyncio.sleep(0.1)
            if result:
                break
        else:
            raise TimeoutError("Timed out waiting for OAuth callback.")
    finally:
        await runner.cleanup()

    return result["code"], result["state"]


async def create_mcp_server(settings: ServerSettings) -> MCPComposer:
    logger.info("Creating MCP Composer server with OAuth support...")
    oauth_provider = SimpleOAuthProvider(settings)

    redirect_uris = [TypeAdapter(AnyUrl).validate_python(settings.callback_path)]

    client_info = OAuthClientInformationFull(  # fill this as per your app requirements
        client_id=settings.client_id,
        client_secret=settings.client_secret,
        redirect_uris=redirect_uris,
    )

    _, code_challenge = generate_pkce_pair()
    params = AuthorizationParams(
        state=None,
        redirect_uri=AnyUrl(settings.callback_path),
        code_challenge=code_challenge,
        redirect_uri_provided_explicitly=True,
        scopes=settings.scope.split(" ") if settings.scope else [],
    )

    auth_url = await oauth_provider.authorize(client_info, params)
    logger.info("Generated authorization URL: %s", auth_url)
    safe_url = sanitize_url(auth_url)
    webbrowser.open(safe_url)
    print(f"Browser opened with: {safe_url}")
    callback_path = urlparse(settings.callback_path).path
    logger.info("Callback path set to: %s", callback_path)

    # --- HANDLE CALLBACK ---
    parsed = urlparse(callback_path)
    print(f"Parsed callback path: {parsed}")
    listen_port = parsed.port or 9000
    expected_path = parsed.path
    print(f"Listening for callback on {expected_path} at port {listen_port}")

    code, state = await wait_for_callback(expected_path, listen_port)

    print(f"Received OAuth code: {code}, state: {state}")

    # --- Complete the token exchange using the callback code/state ---
    # (You will need an async method for this, e.g., oauth_provider.exchange_token(...))
    token = await oauth_provider.handle_callback(code, state)
    print(f"OAuth token received: {token}")

    # Continue with your app, e.g., configure MCPComposer with token
    gw = MCPComposer("composer", auth=oauth_provider)

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
            auth_token = list(oauth_provider.token_mapping.values())[0]

        else:
            auth_token = oauth_provider.token_mapping.get(access_token.token)

        if not auth_token:
            raise ValueError("No auth token found for user")

        return auth_token

    return gw
