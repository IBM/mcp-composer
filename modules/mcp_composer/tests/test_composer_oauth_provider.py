import os
import sys
import asyncio
from mcp_composer.core.auth_handler.oauth import ServerSettings
from mcp_composer.middleware.tool.tool_filter import ListFilteredTool
from mcp_composer.core.auth_handler.providers import OAuthProviderFactory
from dotenv import load_dotenv

from mcp_composer import MCPComposer

load_dotenv()

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

config_settings = ServerSettings()

# ---- OIDC Provider Example
###NOTE: set environment variables for OIDC provider in .env file to use below code
auth = OAuthProviderFactory(
    config_url=config_settings.config_url,
    introspection_url=config_settings.introspection_url,
    client_id=config_settings.client_id,
    client_secret=config_settings.client_secret,
    base_url=config_settings.base_url,
).get_provider_instance()

# ---- GitHub or Google Provider Example
### NOTE: set environment variables for GitHub or Google provider in .env file to use below code
# auth = OAuthProviderFactory(
#     provider=config_settings.provider,
#     client_id=config_settings.client_id,
#     client_secret=config_settings.client_secret,
#     base_url=config_settings.base_url,
# ).get_provider_instance()

gw = MCPComposer("hello-composer", auth=auth)


async def main():
    """_summary_

    Raises:
        ValueError: _description_
    """
    gw.add_middleware(ListFilteredTool(gw))
    gw.disable_composer_tool(["member_health"])
    await gw.setup_member_servers()

    await gw.run_http_async(host="localhost", port=9000, log_level="debug")


if __name__ == "__main__":
    asyncio.run(main())
