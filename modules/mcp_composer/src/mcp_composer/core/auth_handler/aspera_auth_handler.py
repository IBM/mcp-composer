import json
import time
from typing import Any, Optional
import urllib.parse
import httpx
import jwt

from mcp_composer.core.auth_handler.oauth_handler import resolve_env_value
from mcp_composer.core.utils import ConfigKey, LoggerFactory

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

        self._access_token: Optional[str] = None
        self._expires_at: float = 0.0
        self.auth_data = auth_data or {}
        self._resolved_token_url: Optional[str] = None

        super().__init__(base_url=base_url, timeout=timeout, headers=headers or {}, **kwargs)

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
            "aud": token_url,   # base token URL (not org-scoped)
            "nbf": now - 3600,  # Allow 1 hour in the past (matching working test)
            "exp": now + 3600,  # 1 hour expiry (matching working test)
        }
        #logger.debug("Generating JWT assertion for payload=%s", payload)
        jwt_header = {
            "typ": "JWT",
            "alg": "RS256"
        }
        signed_payload = self._sign_payload(payload, jwt_header)


        # Do NOT log the assertion; it's sensitive.
        return signed_payload

    async def _refresh_token(self) -> None:
        """Refresh internal bearer token if missing/expired."""
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
        parameters = f"assertion={assertion_encoded}&grant_type={grant_type}&scope={scope}"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}



        auth = httpx.BasicAuth(client_id, client_secret)
        resp = await super().post(token_url_with_org,
            content=parameters.encode('utf-8'), headers=headers, auth=auth)


        # Avoid printing tokens in logs; show status only
        resp.raise_for_status()
        token_data = resp.json()
        logger.debug("Token exchange status=%s", resp.status_code)

        access_token = token_data.get("access_token") or token_data.get("token")
        if not access_token:
            raise ValueError(f"No access_token in response: {token_data}")
        #logger.debug("Access token %s ",access_token)
        self._access_token = access_token
        expires_in = int(token_data.get("expires_in", DEFAULT_TOKEN_EXPIRY))
        self._expires_at = time.time() + expires_in - TOKEN_REFRESH_BUFFER
        logger.debug("Token acquired; expires_in=%s (buffered)", expires_in)

    # ----------------- public override -----------------

    async def request(self, method: str, url: httpx.URL | str, **kwargs: Any) -> httpx.Response:
        """
        Make an authenticated request, auto-refreshing the token unless we're calling the token URL itself.
        """
        # Cache token URL once to avoid repeated env lookups and any accidental recursion
        if self._resolved_token_url is None and self.auth_data:
            self._resolved_token_url = resolve_env_value(self.auth_data.get(ConfigKey.Token_URL))

        url_str = str(url)
        # Check if this is a token exchange request (hardcoded URL or org-scoped pattern)
        is_token_url = ("/oauth2/" in url_str and "/token" in url_str) or (
            self._resolved_token_url and url_str.startswith(str(self._resolved_token_url))
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
        if "Content-Type" not in headers and any(k in kwargs for k in ("data", "json", "files")):
            headers["Content-Type"] = "application/json"

        response = await super().request(method, url, headers=headers, **kwargs)
        return response
