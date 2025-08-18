"""Auth strategy"""

import httpx

from mcp_composer.core.auth_handler.dynamic_token_client import DynamicTokenClient
from mcp_composer.core.auth_handler.dynamic_token_manager import DynamicTokenManager
from mcp_composer.core.utils.logger import LoggerFactory
from mcp_composer.core.utils.validator import AuthStrategy, ConfigKey

logger = LoggerFactory.get_logger()


async def get_client(
    base_url: str, auth_config: dict | None = None
) -> httpx.AsyncClient:
    """Return http client"""
    headers = {}
    auth_strategy = auth_config.get("auth_strategy") if auth_config else None
    auth_values = auth_config.get("auth") if auth_config else {}

    # Ensure auth_values is a dict
    if not isinstance(auth_values, dict):
        auth_values = {}

    if auth_strategy == AuthStrategy.DYNAMIC_BEARER:  # pylint: disable=R1705
        token_url = auth_values.get(ConfigKey.Token_URL)
        api_key = auth_values.get(ConfigKey.APIKEY)
        if not token_url or not api_key:
            raise ValueError(
                "token_url and api_key are required for DYNAMIC_BEARER strategy"
            )

        return DynamicTokenClient(
            base_url=base_url,
            token_url=token_url,
            api_key=api_key,
            media_type=auth_values.get(ConfigKey.MEDIA_TYPE, ""),
        )
    elif auth_strategy == AuthStrategy.BEARER:
        logger.info("Setting up header and client for bearer")
        headers[ConfigKey.AUTH_HEADER.value] = (
            f"Bearer {auth_values.get(ConfigKey.TOKEN)}"
        )
        return httpx.AsyncClient(base_url=base_url, headers=headers)
    elif auth_strategy == AuthStrategy.APITOKEN:
        logger.info("Setting up header and client for apiToken")
        headers[ConfigKey.AUTH_HEADER.value] = (
            f"{auth_values.get(ConfigKey.AUTH_PREFIX)} {auth_values.get(ConfigKey.TOKEN)}"
        )
        logger.info("the headers are updated %s and the url is %s", headers, base_url)
        http_client = httpx.AsyncClient(base_url=base_url, headers=headers)
        # concert
        response = await http_client.get("/core/api/v1/applications/")
        logger.info("APITOKEN: The response is %s", response)
        return http_client
    elif auth_strategy == AuthStrategy.JSESSIONID:
        logger.info("Setting up header and client for jessionid")
        token_manager = DynamicTokenManager(
            base_url=base_url,
            auth_strategy=auth_strategy,
            login_url=auth_values.get(ConfigKey.LOGIN_URL),
            username=auth_values.get(ConfigKey.USERNAME),
            password=auth_values.get(ConfigKey.PASSWORD),
        )

        client = await token_manager.get_authenticated_http_client_for_jessonid()
        if client is None:
            raise RuntimeError("Failed to get authenticated HTTP client for JSESSIONID")
        return client
    elif auth_strategy == AuthStrategy.BASIC:
        logger.info("Setting up header and client for basic")
        username = auth_values.get(ConfigKey.USERNAME)
        password = auth_values.get(ConfigKey.PASSWORD)
        if not username or not password:
            raise ValueError("username and password are required for BASIC strategy")
        return httpx.AsyncClient(
            base_url=base_url,
            auth=httpx.BasicAuth(username, password),
            headers=headers,
            verify=False,
        )
    else:
        logger.info("No auth strategy provided. Using default client.")
        return httpx.AsyncClient(base_url=base_url)
