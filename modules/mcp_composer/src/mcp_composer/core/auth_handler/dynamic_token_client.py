import base64
import time
from typing import Any

import httpx

from mcp_composer.core.auth_handler.oauth_handler import resolve_env_value
from mcp_composer.core.utils import AuthStrategy, ConfigKey, LoggerFactory

logger = LoggerFactory.get_logger()

# Constants
DEFAULT_TOKEN_EXPIRY = 3600  # 1 hour
TOKEN_REFRESH_BUFFER = 60    # Refresh 1 minute early


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
        # Pass everything to parent class
        super().__init__(
            base_url=base_url,
            timeout=timeout,
            headers=self.headers,
            **kwargs,
        )

    # pylint: disable=too-many-locals,too-many-branches,too-many-statements
    async def _refresh_token(self) -> None:
        try:
            if not self.auth_data:
                raise ValueError("Missing auth_data for token refresh.")
            _id = resolve_env_value(self.auth_data.get(ConfigKey.ID))
            _secret = resolve_env_value(self.auth_data.get(ConfigKey.SECRET))
            apikey = resolve_env_value(self.auth_data.get(ConfigKey.APIKEY, None))
            # Expect apikey to be in headers: self.headers["apikey"]
            token_url = self.auth_data.get(ConfigKey.Token_URL)
            auth_generation_method = self.auth_data.get(ConfigKey.TOKEN_GEN_AUTH_METHOD,"")

            if not token_url:
                raise ValueError("token_url must be provided in auth_data.")

            if not apikey and not (_id and _secret):
                raise ValueError("Either apikey or (id and secret) must be provided in auth_data.")

            logger.debug("Refreshing token using method: %s", auth_generation_method)

            if auth_generation_method == "jwt" and apikey:
                headers = {"Content-Type": "application/json", "Accept": "application/json"}
                data = {ConfigKey.APIKEY: apikey}
                response = await super().post(token_url, headers=headers, json=data)
            elif auth_generation_method == AuthStrategy.BASIC:

                credentials = f"{_id}:{_secret}"
                encoded_credentials = base64.b64encode(credentials.encode()).decode()

                headers = {
                    "Accept": "application/json",
                    "Authorization": f"Basic {encoded_credentials}"
                }

                try:
                    auth = httpx.BasicAuth(str(_id), str(_secret))
                    if self.auth_data.get(ConfigKey.TOKEN_GEN_METHOD,"get").lower()=="post":
                        response = await super().post(token_url, headers=headers, auth=auth)
                    else:
                        response = await super().get(token_url, headers=headers, auth=auth)
                except httpx.HTTPError as exc:
                    logger.error("Basic auth request failed: %s", exc)
                    logger.error("Token URL: %s", token_url)
                    masked_secret = (
                        "*" * len(str(_secret)) if _secret else None
                    )
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
            token_data = response.json()

            self._access_token = token_data.get("access_token") or token_data.get("token")

            if self._access_token:
                logger.debug(
                    "Obtained new access token despite %s status: %s",
                    response.status_code,
                    self._access_token,
                )
                expires_in = int(token_data.get("expires_in", DEFAULT_TOKEN_EXPIRY))
                self._expires_at = time.time() + expires_in - TOKEN_REFRESH_BUFFER
                logger.debug(
                    "Token refreshed successfully, expires in %s seconds", expires_in
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
                    self._expires_at = time.time() + expires_in - TOKEN_REFRESH_BUFFER
                    logger.debug(
                        "Token refreshed successfully from error response, expires in %s seconds",
                        expires_in,
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

    async def request(
        self, method: str, url: httpx.URL | str, **kwargs: Any
    ) -> httpx.Response:
        # Prevent recursion if the token_url is being called
        token_url = self.auth_data.get("token_url") if self.auth_data else None
        if token_url and str(url).startswith(str(token_url)):
            logger.debug(
                "Requesting token, skipping token refresh. kwargs=%s", kwargs
            )
            try:
                return await super().request(method, url, **kwargs)
            except httpx.HTTPError as e:
                logger.error("Failed to make token request to %s: %s", url, e)
        if not self._access_token or time.time() >= self._expires_at:
            try:
                await self._refresh_token()
            except (httpx.HTTPError, ValueError, RuntimeError) as e:
                logger.error("Failed to refresh token: %s", e)
                # Clear the expired token to prevent using stale credentials
                self._access_token = None
                self._expires_at = 0
                raise

        # Merge initialization headers with request headers
        headers = self.headers.copy()
        headers.update(kwargs.pop("headers", {}))
        headers["Authorization"] = f"Bearer {self._access_token}"
        headers.setdefault("Content-Type", "application/json")
        logger.debug("Making request to %s with headers: %s and kwargs: %s", url, headers, kwargs)
        return await super().request(method, url, headers=headers, **kwargs)
