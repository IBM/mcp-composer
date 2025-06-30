import httpx
import os
import asyncio
from mcp_composer.utils.logger import LoggerFactory
from mcp_composer.utils import ConfigKey, AuthStrategy
logger = LoggerFactory.get_logger()

class DynamicTokenManager(httpx.AsyncClient):
    def __init__(
        self,
        *,
        base_url: str,
        timeout: float = 10.0,
        **kwargs,
    ):
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



    async def get_authenticated_http_client_for_jessonid(self):
        try:
            # Check required login fields early
            if not all([self.login_url, self.username, self.password]):
                raise ValueError("Missing login credentials or login URL.")

            async with httpx.AsyncClient(
                base_url=self.base_url,
                follow_redirects=True,
                verify=False  # Consider setting this to True in production
            ) as temp_client:

                logger.info(f"Logging in at: {temp_client.base_url} with username {self.username} and pwd {self.password}")

                response = await temp_client.post(
                    self.login_url,
                    data={
                        ConfigKey.USERNAME: self.username,
                        ConfigKey.PASSWORD: self.password
                    },
                    timeout=10.0  # Optional: explicitly set timeout
                )

                response.raise_for_status()  # Raises for HTTP 4xx/5xx

                jsessionid = response.cookies.get(ConfigKey.JSESSIONID)
                logger.info(f"Received JSESSIONID: {jsessionid}")

                if not jsessionid:
                    raise ValueError("JSESSIONID not found — login failed.")

                headers = {"Cookie": f"JSESSIONID={jsessionid}"}
                return httpx.AsyncClient(base_url=self.base_url, headers=headers, verify=False)

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error during login: {e.response.status_code} - {e.response.text}")
        except httpx.RequestError as e:
            logger.error(f"Request failed: {str(e)}")
        except asyncio.TimeoutError:
            logger.error("Login request timed out.")
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")

        return None  # Return None if anything failed
