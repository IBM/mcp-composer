import os
import secrets
import time

from dotenv import load_dotenv
from fastmcp.exceptions import NotFoundError
from fastmcp.server.auth.auth import OAuthProvider
from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    RefreshToken,
    construct_redirect_uri,
)
from mcp.server.auth.settings import ClientRegistrationOptions
from mcp.shared._httpx_utils import create_mcp_http_client
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from pydantic import AnyHttpUrl, AnyUrl
from pydantic_settings import BaseSettings, SettingsConfigDict
from starlette.exceptions import HTTPException

from mcp_composer.core.utils import LoggerFactory

logger = LoggerFactory.get_logger()
load_dotenv()


class ServerSettings(BaseSettings):
    """Settings for the simple OAuth MCP server."""

    try:
        model_config = SettingsConfigDict(env_prefix="OAUTH_")
        if os.getenv("ENABLE_OAUTH", "False").lower() == "true":
            # Server settings
            host: str = os.environ["OAUTH_HOST"]
            port: str = os.environ["OAUTH_PORT"]
            server_url: AnyHttpUrl = AnyHttpUrl(os.environ["OAUTH_SERVER_URL"])

            # OAuth settings - MUST be provided via environment variables
            client_id: str = os.environ["OAUTH_CLIENT_ID"]
            client_secret: str = os.environ["OAUTH_CLIENT_SECRET"]
            callback_path: str = os.environ["OAUTH_CALLBACK_PATH"]

            # OAuth URLs
            auth_url: str = os.environ["OAUTH_AUTH_URL"]
            token_url: str = os.environ["OAUTH_TOKEN_URL"]

            mcp_scope: str = os.environ["OAUTH_MCP_SCOPE"]
            scope: str = os.environ["OAUTH_PROVIDER_SCOPE"]

    except KeyError as err:
        raise NotFoundError(
            "Failed to load settings. Make sure environment variables are set:{err}"
        ) from err

    def __init__(self, **data):
        """Initialize settings with values from environment variables.

        Note: client_id and client_secret are required but can be
        loaded automatically from environment variables (CLIENT_ID
        and CLIENT_SECRET) and don't need to be passed explicitly.
        """
        super().__init__(**data)


class SimpleOAuthProvider(OAuthProvider):
    """OAuth provider with essential functionality."""

    def __init__(self, settings: ServerSettings):
        self.settings = settings
        self.clients: dict[str, OAuthClientInformationFull] = {}
        self.auth_codes: dict[str, AuthorizationCode] = {}
        self.tokens: dict[str, AccessToken] = {}
        self.state_mapping: dict[str, dict[str, str]] = {}
        # Store tokens with MCP tokens using the format:
        # {"mcp_token": "auth_token"}
        self.token_mapping: dict[str, str] = {}
        self.issuer_url = settings.server_url
        self.service_documentation_url = settings.server_url
        self.client_registration_options = ClientRegistrationOptions(
            enabled=True,
            valid_scopes=[settings.mcp_scope],
            default_scopes=[settings.mcp_scope],
        )
        self.revocation_options = None
        self.required_scopes = None

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        """Get OAuth client information."""
        return self.clients.get(client_id)

    async def register_client(self, client_info: OAuthClientInformationFull):
        """Register a new OAuth client."""
        self.clients[client_info.client_id] = client_info

    async def authorize(
        self, client: OAuthClientInformationFull, params: AuthorizationParams
    ) -> str:
        """Generate an authorization URL for OAuth flow."""
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

        # Build oauth authorization URL
        auth_url = (
            f"{self.settings.auth_url}"
            f"?client_id={self.settings.client_id}"
            f"&redirect_uri={self.settings.callback_path}"
            f"&scope={self.settings.scope}"
            f"&state={state}"
            f"&response_type=code"
        )
        return auth_url

    async def handle_callback(self, code: str, state: str) -> str:
        """Handle OAuth callback."""
        state_data = self.state_mapping.get(state)
        if not state_data:
            raise HTTPException(400, "Invalid state parameter")

        redirect_uri = state_data["redirect_uri"]
        code_challenge = state_data["code_challenge"]
        redirect_uri_provided_explicitly = (
            state_data["redirect_uri_provided_explicitly"] == "True"
        )
        client_id = state_data["client_id"]
        # Exchange code for token with oauth provider
        async with create_mcp_http_client() as client:
            response = await client.post(
                self.settings.token_url,
                data={
                    "client_id": self.settings.client_id,
                    "client_secret": self.settings.client_secret,
                    "code": code,
                    "redirect_uri": f"{self.settings.callback_path}",
                    "grant_type": "authorization_code",
                },
                headers={"Accept": "application/json"},
            )

            if response.status_code != 200:
                raise HTTPException(400, "Failed to exchange code for token")

            data = response.json()

            if "error" in data:
                raise HTTPException(400, data.get("error_description", data["error"]))

            auth_token = data.get("id_token") or data.get("access_token")

            if not auth_token:
                raise ValueError("No valid authentication token found in response.")

            # Create MCP authorization code
            new_code = f"mcp_{secrets.token_hex(16)}"
            auth_code = AuthorizationCode(
                code=new_code,
                client_id=client_id,
                redirect_uri=AnyUrl(redirect_uri),
                redirect_uri_provided_explicitly=redirect_uri_provided_explicitly,
                expires_at=time.time() + 300,
                scopes=[self.settings.mcp_scope],
                code_challenge=code_challenge,
            )
            self.auth_codes[new_code] = auth_code

            # Store oauth token - we'll map the MCP token to this later
            self.tokens[f"auth_{auth_token}"] = AccessToken(
                token=auth_token,
                client_id=client_id,
                scopes=[self.settings.scope],
                expires_at=None,
            )
            self.token_mapping[new_code] = auth_token

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

        # Find auth token for this client
        auth_token = next(
            (
                token
                for token, data in self.tokens.items()
                if (token.startswith("auth_")) and data.client_id == client.client_id
            ),
            None,
        )

        # Store mapping between MCP token and oauth token
        if auth_token:
            self.token_mapping[mcp_token] = auth_token

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

    async def revoke_token(self, token: str) -> None:
        """Revoke a token."""
        if token in self.tokens:
            del self.tokens[token]
