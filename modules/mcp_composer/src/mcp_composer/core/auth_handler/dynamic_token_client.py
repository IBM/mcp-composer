import time
from typing import Any
import base64
import httpx

from mcp_composer.core.utils import ConfigKey, LoggerFactory, AuthStrategy

logger = LoggerFactory.get_logger()

# Constants
DEFAULT_TOKEN_EXPIRY = 3600  # 1 hour
TOKEN_REFRESH_BUFFER = 60    # Refresh 1 minute early


class DynamicTokenClient(httpx.AsyncClient):
    def __init__(
        self,
        base_url: str,
        auth_data: dict[str, Any] | None = None,
        timeout: float = 10.0,
        **kwargs: Any,
    ) -> None:
        if not base_url:
            raise ValueError("base_url cannot be empty")
        if timeout <= 0:
            raise ValueError("timeout must be positive")

        self._access_token = None
        self._expires_at = 0
        self.auth_data = auth_data

        # Pass everything to parent class
        super().__init__(
            base_url=base_url,
            timeout=timeout,
            **kwargs,
        )

    async def _refresh_token(self) -> None:
        try:
            if not self.auth_data:
                raise ValueError("Missing auth_data for token refresh.")
            _id = self.auth_data.get(ConfigKey.ID)
            _secret = self.auth_data.get(ConfigKey.SECRET)
            apikey = self.auth_data.get(ConfigKey.APIKEY, None)
            # Expect apikey to be in headers: self.headers["apikey"]
            token_url = self.auth_data.get(ConfigKey.Token_URL)
            auth_generation_method = self.auth_data.get(ConfigKey.TOKEN_GEN_AUTH_METHOD,"")

            if not token_url:
                raise ValueError("token_url must be provided in auth_data.")

            if not apikey and not (_id and _secret):
                raise ValueError("Either apikey or (id and secret) must be provided in auth_data.")

            logger.debug(f"Refreshing token using method: {auth_generation_method}")

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
                    if self.auth_data.get(ConfigKey.TOKEN_GEN_AUTH_METHOD,"get").lower()=="post":
                        response = await super().post(token_url, headers=headers, auth=auth)
                    else:
                        response = await super().get(token_url, headers=headers, auth=auth)
                except Exception as e:
                    logger.error(f"Basic auth request failed: {e}")
                    logger.error(f"Token URL: {token_url}")
                    logger.error(f"ID: {_id}, Secret: {'*' * len(str(_secret)) if _secret else None}")
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
                # We got a valid token, even if status was 401 - some APIs return 401 with valid tokens
                logger.debug(f"Obtained new access token despite {response.status_code} status: {self._access_token}")
                expires_in = int(token_data.get("expires_in", DEFAULT_TOKEN_EXPIRY))
                self._expires_at = time.time() + expires_in - TOKEN_REFRESH_BUFFER
                logger.debug(f"Token refreshed successfully, expires in {expires_in} seconds")
            else:
                # No token received, raise the status error
                response.raise_for_status()

        except httpx.HTTPStatusError as e:
            # Try to extract token from error response (some APIs return tokens even with 401)
            try:
                error_data = e.response.json()
                error_token = error_data.get("access_token") or error_data.get("token")
                if error_token:
                    logger.warning(f"Received token despite {e.response.status_code} status: {error_token}")
                    self._access_token = error_token
                    expires_in = int(error_data.get("expires_in", DEFAULT_TOKEN_EXPIRY))
                    self._expires_at = time.time() + expires_in - TOKEN_REFRESH_BUFFER
                    logger.debug(f"Token refreshed successfully from error response, expires in {expires_in} seconds")
                else:
                    logger.error(f"HTTP error during token refresh: {e.response.status_code} - {e.response.text}")
                    raise
            except (ValueError, KeyError):
                # Couldn't parse JSON or no token in error response
                logger.error(f"HTTP error during token refresh: {e.response.status_code} - {e.response.text}")
                raise
        except httpx.RequestError as e:
            logger.error(f"Request error during token refresh: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during token refresh: {e}")
            raise

    async def request(
        self, method: str, url: httpx.URL | str, **kwargs: Any
    ) -> httpx.Response:
        # Prevent recursion if the token_url is being called
        token_url = self.auth_data.get("token_url") if self.auth_data else None
        if (token_url and
            str(url).startswith(str(token_url))):
            logger.debug("Requesting token, skipping token refresh. %s", **kwargs)
            try:
                return await super().request(method, url, **kwargs)
            except Exception as e:
                logger.error(f"Failed to make token request to {url}: {e}")
        if not self._access_token or time.time() >= self._expires_at:
            try:
                await self._refresh_token()
            except Exception as e:
                logger.error(f"Failed to refresh token: {e}")
                # Clear the expired token to prevent using stale credentials
                self._access_token = None
                self._expires_at = 0
                raise

        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self._access_token}"
        headers.setdefault("Content-Type", "application/json")
        logger.debug("Making request to %s with headers: %s and kwargs: %s", url, headers, kwargs)
        return await super().request(method, url, headers=headers, **kwargs)
