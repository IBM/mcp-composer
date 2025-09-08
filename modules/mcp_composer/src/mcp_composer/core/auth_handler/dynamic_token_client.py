import time
from typing import Any
import base64
import httpx

from mcp_composer.core.utils import ConfigKey, LoggerFactory, AuthStrategy

logger = LoggerFactory.get_logger()


class DynamicTokenClient(httpx.AsyncClient):
    def __init__(
        self,
        base_url: str,
        auth_data: dict[str, Any] | None = None,
        timeout: float = 10.0,
        **kwargs: Any,
    ) -> None:
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
        if not self.auth_data:
            raise ValueError("Missing auth_data for token refresh.")

        apikey = self.auth_data.get(ConfigKey.APIKEY, None)
        # Expect apikey to be in headers: self.headers["apikey"]
        token_url = self.auth_data.get(ConfigKey.Token_URL)
        auth_genration_method = self.auth_data.get("token_gen_method","")

        if not apikey or not token_url:
            raise ValueError("apikey and token_url must be provided in auth_data.")

        if auth_genration_method == "jwt" and apikey:
            headers = {"Content-Type": "application/json", "Accept": "application/json"}
            data = {ConfigKey.APIKEY: apikey}
            response = await super().post(token_url, headers=headers, json=data)
        elif auth_genration_method == AuthStrategy.BASIC:
            _id = self.auth_data.get("id")
            _secret = self.auth_data.get("secret")
            credentials = f"{_id}:{_secret}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()

            headers = {
                "Accept": "application/json",
                "Authorization": f"Basic {encoded_credentials}"
            }
            response = await super().post(token_url, headers=headers)
        else:
            # IAM-style
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            data = {
                "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
                "apikey": apikey,
            }
            response = await super().post(token_url, headers=headers, data=data)

        response.raise_for_status()

        token_data = response.json()
        self._access_token = token_data.get("access_token") or token_data.get("token")

        expires_in = token_data.get("expires_in", 3600)
        self._expires_at = time.time() + expires_in - 60  # refresh early

    async def request(
        self, method: str, url: httpx.URL | str, **kwargs: Any
    ) -> httpx.Response:
        # Prevent recursion if the token_url is being called
        token_url = self.auth_data.get("token_url") if self.auth_data else None
        if method.upper() == "POST" and str(url).startswith(str(token_url)):
            return await super().request(method, url, **kwargs)
        if not self._access_token or time.time() >= self._expires_at:
            await self._refresh_token()

        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self._access_token}"
        headers.setdefault("Content-Type", "application/json")

        return await super().request(method, url, headers=headers, **kwargs)
