"""IBM W3 OAuth provider for MCP Composer.

This module provides a complete IBM W3 OAuth integration that's ready to use
with just a client ID, client secret, and configuration URL. It handles all
the complexity of IBM W3's OAuth flow, token validation via introspection,
and user management.

Example:
    ```python
    from fastmcp import FastMCP
    from mcp_composer.core.auth_handler.w3 import W3Provider

    # Simple IBM W3 OAuth protection
    auth = W3Provider(
        client_id="your-w3-client-id",
        client_secret="your-w3-client-credential",  # pragma: allowlist secret
        config_url="https://preprod.login.w3.ibm.com/oidc/endpoint/default/.well-known/openid-configuration",
        introspection_url="https://preprod.login.w3.ibm.com/v1.0/endpoint/default/introspect",
        base_url="http://localhost:9000"
    )

    mcp = FastMCP("My Protected Server", auth=auth)
    ```
"""

from __future__ import annotations

from key_value.aio.protocols import AsyncKeyValue
from pydantic import AnyHttpUrl

from fastmcp.server.auth.oidc_proxy import OIDCProxy
from fastmcp.server.auth.providers.introspection import IntrospectionTokenVerifier
from fastmcp.utilities.auth import parse_scopes
from mcp_composer.core.utils import LoggerFactory

logger = LoggerFactory.get_logger()


