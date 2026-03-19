import base64
import time
from typing import Any

import httpx

from mcp_composer.core.auth_handler.oauth_handler import (
    get_access_token_client_credentials,
    refresh_access_token,
    resolve_env_value,
)
from mcp_composer.core.utils import AuthStrategy, ConfigKey, LoggerFactory

logger = LoggerFactory.get_logger()

# Constants
DEFAULT_TOKEN_EXPIRY = 3600  # 1 hour
TOKEN_REFRESH_BUFFER = 60  # Refresh 1 minute early
MAX_TOKEN_LIFETIME = 90 * 60  # 90 minutes - cap expiry so we refresh by then


class DynamicTokenClientOAuth(httpx.Auth):

    def __init__(self, access_token=None, auth_prefix="Bearer") -> None:
        self._access_token = access_token
        self._auth_prefix = auth_prefix

    def auth_flow(self, request):
        request.headers["Authorization"] = f"{self._auth_prefix} {self._access_token}"
        yield request


class DynamicTokenClient(httpx.AsyncClient):
    def __init__(
        self,
        base_url: str,
        auth_data: dict[str, Any] | None = None,
        timeout: float = 30.0,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> None:
        if not base_url:
            raise ValueError("base_url cannot be empty")
        if timeout <= 0:
            raise ValueError("timeout must be positive")

        self._access_token = None
        self._expires_at = 0
        self.auth_data = auth_data
        self.headers = headers or {}
        self._auth_prefix = (
            auth_data.get("auth_prefix", "Bearer") if auth_data else "Bearer"
        )
        # Pass everything to parent class
        super().__init__(
            base_url=base_url,
            timeout=timeout,
            headers=self.headers,
            **kwargs,
        )

    def _get_header_for_basic_auth(self, _id: str, _secret: str) -> dict[str, str]:
        credentials = f"{_id}:{_secret}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        return {
            "Authorization": f"Basic {encoded_credentials}",
            "Accept": "application/json",
        }

    # pylint: disable=too-many-locals,too-many-branches,too-many-statements
    async def _refresh_token(self) -> None:
        try:
            if not self.auth_data:
                raise ValueError("Missing auth_data for token refresh.")
            token_url = resolve_env_value(self.auth_data.get(ConfigKey.Token_URL))
            if not token_url:
                raise ValueError("token_url must be provided in auth_data.")

            # OAuth: client_id + client_secret (+ optional refresh_token)
            client_id = resolve_env_value(self.auth_data.get(ConfigKey.CLIENT_ID))
            client_secret = resolve_env_value(
                self.auth_data.get(ConfigKey.CLIENT_SECRET)
            )
            refresh_token_value = resolve_env_value(
                self.auth_data.get(ConfigKey.REFRESH_TOKEN)
            )
            if client_id and client_secret:
                if refresh_token_value:
                    logger.debug("Refreshing token using OAuth refresh_token grant")
                    access_token = await refresh_access_token(
                        client_id=client_id,
                        client_secret=client_secret,
                        token_url=token_url,
                        refresh_token=refresh_token_value,
                        scope=self.auth_data.get(ConfigKey.SCOPE),
                    )
                    self._access_token = access_token
                    self._expires_at = (
                        time.time() + DEFAULT_TOKEN_EXPIRY - TOKEN_REFRESH_BUFFER
                    )
                    logger.debug(
                        "Token refreshed via refresh_token, expires in %s seconds",
                        DEFAULT_TOKEN_EXPIRY,
                    )
                else:
                    logger.debug(
                        "Getting token using OAuth client_credentials grant (no refresh_token)"
                    )
                    access_token, expires_in = await get_access_token_client_credentials(
                        client_id=client_id,
                        client_secret=client_secret,
                        token_url=token_url,
                        scope=self.auth_data.get(ConfigKey.SCOPE),
                    )
                    self._access_token = access_token
                    effective = min(expires_in, MAX_TOKEN_LIFETIME)
                    self._expires_at = time.time() + effective - TOKEN_REFRESH_BUFFER
                    logger.debug(
                        "Token via client_credentials, effective expiry %.1f min",
                        effective / 60,
                    )
                return

            _id = resolve_env_value(self.auth_data.get(ConfigKey.ID))
            _secret = resolve_env_value(self.auth_data.get(ConfigKey.SECRET))
            apikey = resolve_env_value(self.auth_data.get(ConfigKey.APIKEY, None))
            scope = self.auth_data.get(ConfigKey.SCOPE, None)
            server = self.auth_data.get(ConfigKey.SERVER, "").lower()
            auth_generation_method = self.auth_data.get(
                ConfigKey.TOKEN_GEN_AUTH_METHOD, ""
            )

            if not apikey and not (_id and _secret):
                raise ValueError(
                    "Either apikey, (id and secret), or (client_id and client_secret) must be provided in auth_data."
                )

            logger.debug("Refreshing token using method: %s", auth_generation_method)

            if auth_generation_method == "jwt" and apikey:
                headers = {
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                }
                data = {ConfigKey.APIKEY: apikey}
                response = await super().post(token_url, headers=headers, json=data)

            elif (
                auth_generation_method.lower() == AuthStrategy.BASIC.lower()
                and server == "turbo"
            ):
                headers = self._get_header_for_basic_auth(_id, _secret)
                headers["Content-Type"] = "application/x-www-form-urlencoded"
                data = {
                    "grant_type": "client_credentials",
                    "scope": scope,
                }
                try:
                    auth = httpx.BasicAuth(str(_id), str(_secret))
                    response = await super().post(
                        token_url, headers=headers, auth=auth, data=data
                    )
                except httpx.HTTPError as exc:
                    logger.error("Turbo Basic auth request failed: %s", exc)
                    logger.error("Token URL: %s", token_url)
                    masked_secret = "*" * len(str(_secret)) if _secret else None
                    logger.error("ID: %s, Secret: %s", _id, masked_secret)
                    raise

            elif auth_generation_method.lower() == AuthStrategy.BASIC.lower():
                headers = self._get_header_for_basic_auth(_id, _secret)
                try:
                    auth = httpx.BasicAuth(str(_id), str(_secret))
                    if (
                        self.auth_data.get(ConfigKey.TOKEN_GEN_METHOD, "get").lower()
                        == "post"
                    ):
                        response = await super().post(
                            token_url, headers=headers, auth=auth
                        )
                    else:
                        response = await super().get(
                            token_url, headers=headers, auth=auth
                        )
                except httpx.HTTPError as exc:
                    logger.error("Basic auth request failed: %s", exc)
                    logger.error("Token URL: %s", token_url)
                    masked_secret = "*" * len(str(_secret)) if _secret else None
                    logger.error("ID: %s, Secret: %s", _id, masked_secret)
                    raise

            else:
                # IAM-style
                headers = {"Content-Type": "application/x-www-form-urlencoded"}
                data = {
                    "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
                    "apikey": apikey,
                }
                response = await super().post(token_url, headers=headers, data=data)

            # Check if we got a valid token even with a 401 status (some APIs do this)
            try:
                token_data = response.json()
            except Exception as json_error:
                logger.error(
                    "Failed to parse token response as JSON. Status: %s, Content-Type: %s, Body: %s",
                    response.status_code,
                    response.headers.get("content-type", "unknown"),
                    response.text[:500] if response.text else "(empty)"
                )
                raise ValueError(
                    f"Token endpoint returned invalid JSON (status {response.status_code}). "
                    f"Content-Type: {response.headers.get('content-type', 'unknown')}. "
                    f"Body preview: {response.text[:200] if response.text else '(empty)'}"
                ) from json_error

            self._access_token = token_data.get("access_token") or token_data.get(
                "token"
            )

            if self._access_token:
                logger.debug(
                    "Obtained new access token despite %s status: %s",
                    response.status_code,
                    self._access_token,
                )
                expires_in = int(token_data.get("expires_in", DEFAULT_TOKEN_EXPIRY))
                effective = min(expires_in, MAX_TOKEN_LIFETIME)
                self._expires_at = time.time() + effective - TOKEN_REFRESH_BUFFER
                logger.debug(
                    "Token refreshed successfully, server expires_in=%ss, effective=%ss (capped at 90 min), %.1f min from now",
                    expires_in,
                    effective,
                    (self._expires_at - time.time()) / 60,
                )
            else:
                # No token received, raise the status error
                response.raise_for_status()

        except httpx.HTTPStatusError as e:
            # Try to extract token from error response (some APIs return tokens even with 401)
            try:
                error_data = e.response.json()
                error_token = error_data.get("access_token") or error_data.get("token")
                if error_token:
                    logger.warning(
                        "Received token despite %s status: %s",
                        e.response.status_code,
                        error_token,
                    )
                    self._access_token = error_token
                    expires_in = int(error_data.get("expires_in", DEFAULT_TOKEN_EXPIRY))
                    effective = min(expires_in, MAX_TOKEN_LIFETIME)
                    self._expires_at = time.time() + effective - TOKEN_REFRESH_BUFFER
                    logger.debug(
                        "Token from error response, effective=%ss (capped at 90 min)",
                        effective,
                    )
                else:
                    logger.error(
                        "HTTP error during token refresh: %s - %s",
                        e.response.status_code,
                        e.response.text,
                    )
                    raise
            except (ValueError, KeyError):
                # Couldn't parse JSON or no token in error response
                logger.error(
                    "HTTP error during token refresh: %s - %s",
                    e.response.status_code,
                    e.response.text,
                )
                raise
        except httpx.RequestError as e:
            logger.error("Request error during token refresh: %s", e)
            raise
        except (ValueError, RuntimeError) as e:
            logger.error("Unexpected error during token refresh: %s", e)
            raise

    async def ensure_token(self) -> None:
        """Ensure the bearer token is present and not expired; refresh if needed.
        Call this before making a request when the client is used outside request()
        (e.g. from make_tool_call) so refresh based on expiry is always checked."""
        now = time.time()
        if not self._access_token or now >= self._expires_at:
            logger.debug(
                "ensure_token: token missing or expired (secs_until_expiry=%.1f), refreshing",
                (self._expires_at - now) if self._expires_at else 0,
            )
            await self._refresh_token()

    async def request(
        self, method: str, url: httpx.URL | str, **kwargs: Any
    ) -> httpx.Response:
        # Prevent recursion if the token_url is being called
        token_url = self.auth_data.get("token_url") if self.auth_data else None
        if token_url and str(url).startswith(str(token_url)):
            logger.debug("Requesting token, skipping token refresh. kwargs=%s", kwargs)
            try:
                return await super().request(method, url, **kwargs)
            except httpx.HTTPError as e:
                # Must re-raise: swallowing here falls through to _refresh_token() and
                # re-enters the same token POST, causing repeated ~timeout loops.
                logger.error(
                    "Failed to make token request to %s: %s: %s",
                    url,
                    type(e).__name__,
                    e or repr(e),
                )
                raise
        now = time.time()
        if not self._access_token or now >= self._expires_at:
            secs_left = (self._expires_at - now) if self._expires_at else 0
            logger.debug(
                "Token refresh check: no_token=%s, expired=%s, secs_until_expiry=%.1f (%.1f min), refreshing",
                not self._access_token,
                now >= self._expires_at,
                secs_left,
                secs_left / 60,
            )
            try:
                await self._refresh_token()
            except (httpx.HTTPError, ValueError, RuntimeError) as e:
                logger.error("Failed to refresh token: %s", e)
                # Clear the expired token to prevent using stale credentials
                self._access_token = None
                self._expires_at = 0
                raise
        else:
            secs_left = self._expires_at - now
            logger.debug(
                "Token still valid, secs_until_expiry=%.1f (%.1f min), using existing token",
                secs_left,
                secs_left / 60,
            )

        # Merge initialization headers with request headers
        headers = self.headers.copy()
        headers.update(kwargs.pop("headers", {}))
        headers["Authorization"] = f"Bearer {self._access_token}"
        headers.setdefault("Content-Type", "application/json")
        logger.debug(
            "Making request to %s with headers: %s and kwargs: %s", url, headers, kwargs
        )
        return await super().request(method, url, headers=headers, **kwargs)
