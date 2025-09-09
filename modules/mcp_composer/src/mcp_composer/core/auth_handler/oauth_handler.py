import os
import time
from typing import Optional, Dict, Any

import httpx

from mcp_composer.core.utils.logger import LoggerFactory
from mcp_composer.core.utils import ConfigKey

logger = LoggerFactory.get_logger()


def resolve_env_value(value: Optional[str]) -> str:
    """Resolve a value from environment variable if it starts with 'ENV_', otherwise return as-is.

    Args:
        value: The value to resolve. If it starts with 'ENV_', it will be treated as an environment variable name.

    Returns:
        The resolved value from environment variable or the original value.

    Raises:
        RuntimeError: If the value starts with 'ENV_' but the environment variable is not set.
        RuntimeError: If the value is None.
    """
    if value is None:
        raise RuntimeError("Required configuration value is None")
    if isinstance(value, str) and value.startswith("ENV_"):
        resolved = os.getenv(value)
        if not resolved:
            raise RuntimeError(f"Environment variable '{value}' is not set")
        return resolved
    return value


async def refresh_access_token(
    *,
    client_id: str,
    client_secret: str,
    token_url: str,
    refresh_token: str,
    scope: Optional[str] = None,
    timeout_seconds: float = 30.0,
) -> str:
    """Exchange a refresh token for a new access token.

    Returns the access token string or raises RuntimeError on failure.
    """
    data: Dict[str, Any] = {
        "grant_type": "refresh_token",
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
    }
    if scope:
        data["scope"] = scope

    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        try:
            response = await client.post(token_url, data=data, headers={"Accept": "application/json"})
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("OAuth refresh request failed: %s", exc)
            raise RuntimeError("Failed to refresh OAuth access token") from exc

    token_payload = response.json()
    access_token = token_payload.get("access_token") or token_payload.get("id_token")
    if not access_token:
        logger.error("OAuth refresh response missing access token: %s", token_payload)
        raise RuntimeError("OAuth provider did not return an access token")

    return access_token


async def build_oauth_client(base_url: str, auth_config: Dict[str, Any]) -> httpx.AsyncClient:
    """Build an httpx.AsyncClient authenticated via OAuth using refresh token.

    Supported auth_config keys (both camelCase and snake_case accepted):
      - clientId | client_id
      - clientSecret | client_secret
      - tokenUrl | token_url
      - scope
      - refreshtoke | refresh_token: if value looks like an ENV var key (e.g. "ENV_*"),
        the actual token will be read from that environment variable.
    """
    # Accept both naming styles
    client_id = resolve_env_value(auth_config.get(ConfigKey.CLIENT_ID))
    client_secret = resolve_env_value(auth_config.get(ConfigKey.CLIENT_SECRET))
    token_url = resolve_env_value(auth_config.get(ConfigKey.Token_URL))
    scope = auth_config.get(ConfigKey.SCOPE)

    refresh_token_value = resolve_env_value(auth_config.get(ConfigKey.REFRESH_TOKEN))

    if not all([client_id, client_secret, token_url, refresh_token_value]):
        raise RuntimeError("Missing required OAuth configuration: client_id, client_secret, token_url, refresh_token")

    access_token = await refresh_access_token(
        client_id=client_id,
        client_secret=client_secret,
        token_url=token_url,
        refresh_token=refresh_token_value,
        scope=scope,
    )

    headers = {"Authorization": f"Bearer {access_token}"}
    return httpx.AsyncClient(base_url=base_url, headers=headers)


class OAuthRefreshClient(httpx.AsyncClient):
    def __init__(
        self,
        *,
        base_url: str,
        token_url: str,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        scope: Optional[str] = None,
        timeout: float = 30.0,
        **kwargs: Any,
    ) -> None:
        super().__init__(base_url=base_url, timeout=timeout, **kwargs)
        self._access_token: Optional[str] = None
        self._expires_at: float = 0
        self.token_url = token_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.scope = scope

    async def _ensure_token(self) -> None:
        if not self._access_token or time.time() >= self._expires_at:
            await self._refresh_token()

    async def _refresh_token(self) -> None:
        token = await refresh_access_token(
            client_id=self.client_id,
            client_secret=self.client_secret,
            token_url=self.token_url,
            refresh_token=self.refresh_token,
            scope=self.scope,
        )
        # We don't always get expires_in with refresh flows; default 3600
        self._access_token = token
        self._expires_at = time.time() + 3600 - 60

    async def request(self, method: str, url: httpx.URL | str, **kwargs: Any) -> httpx.Response:
        await self._ensure_token()
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self._access_token}"
        response = await super().request(method, url, headers=headers, **kwargs)
        if response.status_code == 401:
            await self._refresh_token()
            headers["Authorization"] = f"Bearer {self._access_token}"
            response = await super().request(method, url, headers=headers, **kwargs)
        return response


