"""Sample MCP server with an OAuth authorization-code provider."""

import logging
import secrets
import time
from typing import Any, Literal

import click
from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    OAuthAuthorizationServerProvider,
    RefreshToken,
    construct_redirect_uri,
)
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions
from fastmcp import FastMCP
from mcp.shared._httpx_utils import create_mcp_http_client
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
import jwt

logger = logging.getLogger(__name__)


class ServerSettings(BaseSettings):
    """Settings for the simple W3 MCP server."""

    model_config = SettingsConfigDict(env_prefix="MCP_W3_")

    # Server settings
    host: str = "localhost"
    port: int = 8080
    server_url: AnyHttpUrl = AnyHttpUrl("http://localhost:8080")

    # w3 OAuth settings - MUST be provided via environment variables
    w3_client_id: str = ""  # set with MCP_W3_W3_CLIENT_ID env variable
    w3_client_secret: str  # set with MCP_W3_W3_CLIENT_SECRET env variable
    w3_callback_path: str = "https://localhost:8080/auth/idaas/callback"

    # w3 OAuth URLs
    w3_auth_url: str = "https://example.com/authorize"
    w3_token_url: str = "https://example.com/token"

    mcp_scope: str = "user"
    w3_scope: str = "openid"

    def __init__(self, **data):
        """Initialize settings with values from environment variables.

        Note: w3_client_id and w3_client_secret are required but can be
        loaded automatically from environment variables (MCP_W3_W3_CLIENT_ID
        and MCP_W3_W3_CLIENT_SECRET) and don't need to be passed explicitly.
        """
        super().__init__(**data)


class SimpleW3OAuthProvider(OAuthAuthorizationServerProvider):
    """Simple W3 OAuth provider with essential functionality."""

    def __init__(self, settings: ServerSettings):
        self.settings = settings
        self.clients: dict[str, OAuthClientInformationFull] = {}
        self.auth_codes: dict[str, AuthorizationCode] = {}
        self.tokens: dict[str, AccessToken] = {}
        self.state_mapping: dict[str, dict[str, str]] = {}
        # Store W3 tokens with MCP tokens using the format:
        # {"mcp_token": "w3_token"}
        self.token_mapping: dict[str, str] = {}

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        """Get OAuth client information."""
        return self.clients.get(client_id)

    async def register_client(self, client_info: OAuthClientInformationFull):
        """Register a new OAuth client."""
        self.clients[client_info.client_id] = client_info

    async def authorize(
        self, client: OAuthClientInformationFull, params: AuthorizationParams
    ) -> str:
        """Generate an authorization URL for W3 OAuth flow."""
        state = params.state or secrets.token_hex(16)

        # Store the state mapping
        self.state_mapping[state] = {
            "redirect_uri": str(params.redirect_uri),
            "code_challenge": params.code_challenge,
            "redirect_uri_provided_explicitly": str(
                params.redirect_uri_provided_explicitly
            ),
            "client_id": client.client_id,
        }

        # Build W3 authorization URL
        auth_url = (
            f"{self.settings.w3_auth_url}"
            f"?client_id={self.settings.w3_client_id}"
            f"&redirect_uri={self.settings.w3_callback_path}"
            f"&scope={self.settings.w3_scope}"
            f"&state={state}"
            f"&response_type=code"
        )

        return auth_url

    async def handle_w3_callback(self, code: str, state: str) -> str:
        """Handle W3 OAuth callback."""
        state_data = self.state_mapping.get(state)
        if not state_data:
            raise HTTPException(400, "Invalid state parameter")

        redirect_uri = state_data["redirect_uri"]
        code_challenge = state_data["code_challenge"]
        redirect_uri_provided_explicitly = (
            state_data["redirect_uri_provided_explicitly"] == "True"
        )
        client_id = state_data["client_id"]

        # Exchange code for token with W3
        async with create_mcp_http_client() as client:
            response = await client.post(
                self.settings.w3_token_url,
                data={
                    "client_id": self.settings.w3_client_id,
                    "client_secret": self.settings.w3_client_secret,
                    "code": code,
                    "redirect_uri": self.settings.w3_callback_path,
                    "grant_type": "authorization_code",
                },
                headers={"Accept": "application/json"},
            )

            if response.status_code != 200:
                raise HTTPException(400, "Failed to exchange code for token")

            data = response.json()

            if "error" in data:
                raise HTTPException(400, data.get("error_description", data["error"]))

            w3_token = data["id_token"]

            # Create MCP authorization code
            new_code = f"mcp_{secrets.token_hex(16)}"
            auth_code = AuthorizationCode(
                code=new_code,
                client_id=client_id,
                redirect_uri=AnyHttpUrl(redirect_uri),
                redirect_uri_provided_explicitly=redirect_uri_provided_explicitly,
                expires_at=time.time() + 300,
                scopes=[self.settings.mcp_scope],
                code_challenge=code_challenge,
            )
            self.auth_codes[new_code] = auth_code

            # Store W3 token - we'll map the MCP token to this later
            self.tokens[f"w3_{w3_token}"] = AccessToken(
                token=w3_token,
                client_id=client_id,
                scopes=[self.settings.w3_scope],
                expires_at=None,
            )

        del self.state_mapping[state]
        return construct_redirect_uri(redirect_uri, code=new_code, state=state)

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> AuthorizationCode | None:
        """Load an authorization code."""
        return self.auth_codes.get(authorization_code)

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode
    ) -> OAuthToken:
        """Exchange authorization code for tokens."""
        if authorization_code.code not in self.auth_codes:
            raise ValueError("Invalid authorization code")

        # Generate MCP access token
        mcp_token = f"mcp_{secrets.token_hex(32)}"

        # Store MCP token
        self.tokens[mcp_token] = AccessToken(
            token=mcp_token,
            client_id=client.client_id,
            scopes=authorization_code.scopes,
            expires_at=int(time.time()) + 3600,
        )

        # Find W3 token for this client
        w3_token = next(
            (
                token
                for token, data in self.tokens.items()
                if (token.startswith("w3_")) and data.client_id == client.client_id
            ),
            None,
        )

        # Store mapping between MCP token and W3 token
        if w3_token:
            self.token_mapping[mcp_token] = w3_token

        del self.auth_codes[authorization_code.code]

        return OAuthToken(
            access_token=mcp_token,
            token_type="bearer",
            expires_in=3600,
            scope=" ".join(authorization_code.scopes),
        )

    async def load_access_token(self, token: str) -> AccessToken | None:
        """Load and validate an access token."""
        access_token = self.tokens.get(token)
        if not access_token:
            return None

        # Check if expired
        if access_token.expires_at and access_token.expires_at < time.time():
            del self.tokens[token]
            return None

        return access_token

    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> RefreshToken | None:
        """Load a refresh token - not supported."""
        return None

    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: RefreshToken,
        scopes: list[str],
    ) -> OAuthToken:
        """Exchange refresh token"""
        raise NotImplementedError("Not supported")

    async def revoke_token(
        self, token: str, token_type_hint: str | None = None
    ) -> None:
        """Revoke a token."""
        if token in self.tokens:
            del self.tokens[token]


