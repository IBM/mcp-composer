"""Auth strategy"""

import httpx
from mcp_composer.auth_handler.dynamic_token_client import DynamicTokenClient
from mcp_composer.auth_handler.dynamic_token_manager import DynamicTokenManager
from mcp_composer.utils.logger import LoggerFactory
from mcp_composer.utils.validator import AuthStrategy, ConfigKey

logger = LoggerFactory.get_logger()


async def get_client(base_url: str, auth_config: dict | None = None):
    """Return http client"""
    headers = {}
    auth_strategy = auth_config.get("auth_strategy") if auth_config else None
    auth_values = auth_config.get("auth") if auth_config else {}

    match auth_strategy:
        case AuthStrategy.DYNAMIC_BEARER:
            http_client = DynamicTokenClient(
                base_url=base_url,
                token_url=auth_values.get(ConfigKey.Token_URL),
                api_key=auth_values.get(ConfigKey.APIKEY),
                media_type=auth_values.get(ConfigKey.MEDIA_TYPE, ""),
            )

        case AuthStrategy.BEARER:
            logger.info("Setting up header and client for bearer")
            headers[ConfigKey.AUTH_HEADER.value] = (
                f"Bearer {auth_values.get(ConfigKey.TOKEN)}"
            )
            http_client = httpx.AsyncClient(base_url=base_url, headers=headers)

        case AuthStrategy.APITOKEN:
            logger.info("Setting up header and client for apiToken")
            headers[ConfigKey.AUTH_HEADER.value] = (
                f"{auth_values.get(ConfigKey.AUTH_PREFIX)} {auth_values.get(ConfigKey.TOKEN)}"
            )
            logger.info(
                "the headers are updated %s and the url is %s", headers, base_url
            )
            http_client = httpx.AsyncClient(base_url=base_url, headers=headers)
            # concert
            response = await http_client.get("/core/api/v1/applications/")
            logger.info("APITOKEN: The response is %s", response)

        case AuthStrategy.JSESSIONID:
            logger.info("Setting up header and client for jessionid")
            try:
                token_manager = DynamicTokenManager(
                    base_url=base_url,
                    auth_strategy=auth_strategy,
                    login_url=auth_values.get(ConfigKey.LOGIN_URL),
                    username=auth_values.get(ConfigKey.USERNAME),
                    password=auth_values.get(ConfigKey.PASSWORD),
                )

                http_client = (
                    await token_manager.get_authenticated_http_client_for_jessonid()
                )
            except KeyError as e:
                # Required config missing
                logger.error("Missing configuration key:%s", e)

            except httpx.HTTPError as e:
                # Any HTTP-related error from httpx
                logger.error("HTTP error during authentication: %s", e)

            except Exception as e:
                # Catch-all for unexpected errors
                logger.error("Unexpected error: %s", e)

        case AuthStrategy.BASIC:
            logger.info("Setting up header and client for basic")
            username = auth_values.get(ConfigKey.USERNAME)
            password = auth_values.get(ConfigKey.PASSWORD)
            http_client = httpx.AsyncClient(
                base_url=base_url,
                auth=httpx.BasicAuth(username, password),
                headers=headers,
                verify=False,
            )

        case _:
            logger.info("No auth strategy provided. Using default client.")
            http_client = httpx.AsyncClient(base_url=base_url)

    return http_client  # type: ignore
