import asyncio
import base64
import hashlib
import secrets
import uuid, socket, webbrowser
from typing import Any
from urllib.parse import urlparse, urlunparse
import httpx
import jwt
import os
from aiohttp import web
from mcp.server.auth.middleware.auth_context import get_access_token
from urllib.parse import urlencode
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response
from mcp_composer import MCPComposer
from mcp_composer.core.auth_handler.oauth import ServerSettings, SimpleOAuthProvider
from mcp_composer.core.utils.logger import LoggerFactory

logger = LoggerFactory.get_logger()


def get_issuer(remote_url: str):
    """
    Normalize issuer base and choose transport type based on URL suffix.
    Returns (issuer_base, transport_class).
    """
    u = remote_url.rstrip("/")
    if u.endswith("/sse"):
        return u[:-4]
    elif u.endswith("/mcp"):
        return u[:-4]
    else:
        # default to SSE if not explicit
        return u

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

def _get_free_port() -> int:
    s = socket.socket(); s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]; s.close()
    return port


async def wait_for_callback(expected_path="/callback", listen_port=9000, timeout=120):
    """Runs a local aiohttp server to listen for the callback, returns code and state."""
    result = {}
    result: dict[str, str] = {}
    path = expected_path if expected_path.startswith("/") else f"/{expected_path}"
    port = listen_port or _get_free_port()

    async def handle_callback(request):
        params = request.rel_url.query
        result["code"] = params.get("code")
        result["state"] = params.get("state")
        # Simple HTML response for the browser
        return web.Response(text="Authentication complete. You may close this window.")

    app = web.Application()
    app.router.add_get(path, handle_callback)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "localhost", port)
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


async def discover_oauth_metadata(issuer_base: str) -> dict:
    """
    Discover OAuth endpoints from your MCP server:
    - /.well-known/oauth-authorization-server (preferred)
    - fallback: /.well-known/openid-configuration
    """
    issuer = issuer_base.rstrip("/")
    async with httpx.AsyncClient(timeout=10) as client:
        for path in ("/.well-known/oauth-authorization-server", "/.well-known/openid-configuration"):
            try:
                r = await client.get(f"{issuer}{path}")
                r.raise_for_status()
                meta = r.json()
                return {
                    "authorization_endpoint": meta.get("authorization_endpoint"),
                    "token_endpoint": meta.get("token_endpoint"),
                    "issuer": meta.get("issuer") or issuer,
                    "registration_endpoint": meta.get("registration_endpoint"),
                    "scopes_supported": meta.get("scopes_supported", []),
                }
            except Exception:
                continue
    raise RuntimeError(f"Failed OAuth discovery from {issuer_base}")


async def dynamic_client_register(registration_endpoint: str, redirect_uri: str) -> str:
    """
    RFC 7591 dynamic registration for a native (public) client.
    Returns client_id.
    """
    payload = {
        "application_type": "native",
        "token_endpoint_auth_method": "none",
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "redirect_uris": [redirect_uri],
        "client_name": "mcp-cli",
    }
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(registration_endpoint, json=payload,
                                 headers={"Accept": "application/json"})
        resp.raise_for_status()
        data = resp.json()
        cid = data.get("client_id")
        if not cid:
            raise RuntimeError("Dynamic registration succeeded but no client_id returned.")
        return cid

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

async def oauth_pkce_login_async(issuer: str, scope: str = "openid", client_id: str | None = None) -> dict:
    """
    Fully async OAuth Authorization Code + PKCE using a loopback redirect.
    - Discovers endpoints from server_url base
    - Spins aiohttp loopback listener
    - Opens browser
    - Exchanges code for tokens
    Returns token dict (access_token, refresh_token if provided, etc.)
    """

    meta = await discover_oauth_metadata(issuer)
    authz = meta["authorization_endpoint"]; token_ep = meta["token_endpoint"]
    if not authz or not token_ep:
        raise RuntimeError("Discovery missing authorization/token endpoints.")

    # Loopback receiver
    port = _get_free_port()
    redirect_uri = f"http://127.0.0.1:{port}/callback"


    # 2) Else try dynamic registration if available
    if not client_id and meta.get("registration_endpoint"):
        try:
            client_id = await dynamic_client_register(meta["registration_endpoint"], redirect_uri)
        except Exception as e:
            # fall back to requiring a pre-registered client id
            raise RuntimeError(
                f"Dynamic client registration failed: {e}. "
                "Please register a public client and provide its client_id."
            )

    # 3) If still no client_id, we *must* fail (your AS rejects ephemeral IDs)
    if not client_id:
        raise RuntimeError(
            "Authorization server requires a registered client_id. "
            "Please register a public client and pass its client_id to the CLI."
        )
    # PKCE
    verifier, challenge = generate_pkce_pair()
    preferred_scopes = ["openid", "profile", "email"]  # ask for these if allowed
    supported = meta.get("scopes_supported", [])

    # If the server advertises scopes, only request the intersection.
    if supported:
        req = [s for s in preferred_scopes if s in supported]
        # If none of our preferred scopes are supported, try a sensible default like the first supported,
        # or omit "scope" entirely (some AS treat missing scope as default).
        scope_str = " ".join(req) if req else None
    else:
        # If server doesn't publish scopes, you can try omitting scope (common) or use your MCP scope if you know it.
        scope_str = None  # or "mcp" if your resource expects it

    # Build authorization URL manually (Authlib’s OAuth2Client is sync; we keep the flow async here)
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        # "state": ...  # optional: could add your own if you want to validate
    }
    if scope_str:
        params["scope"] = scope_str
    auth_url = f"{authz}?{urlencode(params)}"

    # Open system browser and wait for callback concurrently
    webbrowser.open(auth_url, new=1)
    code, _state = await wait_for_callback("/callback", listen_port=port, timeout=180)

    # Exchange code for tokens
    async with httpx.AsyncClient(timeout=15) as client:
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "code_verifier": verifier,
        }
        resp = await client.post(token_ep, data=data, headers={"Accept": "application/json"})
        resp.raise_for_status()
        return resp.json()