def create_simple_mcp_server(settings: ServerSettings) -> FastMCP:
    """Create a simple FastMCP server with W3 OAuth."""
    oauth_provider = SimpleW3OAuthProvider(settings)

    auth_settings = AuthSettings(
        issuer_url=settings.server_url,
        client_registration_options=ClientRegistrationOptions(
            enabled=True,
            valid_scopes=[settings.mcp_scope],
            default_scopes=[settings.mcp_scope],
        ),
        required_scopes=[settings.mcp_scope],
    )

    app = FastMCP(
        name="Simple W3 MCP Server",
        instructions="A simple MCP server with W3 OAuth authentication",
        auth_server_provider=oauth_provider,
        host=settings.host,
        port=settings.port,
        debug=True,
        auth=auth_settings,
    )

    @app.custom_route("/auth/idaas/callback", methods=["GET"])
    async def w3_callback_handler(request: Request) -> Response:
        """Handle W3 OAuth callback."""
        code = request.query_params.get("code")
        state = request.query_params.get("state")

        if not code or not state:
            raise HTTPException(400, "Missing code or state parameter")

        try:
            redirect_uri = await oauth_provider.handle_w3_callback(code, state)
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

    def get_w3_token() -> str:
        """Get the W3 token for the authenticated user."""
        access_token = get_access_token()
        if not access_token:
            raise ValueError("Not authenticated")

        # Get W3 token from mapping
        w3_token = oauth_provider.token_mapping.get(access_token.token)

        if not w3_token:
            raise ValueError("No W3 token found for user")

        return w3_token

    @app.tool()
    async def get_user_profile() -> dict[str, Any]:
        """
        This tool is just a stub to show you how to access w3 token
        """
        w3_token = get_w3_token().replace("w3_", "")
        payload = jwt.decode(w3_token, options={"verify_signature": False})

        return payload

    return app


@click.command()
@click.option("--port", default=8080, help="Port to listen on")
@click.option("--host", default="localhost", help="Host to bind to")
@click.option(
    "--transport",
    default="sse",
    type=click.Choice(["sse", "streamable-http"]),
    help="Transport protocol to use ('sse' or 'streamable-http')",
)
def main(port: int, host: str, transport: Literal["sse", "streamable-http"]) -> int:
    """Run the simple W3 MCP server."""
    logging.basicConfig(level=logging.INFO)

    try:
        # No hardcoded credentials - all from environment variables
        settings = ServerSettings(host=host, port=port)
    except ValueError as e:
        logger.error(
            "Failed to load settings. Make sure environment variables are set:"
        )
        logger.error("MCP_W3_W3_CLIENT_ID=<your-client-id>")
        logger.error("MCP_W3_W3_CLIENT_SECRET=<your-client-secret>")
        logger.error(f"Error: {e}")
        return 1

    mcp_server = create_simple_mcp_server(settings)
    logger.info(f"Starting server with {transport} transport")
    mcp_server.run(transport=transport)
    return 0
