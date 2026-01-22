"""Turbo OAuth Handler for JWT-based authentication."""

import asyncio
import time
from typing import Any, Optional

import httpx

from mcp_composer.core.auth_handler.oauth_handler import resolve_env_value
from mcp_composer.core.utils import ConfigKey, LoggerFactory

logger = LoggerFactory.get_logger()

DEFAULT_TOKEN_EXPIRY = 3600
TOKEN_REFRESH_BUFFER = 60
DEFAULT_TIMEOUT = 30.0


class TurboJWTClient(httpx.Auth):
    """Async auth handler for Turbo OAuth client-credentials flow."""

    def __init__(
        self,
        base_url: str,
        auth_data: dict[str, Any] | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        headers: dict[str, str] | None = None,
        **_: Any,
    ) -> None:
        if not base_url:
            raise ValueError("base_url cannot be empty")
        if timeout <= 0:
            raise ValueError("timeout must be positive")

        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.auth_data = auth_data or {}
        self._access_token: Optional[str] = None
        self._expires_at: float = 0.0
        self._refresh_lock = asyncio.Lock()
        self._auth_prefix = self.auth_data.get("auth_prefix", "Bearer")
        self._token_url = self.auth_data.get(ConfigKey.Token_URL) or (
            f"{self.base_url}/oauth2/token"
        )
        self._base_headers = headers or {}
        self._client: Optional[httpx.AsyncClient] = None

    async def _refresh_token(self) -> None:
        """Obtain a new access token using client credentials."""
        client_id = resolve_env_value(self.auth_data.get(ConfigKey.CLIENT_ID))
        client_secret = resolve_env_value(self.auth_data.get(ConfigKey.CLIENT_SECRET))
        scope = self.auth_data.get(ConfigKey.SCOPE)
        if not all([client_id, client_secret, scope]):
            raise ValueError(
                "client_id, client_secret, and scope must be provided for Turbo OAuth"
            )

        data = {
            "grant_type": "client_credentials",
            "scope": scope,
        }

        token_headers = {
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            **{
                k: v
                for k, v in self._base_headers.items()
                if k.lower() != "authorization"
            },
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self._token_url,
                    data=data,
                    auth=httpx.BasicAuth(client_id, client_secret),
                    headers=token_headers,
                )
                response.raise_for_status()

            token_data = response.json()
            logger.debug("Turbo OAuth token exchange status=%s", response.status_code)

            access_token = token_data.get("access_token") or token_data.get("token")
            if not access_token:
                raise ValueError(f"No access_token in response: {token_data}")

            expires_in = max(int(token_data.get("expires_in", DEFAULT_TOKEN_EXPIRY)), 1)
            self._access_token = access_token
            self._expires_at = time.time() + expires_in - TOKEN_REFRESH_BUFFER
            logger.debug(
                "Turbo OAuth token acquired; expires_in=%s (buffered)", expires_in
            )

        except httpx.HTTPError as exc:
            logger.error("Turbo OAuth token request failed: %s", exc)
            raise RuntimeError("Failed to obtain Turbo OAuth access token") from exc

    def _needs_refresh(self) -> bool:
        return not self._access_token or time.time() >= self._expires_at

    async def _ensure_token(self) -> None:
        if not self._needs_refresh():
            return
        async with self._refresh_lock:
            if not self._needs_refresh():
                return
            await self._refresh_token()

    async def ensure_token(self) -> None:
        """Public helper to prefetch a token and surface configuration errors early."""
        await self._ensure_token()

    async def async_auth_flow(self, request: httpx.Request):  # type: ignore[override]
        """httpx auth flow that injects/refreshes the Bearer token."""
        await self._ensure_token()

        request.headers.update(self._base_headers)
        request.headers.pop("Authorization", None)
        request.headers["Authorization"] = f"{self._auth_prefix} {self._access_token}"
        request.headers.setdefault("Accept", "application/json")
        yield request

    async def request(
        self, method: str, url: httpx.URL | str, **kwargs: Any
    ) -> httpx.Response:
        """Convenience wrapper that issues a request using this auth handler."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                auth=self,
                headers=self._base_headers,
            )
        return await self._client.request(method, url, **kwargs)

    async def __aenter__(self) -> "TurboJWTClient":
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            auth=self,
            headers=self._base_headers,
        )
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        if self._client:
            await self._client.aclose()
        self._client = None
