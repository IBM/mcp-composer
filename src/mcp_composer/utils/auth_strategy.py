import base64
import httpx
from mcp_composer.auth_handler.dynamicTokenClient import DynamicTokenClient
from mcp_composer.auth_handler.dynamic_token_manager import DynamicTokenManager
from mcp_composer.utils.logger import LoggerFactory
from mcp_composer.utils.validator import AuthStrategy, ConfigKey

logger = LoggerFactory.get_logger()


async def get_client(base_url: str, auth_config: dict | None = None):
    headers = {}
    if auth_config:
        auth_strategy = auth_config["auth_strategy"]
        auth_values = auth_config["auth"]
    else:
        auth_strategy = None
        auth_values = None

    match auth_strategy:
        case AuthStrategy.DYNAMIC_BEARER:
            http_client = DynamicTokenClient(
                base_url=base_url,
                token_url=auth_values.get(ConfigKey.Token_URL),
                api_key=auth_values.get(ConfigKey.APIKEY),
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
            logger.info(f"the headers are updated {headers} and the url is {base_url}")
            http_client = httpx.AsyncClient(base_url=base_url, headers=headers)
            # concert
            response = await http_client.get("/core/api/v1/applications/")
            logger.info(f"APITOKEN: The response is {response}")

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
                logger.error(f"Missing configuration key: {e}")

            except httpx.HTTPError as e:
                # Any HTTP-related error from httpx
                logger.error(f"HTTP error during authentication: {e}")

            except Exception as e:
                # Catch-all for unexpected errors
                logger.error(f"Unexpected error: {e}")

        case AuthStrategy.BASIC:
            logger.info("Setting up header and client for basic")
            basic_auth = f"{auth_values[ConfigKey.AUTH][ConfigKey.USERNAME]}:{
                auth_values[ConfigKey.AUTH][ConfigKey.PASSWORD]
            }"
            headers[ConfigKey.AUTH_HEADER] = (
                f"Basic {base64.b64encode(basic_auth.encode('utf-8')).decode('ascii')}"
            )
            http_client = httpx.AsyncClient(
                base_url=base_url,
                headers=headers,
                verify=False,
            )

        case _:
            # Default/fallback client
            logger.info("No AuthStrategy is found, retrun Default/fallback client")
            http_client = httpx.AsyncClient(base_url=base_url)

    return http_client  # type: ignore
