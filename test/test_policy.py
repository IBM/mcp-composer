import os
import sys
import asyncio
from mcp_composer import MCPComposer
from mcp_composer.middleware.acl.policy import PolicyMiddleware
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))


mcp = MCPComposer("hello-composer")


@mcp.tool()
def start_cluster(cluster_id: str):
    return f"Started cluster {cluster_id}"


@mcp.tool()
def terminate_cluster(cluster_id: str):
    return f"Terminated cluster {cluster_id}"


@mcp.tool()
def generate_report(report_type: str):
    return f"Generated {report_type} report"

@mcp.tool()
def check_status(service: str):
    return f"Status of {service}: OK"


@mcp.tool()
def read_user_data(user_id: str):
    return f"Reading data for user {user_id}"
async def main():
    """_summary_

    Raises:
        ValueError: _description_
    """
    mode = os.getenv("MCP_MODE", "http").lower()
    policy_engine = os.getenv("POLICY_ENGINE", "vault").lower()
    
    if policy_engine == "vault":
        mcp.add_middleware(PolicyMiddleware(mode="vault",policy_config={
                                        "vault_url": "http://127.0.0.1:8200",
                                        "vault_token": "root"
                                    }))
    elif policy_engine == "opa":
        mcp.add_middleware(PolicyMiddleware(mode="opa", policy_config={
                                            "opa_url":"http://localhost:8181/v1/data/mcp/allow"}))


    await mcp.setup_member_servers()

    if mode == "http":
        await mcp.run_http_async(
            host="0.0.0.0", port=9000, log_level="debug", path="/mcp"
        )
    elif mode == "stdio":
        await mcp.run_stdio_async()
    elif mode == "sse":
        await mcp.run_sse_async(host="0.0.0.0", port=9000, log_level="debug")    
    else:
        raise ValueError(f"Unsupported MCP_MODE: {mode}")


if __name__ == "__main__":
    asyncio.run(main())
