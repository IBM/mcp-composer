# src/mcp_composer/utils/cli.py
import argparse
import asyncio
import os
import sys
import secrets
import hashlib
import base64
from pathlib import Path
from dotenv import load_dotenv
from typing import List, Dict, Any
from pydantic import AnyUrl, TypeAdapter
from fastmcp.server.proxy import ProxyClient
from mcp_composer import MCPComposer
from urllib.parse import urlparse, urlunparse
from mcp_composer.auth_handler.oauth import SimpleOAuthProvider, ServerSettings
from mcp_composer.utils.logger import LoggerFactory
from mcp_composer.utils import MemberServerType
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.shared.auth import OAuthClientInformationFull
from mcp.server.auth.provider import (
    AuthorizationParams,
)
import webbrowser
from aiohttp import web
import jwt
load_dotenv()
logger = LoggerFactory.get_logger()




def generate_pkce_pair():
    # Step 1: Generate a secure random code_verifier (43-128 characters)
    code_verifier = secrets.token_urlsafe(64)
    # Step 2: Create the code_challenge (SHA256, base64url, no '=' padding)
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).rstrip(b'=').decode('ascii')
    return code_verifier, code_challenge

# Usage

def sanitize_url(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("Invalid URL")
    return urlunparse(parsed)

async def wait_for_callback(expected_path, listen_port=9000, timeout=120):
    """Runs a local aiohttp server to listen for the callback, returns code and state."""
    result = {}

    async def handle_callback(request):
        params = request.rel_url.query
        result["code"] = params.get("code")
        result["state"] = params.get("state")
        # Simple HTML response for the browser
        return web.Response(text="Authentication complete. You may close this window.")

    app = web.Application()
    app.router.add_get(expected_path, handle_callback)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "localhost", listen_port)
    await site.start()

    # Wait until callback received or timeout
    try:
        for _ in range(timeout * 10):
            await asyncio.sleep(0.1)
            if result:
                break
        else:
            raise TimeoutError("Timed out waiting for OAuth callback.")
    finally:
        await runner.cleanup()

    return result["code"], result["state"]


async def create_mcp_server(settings: ServerSettings) -> MCPComposer:
    logger.info("Creating MCP Composer server with OAuth support...")
    oauth_provider = SimpleOAuthProvider(settings)
    
    redirect_uris = [TypeAdapter(AnyUrl).validate_python(settings.callback_path)]

    client_info = OAuthClientInformationFull( # fill this as per your app requirements
        client_id=settings.client_id,
        client_secret=settings.client_secret,
        redirect_uris=redirect_uris
    )

    code_verifier, code_challenge = generate_pkce_pair()
    params = AuthorizationParams(
        state=None,
        redirect_uri=AnyUrl(settings.callback_path),
        code_challenge=code_challenge,
        redirect_uri_provided_explicitly=True, 
        scopes=settings.scope.split(" ") if settings.scope else []
    )

    auth_url = await oauth_provider.authorize(client_info, params)
    logger.info(f"Generated authorization URL: {auth_url}")
    safe_url = sanitize_url(auth_url)
    webbrowser.open(safe_url)
    print(f"Browser opened with: {safe_url}")
    callback_path = urlparse(settings.callback_path).path
    logger.info(f"Callback path set to: {callback_path}")
    
 # --- HANDLE CALLBACK ---
    parsed = urlparse(callback_path)
    print(f"Parsed callback path: {parsed}")
    listen_port = parsed.port or 9000
    expected_path = parsed.path
    print(f"Listening for callback on {expected_path} at port {listen_port}")


    code, state = await wait_for_callback(expected_path, listen_port)

    print(f"Received OAuth code: {code}, state: {state}")

    # --- Complete the token exchange using the callback code/state ---
    # (You will need an async method for this, e.g., oauth_provider.exchange_token(...))
    token = await oauth_provider.handle_callback(code, state)
    print(f"OAuth token received: {token}")

    # Continue with your app, e.g., configure MCPComposer with token
    gw = MCPComposer("composer", auth=oauth_provider)


    @gw.tool()
    async def get_user_profile() -> dict[str, Any]:
        """
        This tool is just a stub to show you how to access token
        """
        auth_token = get_token().replace("auth_", "")
        payload = jwt.decode(auth_token, options={"verify_signature": False})

        return payload

    def get_token() -> str:
        """Get the token for the authenticated user."""
        access_token = get_access_token()
        if not access_token:
            auth_token = list(oauth_provider.token_mapping.values())[0]

        else:
            auth_token = oauth_provider.token_mapping.get(access_token.token)

        if not auth_token:
            raise ValueError("No auth token found for user")

        return auth_token

    return gw



