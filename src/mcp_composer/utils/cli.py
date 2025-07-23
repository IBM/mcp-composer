# src/mcp_composer/utils/cli.py
import argparse
import os
from typing import Dict, List
from pathlib import Path
import asyncio
import sys
from dotenv import load_dotenv
from mcp_composer.utils.logger import LoggerFactory
from fastmcp.server.proxy import ProxyClient
from mcp_composer.auth_handler.oauth import ServerSettings
from mcp_composer import MCPComposer
from mcp_composer.utils import MemberServerType
from mcp_composer.utils.oauth_cli_utils import create_mcp_server
load_dotenv()
logger = LoggerFactory.get_logger()



def _setup_args_parser() -> argparse.ArgumentParser:
    """Main entry point for the MCP Composer CLI."""
    logger.info("Starting MCP Composer CLI...")
    
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
    _add_arguments_to_parser(parser)
    return parser


def _add_arguments_to_parser(parser: argparse.ArgumentParser) -> None:
    """Add arguments to the parser."""
    logger.info("Adding arguments...")
    default_config_path = os.getenv("SERVER_CONFIG_FILE_PATH", "")
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
    parser.add_argument(
        "-e",
        "--env",
        nargs=2,
        action="append",
        metavar=("KEY", "VALUE"),
        help=(
            "Environment variables used when spawning the default server. Can be "
            "used multiple times. For named servers, environment is inherited or "
            "passed via --pass-environment."
        ),
        default=[],
    )
    parser.add_argument(
        "--pass-environment",
        action=argparse.BooleanOptionalAction,
        help="Pass through all environment variables when spawning all server processes.",
        default=False,
    )

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



def main() -> None:
    """Main entry point for the MCP Composer CLI."""
    logger.info("Starting MCP Composer CLI...")
    parser = _setup_args_parser()
    args = parser.parse_args()

    base_env: dict[str, str] = {}
    if args.pass_environment or args.env or args.e:
        base_env.update(os.environ)
    config = []
    try:
        if args.endpoint or args.script_path:
            config = build_config_from_args(args)
        os.environ["SERVER_CONFIG_FILE_PATH"] = args.config_path
        asyncio.run(run_dynamic_composer(args,config))

    except Exception as e:
        logger.error(f" Error to start MCP: {e}")
        sys.exit(1)    



if __name__ == "__main__":
    main()
