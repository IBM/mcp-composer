import pytest
import logging
from mcp_gateway.utils import ValidationError
from mcp_gateway import MCPGateway
from fastmcp import Client

@pytest.mark.asyncio
async def test_gateway_restart_persists_and_restores_server(caplog):
    """
    Test:
    1. Register a server with config (first run)
    2. Simulate gateway restart (load from DB)
    3. Ensure the server and tool are still available
    """
    caplog.set_level(logging.DEBUG)
    logger = logging.getLogger(__name__)
    server_id = "mcp-server-fetch"
    config = [{
        "id": server_id,
        "type": "sse",
        "endpoint": "https://your.real.endpoint/sse"  # Replace with working endpoint
    }]

    # -------- First run: Register the server and mount it --------
    gateway_1 = MCPGateway("gateway", config=config)
    await gateway_1.setup_member_servers()
    tools_1 = await gateway_1.get_tools()
    logger.debug(f"[First run] Tools: {tools_1}")
    assert any("mcp-server-fetch" in t for t in tools_1.keys()), \
        "Server tools not available after registration"

    # -------- Simulate restart: Load from DB only --------
    gateway_2 = MCPGateway("gateway")
    await gateway_2.setup_member_servers()

    tools_2 = await gateway_2.get_tools()
    logger.debug(f"[After restart] Tools: {tools_2}")
    assert any("mcp-server-fetch" in name for name in tools_2.keys()), "Server tool not found after restart"
    # -------- Cleanup: remove the server --------
    await gateway_2.remove_mcp_server(server_id)
    logger.debug(f"[Cleanup] Removed server: {server_id}")

    # Optional: Verify removal
    tools_post_cleanup = await gateway_2.get_tools()
    assert not any(server_id in name for name in tools_post_cleanup.keys()), "Server was not removed during cleanup"