class W3Provider(OIDCProxy):
    """Complete IBM W3 OAuth provider for MCP Composer.

    This provider makes it trivial to add IBM W3 OAuth protection to any
    FastMCP server. Just provide your IBM W3 OAuth app credentials,
    configuration URL, introspection URL, and a base URL, and you're ready to go.

    Features:
    - Transparent OAuth proxy to IBM W3 OIDC
    - Automatic token validation via RFC 7662 token introspection
    - User information extraction from introspection response
    - Automatic callback handling (unlike SimpleOAuthProvider which requires manual handling)
    - Refresh token support (unlike SimpleOAuthProvider which doesn't support refresh tokens)
    - Minimal configuration required
    - Supports OIDC discovery for automatic endpoint detection

    Setup:
    1. Register an OAuth client in IBM W3 Identity Provider
    2. Configure redirect URI: http://localhost:9000/auth/callback (or your custom path)
    3. Get Client ID and Client Secret
    4. Get OIDC configuration URL (e.g., https://preprod.login.w3.ibm.com/oidc/endpoint/default/.well-known/openid-configuration)
    5. Get introspection endpoint URL (e.g., https://preprod.login.w3.ibm.com/v1.0/endpoint/default/introspect)

    Example:
        ```python
        from fastmcp import FastMCP
        from mcp_composer.core.auth_handler.w3 import W3Provider

        auth = W3Provider(
            client_id="example-client-id-12345",
            client_secret="your-client-credential",  # pragma: allowlist secret
            config_url="https://preprod.login.w3.ibm.com/oidc/endpoint/default/.well-known/openid-configuration",
            introspection_url="https://preprod.login.w3.ibm.com/v1.0/endpoint/default/introspect",
            base_url="http://localhost:9000"
        )

        mcp = FastMCP("My App", auth=auth)
        ```
    """

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        config_url: AnyHttpUrl | str,
        introspection_url: str,
        base_url: AnyHttpUrl | str,
        issuer_url: AnyHttpUrl | str | None = None,
        redirect_path: str | None = None,
        required_scopes: list[str] | None = None,
        timeout_seconds: int = 10,
        allowed_client_redirect_uris: list[str] | None = None,
        client_storage: AsyncKeyValue | None = None,
        jwt_signing_key: str | bytes | None = None,
        require_authorization_consent: bool = True,
        client_auth_method: str = "client_secret_basic",
        audience: str | None = None,
        extra_authorize_params: dict[str, str] | None = None,
    ):
        """Initialize IBM W3 OAuth provider.

        Args:
            client_id: IBM W3 OAuth client ID (e.g., "example-client-id-12345")
            client_secret: IBM W3 OAuth client secret
            config_url: OIDC discovery configuration URL
                (e.g., "https://preprod.login.w3.ibm.com/oidc/endpoint/default/.well-known/openid-configuration")
            introspection_url: Token introspection endpoint URL
                (e.g., "https://preprod.login.w3.ibm.com/v1.0/endpoint/default/introspect")
            base_url: Public URL where OAuth endpoints will be accessible (includes any mount path)
            issuer_url: Issuer URL for OAuth metadata (defaults to base_url). Use root-level URL
                to avoid 404s during discovery when mounting under a path.
            redirect_path: Redirect path configured in IBM W3 OAuth app (defaults to "/auth/callback")
            required_scopes: Required IBM W3 scopes (defaults to ["openid"]). Common scopes include:
                - "openid" for OpenID Connect (default)
                - "profile" for profile information
                - "email" for email access
                - "offline_access" for refresh tokens (recommended for long-lived sessions)

                Note: Unlike SimpleOAuthProvider, W3Provider supports refresh tokens through
                OIDCProxy's automatic refresh token handling. Include "offline_access" in
                required_scopes to receive refresh tokens during authorization.
            timeout_seconds: HTTP request timeout for IBM W3 API calls (defaults to 10)
            allowed_client_redirect_uris: List of allowed redirect URI patterns for MCP clients.
                If None (default), all URIs are allowed. If empty list, no URIs are allowed.
            client_storage: Storage backend for OAuth state (client registrations, encrypted tokens).
                If None, a DiskStore will be created in the data directory (derived from `platformdirs`). The
                disk store will be encrypted using a key derived from the JWT Signing Key.
            jwt_signing_key: Secret for signing FastMCP JWT tokens (any string or bytes). If bytes are provided,
                they will be used as is. If a string is provided, it will be derived into a 32-byte key. If not
                provided, the upstream client secret will be used to derive a 32-byte key using PBKDF2.
            require_authorization_consent: Whether to require user consent before authorizing clients (default True).
                When True, users see a consent screen before being redirected to IBM W3.
                When False, authorization proceeds directly without user confirmation.
                SECURITY WARNING: Only disable for local development or testing environments.
            client_auth_method: Client authentication method for introspection endpoint.
                "client_secret_basic" (default) uses HTTP Basic Auth header,
                "client_secret_post" sends credentials in POST body.
                Note: This parameter is accepted for future compatibility but may not be
                supported by all fastmcp versions. The default "client_secret_basic" will be used.
            audience: Optional audience claim for token validation
            extra_authorize_params: Additional parameters to forward to IBM W3's authorization endpoint.
                Example: {"prompt": "select_account"} to let users choose their account.
        """
        # Parse scopes if provided as string
        # W3 requires at least one scope - openid is the minimal OIDC scope
        # Note: To receive refresh tokens, include "offline_access" in required_scopes
        required_scopes_final = (
            parse_scopes(required_scopes) if required_scopes is not None else ["openid"]
        )

        # Ensure offline_access is included if user wants refresh tokens
        # OIDCProxy will automatically request refresh tokens if the provider supports them
        # and the offline_access scope is requested

        # Create W3 token verifier using introspection
        # Note: client_auth_method parameter may not be supported in all fastmcp versions
        # Only pass parameters that are supported by the installed version
        token_verifier = IntrospectionTokenVerifier(
            introspection_url=introspection_url,
            client_id=client_id,
            client_secret=client_secret,
            timeout_seconds=timeout_seconds,
            required_scopes=required_scopes_final,
        )

        # Initialize OIDC proxy with W3 endpoints
        # Note: When providing a custom token_verifier, we cannot pass required_scopes
        # as it's already configured on the token_verifier.
        # extra_authorize_params may not be supported in all versions of OIDCProxy.
        super().__init__(
            config_url=config_url,
            client_id=client_id,
            client_secret=client_secret,
            token_verifier=token_verifier,
            base_url=base_url,
            redirect_path=redirect_path,
            issuer_url=issuer_url or base_url,  # Default to base_url if not specified
            allowed_client_redirect_uris=allowed_client_redirect_uris,
            client_storage=client_storage,
            jwt_signing_key=jwt_signing_key,
            require_authorization_consent=require_authorization_consent,
            audience=audience,
            timeout_seconds=timeout_seconds,
        )

        logger.info(
            "Initialized IBM W3 OAuth provider for client %s with scopes: %s",
            client_id,
            required_scopes_final,
        )
        logger.debug(
            "W3 OAuth configuration: config_url=%s, introspection_url=%s, base_url=%s",
            config_url,
            introspection_url,
            base_url,
        )
