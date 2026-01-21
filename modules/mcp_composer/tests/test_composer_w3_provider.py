import os
import sys
import asyncio
from mcp_composer.core.auth_handler.w3 import W3Provider
from mcp_composer.middleware.tool.tool_filter import ListFilteredTool
from dotenv import load_dotenv

from mcp_composer import MCPComposer

load_dotenv()

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

# ---- W3 Provider Example
###NOTE: set environment variables for W3 provider in .env file to use below code
# Required: OAUTH_CLIENT_ID, OAUTH_CLIENT_SECRET
# Optional: OAUTH_CONFIG_URL, OAUTH_INTROSPECTION_URL, OAUTH_BASE_URL, OAUTH_PROVIDER_SCOPE
client_id = os.getenv("OAUTH_CLIENT_ID", "")
client_secret = os.getenv("OAUTH_CLIENT_SECRET", "")

if not client_id or not client_secret:
    raise ValueError(
        "OAUTH_CLIENT_ID and OAUTH_CLIENT_SECRET must be set in environment variables"
    )

auth = W3Provider(
    client_id=client_id,
    client_secret=client_secret,
    config_url=os.getenv(
        "OAUTH_CONFIG_URL",
        "https://preprod.login.w3.ibm.com/oidc/endpoint/default/.well-known/openid-configuration",
    ),
    introspection_url=os.getenv(
        "OAUTH_INTROSPECTION_URL",
        "https://preprod.login.w3.ibm.com/v1.0/endpoint/default/introspect",
    ),
    base_url=os.getenv("OAUTH_BASE_URL", "http://localhost:9000"),
    required_scopes=(
        os.getenv("OAUTH_PROVIDER_SCOPE", "openid offline_access").split()
        if os.getenv("OAUTH_PROVIDER_SCOPE")
        else ["openid"]
    ),
    redirect_path=os.getenv("OAUTH_REDIRECT_PATH", "/auth/idaas/callback"),
)

gw = MCPComposer("hello-composer", auth=auth)


async def main():
    """Run MCP Composer with W3 OAuth provider.

    Raises:
        ValueError: If required OAuth environment variables are not set.
    """
    gw.add_middleware(ListFilteredTool(gw))
    gw.disable_composer_tool(["member_health"])
    await gw.setup_member_servers()

    await gw.run_http_async(host="localhost", port=9000, log_level="debug")


if __name__ == "__main__":
    asyncio.run(main())
