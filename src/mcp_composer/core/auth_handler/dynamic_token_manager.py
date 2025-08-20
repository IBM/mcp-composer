import asyncio
from typing import Any

import httpx

from mcp_composer.core.utils import AuthStrategy, ConfigKey
from mcp_composer.core.utils.logger import LoggerFactory

logger = LoggerFactory.get_logger()
# pylint: disable=W0718


class DynamicTokenManager(httpx.AsyncClient):
    def __init__(
        self,
        *,
        base_url: str,
        timeout: float = 10.0,
        **kwargs: Any,
    ) -> None:
        self.auth_strategy = kwargs.pop(ConfigKey.AUTH_STRATEGY, None)

        if self.auth_strategy == AuthStrategy.JSESSIONID:
            self.login_url = kwargs.pop(ConfigKey.LOGIN_URL, None)
            self.username = kwargs.pop(ConfigKey.USERNAME, None)
            self.password = kwargs.pop(ConfigKey.PASSWORD, None)

        super().__init__(
            base_url=base_url,
            timeout=timeout,
            **kwargs,
        )

    async def get_authenticated_http_client_for_jessonid(
        self,
    ) -> httpx.AsyncClient | None:
        """Get an authenticated HTTP client using JSESSIONID authentication."""
        if self.auth_strategy != AuthStrategy.JSESSIONID:
            return None

        try:
            # Check required login fields early
            if not all([self.login_url, self.username, self.password]):
                logger.warning("Missing login credentials or login URL")
                return None

            async with httpx.AsyncClient(
                base_url=self.base_url,
                follow_redirects=True,
                verify=False,  # Consider setting this to True in production
            ) as temp_client:
                logger.info(
                    "Logging in at: %s with username %s and pwd %s",
                    temp_client.base_url,
                    self.username,
                    self.password,
                )

                response = await temp_client.post(
                    self.login_url,
                    data={
                        ConfigKey.USERNAME: self.username,
                        ConfigKey.PASSWORD: self.password,
                    },
                    timeout=10.0,  # Optional: explicitly set timeout
                )

                response.raise_for_status()  # Raises for HTTP 4xx/5xx

                jsessionid = response.cookies.get(ConfigKey.JSESSIONID)
                logger.info("Received JSESSIONID: %s", jsessionid)

                if not jsessionid:
                    raise ValueError("JSESSIONID not found — login failed.")

                headers = {"Cookie": f"JSESSIONID={jsessionid}"}
                return httpx.AsyncClient(
                    base_url=self.base_url, headers=headers, verify=False
                )

        except httpx.HTTPStatusError as e:
            logger.error(
                "HTTP error during login: %s - %s",
                e.response.status_code,
                e.response.text,
            )
        except httpx.RequestError as e:
            logger.error("Request failed: %s", str(e))
        except asyncio.TimeoutError:
            logger.error("Login request timed out.")
        except ValueError as e:
            # Re-raise ValueError for JSESSIONID not found
            logger.error("Unexpected error: %s", str(e))
            raise
        except Exception as e:
            logger.error("Unexpected error: %s", str(e))

        return None  # Return None if anything failed