def build_config_from_args(args) -> List[Dict]:
    """Build configuration dictionary from command line arguments."""

    if args.mode in (MemberServerType.SSE, MemberServerType.HTTP) and args.endpoint:
        config =  {
            "id": args.id,
            "type": args.mode,
            "endpoint": args.endpoint,
            "_id": args.id
        }

    elif args.mode == MemberServerType.STDIO:
        if not args.script_path:
            raise ValueError("--script-path is required for mode 'stdio'")
        config =  {
            "id": args.id,
            "type": MemberServerType.STDIO,
            "command": "uv",
            "args": [
                "--directory",
                args.directory or str(Path(args.script_path).parent),
                "run",
                Path(args.script_path).name
            ],
            "_id": args.id
        }
    else:
        raise ValueError(f"Unsupported mode '{args.mode}'")
    server_configs = [config]
    print(f"Generated config: {server_configs}")
    return server_configs




async def run_dynamic_composer(args, config: list[Dict]) -> None:
    """Run MCP Composer with dynamically constructed configuration."""
    logger.info("Running MCP Composer with dynamic configuration... %s", args.auth_type)
    mcp= None
    if args.auth_type == "oauth":
        logger.info("Detected --auth_type oauth")
        settings = ServerSettings()
        mcp =  await create_mcp_server(settings)
        print(f"Created MCP Composer with OAuth: {mcp.custom_route}")
    else:
        logger.info("Running MCP Composer without OAuth")
        mcp = MCPComposer("composer",config=config) # type: ignore

    if args.sse_url:
        print(f"Converting SSE URL {args.sse_url} to stdio")
        remote_proxy = MCPComposer.as_proxy(
                ProxyClient(args.sse_url),name="local-stdio")
        await mcp.import_server(remote_proxy)


    ##mcp.add_middleware(ListFilteredTool(mcp))

    await mcp.setup_member_servers()
    server_config = config[0] if config else {}
    if args.mode == MemberServerType.STDIO:
        await mcp.run_stdio_async()
    elif args.mode == MemberServerType.SSE:
        await mcp.run_sse_async(host= args.host, port=args.port, log_level="debug", path="/sse")
    elif args.mode == MemberServerType.HTTP:
        await mcp.run_http_async(host=args.host, port=args.port, log_level="debug", path="/mcp")
    else:
        raise ValueError(f"Unknown config type: {server_config['type']}")

def main():
    """Main entry point for the MCP Composer CLI."""
    logger.info("Starting MCP Composer CLI...")
    default_config_path = os.getenv("SERVER_CONFIG_FILE_PATH", "")


    parser = argparse.ArgumentParser(
        description="Run MCP Composer with dynamically constructed config",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
        Examples:
        mcp-composer --mode http --endpoint http://api.example.com
        mcp-composer --mode sse --endpoint http://localhost:8001/sse
        mcp-composer --mode stdio --script-path /path/to/server.py --id mcp-news
        """
            )

    parser.add_argument("--mode", choices=["http", "sse", "stdio"], default="stdio", help="MCP mode to run (http, sse, or stdio)")
    parser.add_argument("--id", default="mcp-local", help="Unique ID for this MCP instance")
    parser.add_argument("--endpoint",help="endpoint for HTTP or SSE server running remotely")
    parser.add_argument("--config_path", default=default_config_path,
                        help="Path to JSON config for MCP member servers")
    parser.add_argument("--directory", help="Working directory for the uvicorn process (optional)")
    parser.add_argument("--script_path", help="Path to the script to run in 'stdio' mode")
    parser.add_argument("--host", default="0.0.0.0", help="Host for SSE or HTTP server")
    parser.add_argument("--port", type=int, default=9000, help="Port for SSE or HTTP server")
    parser.add_argument("--auth_type", help="Optional auth type. If 'oauth', uses test_composer_oauth.create_mcp_server()")
    parser.add_argument("--sse-url", help="Langflow-compatible SSE URL to convert into stdio")

    args = parser.parse_args()

    # Conditional validation for --endpoint
    config = []
    try:
        if args.endpoint or args.script_path:
            config = build_config_from_args(args)
        os.environ["SERVER_CONFIG_FILE_PATH"] = args.config_path or default_config_path
        asyncio.run(run_dynamic_composer(args,config))

    except Exception as e:
        logger.error(f" Error to start MCP: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
