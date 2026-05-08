import json
import time
from typing import Any
import urllib.parse
import httpx
import jwt

from mcp_composer.core.auth_handler.oauth_handler import resolve_env_value
from mcp_composer.core.auth.jwt.jwt_utils import decode_jwt_without_verification
from mcp_composer.core.utils import ConfigKey, LoggerFactory
from mcp_composer.middleware.auth_context_middleware import (
    get_auth_context,
    AUTH_KEY_AUTH_TOKEN,
    AUTH_KEY_ISV_TOKEN,
    AUTH_KEY_ORG,
)

logger = LoggerFactory.get_logger()

DEFAULT_TOKEN_EXPIRY = 3600
TOKEN_REFRESH_BUFFER = 60
DEFAULT_SCOPE = "user:all"

DEFAULT_TIMEOUT = 30.0


class AsperaJWTClient(httpx.AsyncClient):
    """
    Async HTTP client for IBM Aspera on Cloud using OAuth2 JWT Bearer (RFC 7523).

    Flow:
      1) Build RS256-signed JWT (iss=client_id, sub=user email, aud=token_url, iat/nbf/exp/jti)
      2) POST assertion to token URL (form-encoded) to obtain access_token
      3) Attach Bearer token to subsequent requests
      4) Auto-refresh before expiry
    """

    def __init__(
        self,
        base_url: str,
        auth_data: dict[str, Any] | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> None:
        if not base_url:
            raise ValueError("base_url cannot be empty")
        if timeout <= 0:
            raise ValueError("timeout must be positive")

        self._access_token: str | None = None
        self._expires_at: float = 0.0
        self.auth_data = auth_data or {}
        self._resolved_token_url: str | None = None

        super().__init__(
            base_url=base_url, timeout=timeout, headers=headers or {}, **kwargs
        )

    def _encode_dict_to_json(self, input_dict: dict[str, Any]) -> str:
        """Serialize a mapping to JSON."""
        return json.dumps(input_dict)

    def _sign_payload(self, payload, headers):
        cert_value = resolve_env_value(self.auth_data.get(ConfigKey.CERT_VALUE))
        asseert_string = jwt.encode(
            payload,
            cert_value,
            algorithm="RS256",
            headers=headers,
        )
        return asseert_string

    def _generate_jwt_assertion(self) -> str:
        """Create RS256 JWT for AoC JWT-bearer grant."""
        client_id = resolve_env_value(self.auth_data.get(ConfigKey.CLIENT_ID))
        token_url = resolve_env_value(self.auth_data.get(ConfigKey.Token_URL))

        user_email = resolve_env_value(self.auth_data.get("user_email"))
        if not user_email:
            raise ValueError("user_email must be provided (AoC JWT 'sub' claim)")

        now = int(time.time())
        # Match the working test: use longer window (1 hour) and omit iat/jti claims
        payload = {
            "iss": client_id,
            "sub": user_email,
            "aud": token_url,  # base token URL (not org-scoped)
            "nbf": now - 3600,  # Allow 1 hour in the past (matching working test)
            "exp": now + 3600,  # 1 hour expiry (matching working test)
        }
        # logger.debug("Generating JWT assertion for payload=%s", payload)
        jwt_header = {"typ": "JWT", "alg": "RS256"}
        signed_payload = self._sign_payload(payload, jwt_header)

        # Do NOT log the assertion; it's sensitive.
        return signed_payload

    def _extract_org_from_isv_token(self, isv_token: str) -> str | None:
        """
        Extract organization from ISV token's platform_attributes.product_origin_url.

        Args:
            isv_token: ISV JWT access token

        Returns:
            Organization name (subdomain) or None if extraction fails
        """
        try:
            # Decode JWT without signature verification
            claims = decode_jwt_without_verification(isv_token)
            if not claims:
                return None

            # Get platform_attributes
            platform_attrs_str = claims.get("platform_attributes")
            if not platform_attrs_str:
                return None

            # Parse JSON string
            platform_attrs = json.loads(platform_attrs_str)

            # Extract product_origin_url
            origin_url = platform_attrs.get("product_origin_url")
            if not origin_url:
                return None

            # Parse URL and extract subdomain (org)
            parsed = urllib.parse.urlparse(origin_url)
            hostname = parsed.hostname or ""
            org = hostname.split(".")[0] if hostname else None

            if org:
                logger.info("Extracted org '%s' from ISV token", org)

            return org

        except Exception as e:
            logger.debug("Failed to extract org from ISV token: %s", e)
            return None

    async def _refresh_token(self) -> None:
        """Refresh internal bearer token if missing/expired."""
        auth_context = get_auth_context()
        session_id = auth_context.get(AUTH_KEY_AUTH_TOKEN) if auth_context else None
        isv_token = auth_context.get(AUTH_KEY_ISV_TOKEN) if auth_context else None

        if session_id:
            logger.debug(
                "Using platform-session grant type (session_id and ISV token available)"
            )
            await self._refresh_token_platform_session(session_id, isv_token)
        else:
            logger.debug("Using JWT bearer grant type (no session_id in auth context)")
            await self._refresh_token_jwt_bearer()

    async def _refresh_token_platform_session(
        self, session_id: str, isv_token: str | None = None
    ) -> None:
        """
        Refresh token using platform-session grant type with dynamic org extraction.

        Constructs URL: POST /api/v1/oauth2/{org}/token
        Where {org} is extracted from ISV token's platform_attributes.product_origin_url

        Args:
            session_id: Platform session ID for Authorization header
            isv_token: ISV JWT token for org extraction (optional)
        """
        base_token_url = self.auth_data.get(ConfigKey.Token_URL)
        if not base_token_url:
            raise ValueError("token_url must be provided")

        # Extract org using dual-fallback approach
        org = None
        if isv_token:
            org = self._extract_org_from_isv_token(isv_token)

        if not org:
            auth_context = get_auth_context()
            org = auth_context.get(AUTH_KEY_ORG) if auth_context else None

        if not org:
            logger.warning(
                "No org found - ISV token should contain platform_attributes with product_origin_url"
            )

        # Build token URL with dynamic org
        if org:
            import re

            # Try to replace existing org in URL pattern: /oauth2/{org}/token
            if re.search(r"/oauth2/[^/]+/token", base_token_url):
                # URL has org, replace it: /oauth2/abc/token -> /oauth2/testeng/token
                token_url = re.sub(
                    r"/oauth2/[^/]+/token", f"/oauth2/{org}/token", base_token_url
                )
            else:
                # URL doesn't have org, insert it: /oauth2/token -> /oauth2/testeng/token
                token_url = base_token_url.replace(
                    "/oauth2/token", f"/oauth2/{org}/token"
                )
            logger.info("Token URL with dynamic org '%s': %s", org, token_url)
        else:
            # Use configured URL as-is (contains default org or no org)
            token_url = base_token_url
            logger.warning("Using fallback token_url (no org extracted): %s", token_url)

        scope = self.auth_data.get(ConfigKey.SCOPE) or DEFAULT_SCOPE

        headers = {
            "Authorization": f"ibm-platform {session_id}",
            "Content-Type": "application/json",
        }

        body = {
            "grant_type": "urn:ibm:params:oauth:grant-type:platform-session",
            "scope": scope,
        }

        logger.debug("Requesting token with platform-session grant type")
        resp = await super().post(
            token_url,
            json=body,
            headers=headers,
        )

        # Avoid printing tokens in logs; show status only
        resp.raise_for_status()
        token_data = resp.json()
        logger.debug("Token exchange status=%s", resp.status_code)

        access_token = token_data.get("access_token") or token_data.get("token")
        if not access_token:
            raise ValueError(f"No access_token in response: {token_data}")

        self._access_token = access_token
        expires_in = int(token_data.get("expires_in", DEFAULT_TOKEN_EXPIRY))
        self._expires_at = time.time() + expires_in - TOKEN_REFRESH_BUFFER
        logger.debug("Token acquired; expires_in=%s (buffered)", expires_in)

    async def _refresh_token_jwt_bearer(self) -> None:
        """
        Refresh token using JWT bearer grant type (original flow).

        Request format:
        POST /api/v1/oauth2/{org}/token
        Authorization: Basic {client_id:client_secret}
        Content-Type: application/x-www-form-urlencoded
        Body: assertion={jwt}&grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer&scope={scope}
        """
        assertion = self._generate_jwt_assertion()
        scope = self.auth_data.get(ConfigKey.SCOPE) or DEFAULT_SCOPE
        scope = urllib.parse.quote(scope)

        token_url_with_org = self.auth_data.get(ConfigKey.TOKEN_URL_WITH_ORG)
        if not token_url_with_org:
            raise ValueError("token_url_with_org must be provided")

        client_id = resolve_env_value(self.auth_data.get(ConfigKey.CLIENT_ID))
        client_secret = resolve_env_value(self.auth_data.get(ConfigKey.CLIENT_SECRET))
        grant_type = urllib.parse.quote("urn:ietf:params:oauth:grant-type:jwt-bearer")
        assertion_encoded = urllib.parse.quote(assertion)
        parameters = (
            f"assertion={assertion_encoded}&grant_type={grant_type}&scope={scope}"
        )
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        auth = httpx.BasicAuth(client_id, client_secret)
        resp = await super().post(
            token_url_with_org,
            content=parameters.encode("utf-8"),
            headers=headers,
            auth=auth,
        )

        # Avoid printing tokens in logs; show status only
        resp.raise_for_status()
        token_data = resp.json()
        logger.debug("Token exchange status=%s", resp.status_code)

        access_token = token_data.get("access_token") or token_data.get("token")
        if not access_token:
            raise ValueError(f"No access_token in response: {token_data}")

        self._access_token = access_token
        expires_in = int(token_data.get("expires_in", DEFAULT_TOKEN_EXPIRY))
        self._expires_at = time.time() + expires_in - TOKEN_REFRESH_BUFFER
        logger.debug("Token acquired; expires_in=%s (buffered)", expires_in)

    # ----------------- public override -----------------

    async def request(
        self, method: str, url: httpx.URL | str, **kwargs: Any
    ) -> httpx.Response:
        """
        Make an authenticated request, auto-refreshing the token unless we're calling the token URL itself.
        """
        # Cache token URL once to avoid repeated env lookups and any accidental recursion
        if self._resolved_token_url is None and self.auth_data:
            self._resolved_token_url = resolve_env_value(
                self.auth_data.get(ConfigKey.Token_URL)
            )

        url_str = str(url)
        # Check if this is a token exchange request (hardcoded URL or org-scoped pattern)
        is_token_url = ("/oauth2/" in url_str and "/token" in url_str) or (
            self._resolved_token_url
            and url_str.startswith(str(self._resolved_token_url))
        )

        if is_token_url:
            # Direct calls to the token URL shouldn't recurse into refresh
            return await super().request(method, url, **kwargs)

        if not self._access_token or time.time() >= self._expires_at:
            await self._refresh_token()

        # Merge headers safely
        headers = (kwargs.pop("headers", {}) or {}).copy()

        headers = {k: v for k, v in headers.items() if k.lower() != "authorization"}
        headers["Authorization"] = f"Bearer {self._access_token}"
        headers.setdefault("Accept", "application/json")

        # Only set JSON Content-Type if caller didn’t specify and is sending a body
        if "Content-Type" not in headers and any(
            k in kwargs for k in ("data", "json", "files")
        ):
            headers["Content-Type"] = "application/json"

        response = await super().request(method, url, headers=headers, **kwargs)
        return response
