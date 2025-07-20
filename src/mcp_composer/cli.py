# src/mcp_composer/utils/cli.py

import argparse
import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from typing import List, Dict
from mcp_composer import MCPComposer
from mcp_composer.utils.validator import MemberServerType
from mcp_composer.middleware.tool_filter import ListFilteredTool

load_dotenv()

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
            "command": "mcp-composer",
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
    mcp = MCPComposer("composer",config=config) # type: ignore

    mcp.add_middleware(ListFilteredTool(mcp))

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

    parser.add_argument("--mode", choices=["http", "sse", "stdio"], required=True)
    parser.add_argument("--id", default="mcp-local", help="Unique ID for this MCP instance")
    parser.add_argument("--endpoint",help="endpoint for HTTP or SSE server running remotely")
    parser.add_argument("--config_path", default=default_config_path,
                        help="Path to JSON config for MCP member servers")
    parser.add_argument("--directory", help="Working directory for the uvicorn process (optional)")
    parser.add_argument("--script_path", help="Path to the script to run in 'stdio' mode")
    parser.add_argument("--host", default="0.0.0.0", help="Host for SSE or HTTP server")
    parser.add_argument("--port", type=int, default=9000, help="Port for SSE or HTTP server")
    args = parser.parse_args()

    # Conditional validation for --endpoint
    config = []
    try:
        if args.endpoint or args.script_path:
            config = build_config_from_args(args)
        os.environ["SERVER_CONFIG_FILE_PATH"] = args.config_path or default_config_path
        asyncio.run(run_dynamic_composer(args,config))

    except Exception as e:
        print(f" Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
