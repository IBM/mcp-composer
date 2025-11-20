import os
import re
import time
import uuid
from typing import Any, Optional
import httpx
import jwt
import urllib.parse
import json
from mcp_composer.core.utils import ConfigKey, LoggerFactory
from mcp_composer.core.auth_handler.oauth_handler import resolve_env_value

logger = LoggerFactory.get_logger()

DEFAULT_TOKEN_EXPIRY = 3600
TOKEN_REFRESH_BUFFER = 60
DEFAULT_SCOPE = "user:all"
MAX_ENV_RESOLVE_HOPS = 4  # prevent infinite ENV_* indirection


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
        timeout: float = 10.0,
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

    def _encode_dict_to_json(self, dict):
        return json.dumps(dict)

    def _sign_payload(self, cert_path, payload, headers):
        try:
            with open(cert_path, "r", encoding="utf-8") as f:
                assertion_string = jwt.encode(
                payload,
                f.read(),
                algorithm='RS256',
                headers=headers
                )
            return assertion_string
        except FileNotFoundError:
            raise ValueError(f"Certificate/private key not found: {cert_path}")
        except Exception as e:
            raise ValueError(f"Error reading private key: {e}")



    def _generate_jwt_assertion(self) -> str:
        """Create RS256 JWT for AoC JWT-bearer grant."""
        client_id = resolve_env_value(self.auth_data.get(ConfigKey.CLIENT_ID))
        token_url = resolve_env_value(self.auth_data.get(ConfigKey.Token_URL))
        cert_path = resolve_env_value(self.auth_data.get(ConfigKey.CERT_PATH))

        user_email = resolve_env_value(self.auth_data.get("user_email"))
        if not user_email:
            raise ValueError("user_email must be provided (AoC JWT 'sub' claim)")



        now = int(time.time())
        payload = {
            "iss": client_id,
            "sub": user_email,
            "aud": token_url,   # must EXACTLY match the token endpoint you POST to (base or org-scoped if that's what you use)
            "iat": now,
            "nbf": now - 10,
            "exp": now + 300,   # short TTL
            "jti": str(uuid.uuid4()),
        }

        jwt_header = {
            "typ": "JWT",
            "alg": "RS256"
        }
        signed_payload = self._sign_payload(cert_path, payload, jwt_header)




        # Do NOT log the assertion; it's sensitive.
        return signed_payload



    async def _refresh_token(self) -> None:
        """Refresh internal bearer token if missing/expired."""
        assertion = self._generate_jwt_assertion()



        scope = self.auth_data.get(ConfigKey.SCOPE) or DEFAULT_SCOPE
        scope = urllib.parse.quote(scope)

        token_url_with_org = self.auth_data.get(ConfigKey.TOKEN_URL_WITH_ORG)

        if  not token_url_with_org:
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

        self._access_token = access_token
        expires_in = int(token_data.get("expires_in", DEFAULT_TOKEN_EXPIRY))
        self._expires_at = time.time() + expires_in - TOKEN_REFRESH_BUFFER
        logger.debug("Token acquired; expires_in=%s (buffered)", expires_in)

    # ----------------- public override -----------------

    async def request(self, method: str, url: httpx.URL | str, **kwargs: Any) -> httpx.Response:
        """
        Make an authenticated request, auto-refreshing the token unless we're calling the token URL itself.
        """
        logger.info("Preparing %s request to %s", method, url)
        # Cache token URL once to avoid repeated env lookups and any accidental recursion
        if self._resolved_token_url is None and self.auth_data:
            self._resolved_token_url = resolve_env_value(self.auth_data.get(ConfigKey.Token_URL))

        url_str = str(url)
        # Check if this is a token exchange request (hardcoded URL or org-scoped pattern)
        is_token_url = (
            "/oauth2/" in url_str and "/token" in url_str
        ) or (
            self._resolved_token_url and url_str.startswith(str(self._resolved_token_url))
        )

        if is_token_url:
            # Direct calls to the token URL shouldn't recurse into refresh
            return await super().request(method, url, **kwargs)

        if not self._access_token or time.time() >= self._expires_at:
            await self._refresh_token()

        # Merge headers safely
        headers = (kwargs.pop("headers", {}) or {}).copy()
        headers["Authorization"] = f"Bearer {self._access_token}"
        headers.setdefault("Accept", "application/json")

        # Only set JSON Content-Type if caller didn’t specify and is sending a body
        if "Content-Type" not in headers and any(k in kwargs for k in ("data", "json", "files")):
            headers["Content-Type"] = "application/json"

        return await super().request(method, url, headers=headers, **kwargs)
