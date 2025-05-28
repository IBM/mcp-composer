import pytest
import logging

from mcp_gateway import MCPGateway
from mcp_gateway.store.database import DatabaseInterface


###############################################################################
# Fake Database – implements only what ServerManager uses
###############################################################################
class FakeDatabase(DatabaseInterface):
    def __init__(self):
        self._servers: dict[str, dict] = {}
        self.reset()

    def reset(self):
        self._servers.clear()

    def load_all_servers(self) -> list[dict]:
        return list(self._servers.values())

    def add_server(self, config: dict) -> None:
        self._servers[config["id"]] = config

    def remove_server(self, server_id: str) -> None:
        self._servers.pop(server_id, None)


###############################################################################
# Fixtures
###############################################################################
@pytest.fixture
def fake_db():
    """Provides a fresh fake database for each test"""
    db = FakeDatabase()
    yield db
    db.reset()


@pytest.fixture
def server_config():
    return {
        "id": "test-server",
        "type": "sse",
        "endpoint": "https://mcp-server-fetch.1vgzmntiwjzl.eu-es.codeengine.appdomain.cloud/sse"
    }


###############################################################################
# Tests
###############################################################################
@pytest.mark.asyncio
async def test_gateway_restart_persists_and_restores_server(fake_db, server_config, caplog):
    """
    1. Register a server with config (first run)
    2. Simulate gateway restart (load from fake DB)
    3. Ensure the server and tool are still available
    """
    caplog.set_level(logging.DEBUG)
    logger = logging.getLogger(__name__)

    # -------- First run --------
    gateway_1 = MCPGateway("gateway", config=[server_config], database_config=fake_db)
    await gateway_1.setup_member_servers()
    tools_1 = await gateway_1.get_tools()
    logger.debug("[First run] Tools: %s", tools_1)
    assert any(server_config["id"] in t for t in tools_1), \
        "Server tools not available after registration"

    # -------- Simulate restart --------
    gateway_2 = MCPGateway("gateway", database_config=fake_db)
    await gateway_2.setup_member_servers()
    tools_2 = await gateway_2.get_tools()
    logger.debug("[After restart] Tools: %s", tools_2)
    assert any(server_config["id"] in t for t in tools_2), \
        "Server tool not found after restart"


@pytest.mark.asyncio
async def test_duplicate_registration_skips_duplicate(fake_db, server_config, caplog):
    caplog.set_level(logging.INFO)
    gateway = MCPGateway("gateway", config=[server_config], database_config=fake_db)
    await gateway.setup_member_servers()

    # Register again with same config
    await gateway.setup_member_servers()

    assert len(fake_db._servers) == 1, "Duplicate registration should not add a second entry"
    assert server_config["id"] in fake_db._servers


@pytest.mark.asyncio
async def test_corrupt_entry_does_not_crash_gateway(fake_db):
    # Add corrupt entry directly to the fake database
    fake_db._servers["corrupt-entry"] = {"type": "sse", "endpoint": "http://bad"}

    gateway = MCPGateway("gateway", database_config=fake_db)
    # Should not raise error even though one entry is invalid
    await gateway.setup_member_servers()

    tools = await gateway.get_tools()
    assert isinstance(tools, dict), "Gateway should recover from bad DB entries"


@pytest.mark.asyncio
async def test_empty_database_loads_no_servers(fake_db):
    gateway = MCPGateway("gateway", database_config=fake_db)
    await gateway.setup_member_servers()
    mounted_servers = gateway.list_member_servers()
    assert mounted_servers == [], "Gateway should start cleanly with empty DB"


@pytest.mark.asyncio
async def test_no_database_config_works(fake_db, server_config):
    # Test with no database config
    gateway = MCPGateway("gateway", config=[server_config])
    await gateway.setup_member_servers()
    
    # Should still work but not persist
    tools = await gateway.get_tools()
    assert any(server_config["id"] in t for t in tools)
    
    # Verify nothing was persisted to database
    assert len(fake_db._servers) == 0