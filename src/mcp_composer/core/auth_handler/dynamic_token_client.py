import time
from typing import Any

import httpx

from mcp_composer.core.utils import ConfigKey, LoggerFactory

logger = LoggerFactory.get_logger()


class DynamicTokenClient(httpx.AsyncClient):
    def __init__(
        self,
        *,
        base_url: str,
        token_url: str,
        api_key: str,
        timeout: float = 10.0,
        media_type: str,
        **kwargs: Any,
    ) -> None:
        self._access_token = None
        self._expires_at = 0
        self.token_url = token_url
        self.apikey = api_key
        self.media_type = media_type

        # Pass everything to parent class
        super().__init__(
            base_url=base_url,
            timeout=timeout,
            **kwargs,
        )

    async def _refresh_token(self) -> None:
        logger.debug("crating access token at %s", self.token_url)
        # Expect apikey to be in headers: self.headers["apikey"]

        if not self.apikey or not self.token_url:
            raise ValueError(
                "Missing 'apikey' or 'token_url' in headers for token refresh."
            )

        if self.media_type == ConfigKey.MEDIA_TYPE_JSON:
            headers = {"Content-Type": "application/json", "Accept": "application/json"}
            data = {"apikey": self.apikey}
            response = await super().post(self.token_url, headers=headers, json=data)
        else:
            # IAM-style
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            data = {
                "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
                "apikey": self.apikey,
            }
            response = await super().post(self.token_url, headers=headers, data=data)

        response.raise_for_status()

        token_data = response.json()
        self._access_token = token_data.get("access_token") or token_data.get("token")

        expires_in = token_data.get("expires_in", 3600)
        self._expires_at = time.time() + expires_in - 60  # refresh early

    async def request(
        self, method: str, url: httpx.URL | str, **kwargs: Any
    ) -> httpx.Response:
        # Prevent recursion if the token_url is being called

        if method.upper() == "POST" and str(url).startswith(str(self.token_url)):
            return await super().request(method, url, **kwargs)
        if not self._access_token or time.time() >= self._expires_at:
            await self._refresh_token()

        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self._access_token}"
        headers.setdefault("Content-Type", "application/json")

        return await super().request(method, url, headers=headers, **kwargs)
