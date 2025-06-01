import pytest
from mcp_gateway import MCPGateway
from mcp_gateway.store.fake_database import FakeDatabase

###############################################################################
# PyTest fixtures
###############################################################################
@pytest.fixture()
def fake_db():
    db = FakeDatabase()
    yield db
    db.reset()


@pytest.fixture()
def server_config():
    return {
        "id": "list-test-server",
        "type": "sse",
        "endpoint": "https://dummy/path/sse",
    }

###############################################################################
# Tests
###############################################################################

@pytest.mark.asyncio
async def test_list_member_servers_empty(fake_db):
    """Gateway should return an empty list when no servers are mounted."""
    gateway = MCPGateway("gateway", database_config=fake_db)
    await gateway.setup_member_servers()

    members = gateway.list_member_servers()
    assert members == [], "Expected no mounted servers on fresh start"


@pytest.mark.asyncio
async def test_list_member_servers_populated(fake_db, server_config):
    """After mounting a server, it must appear in list_member_servers()."""
    gateway = MCPGateway("gateway", config=[server_config], database_config=fake_db)
    await gateway.setup_member_servers()

    members = gateway.list_member_servers()

    # basic shape checks
    assert isinstance(members, list)
    assert all("id" in m and "server_name" in m for m in members), "List items must expose id and server_name"

    # ensure our test server is present exactly once
    hits = [m for m in members if m["id"] == server_config["id"]]
    assert len(hits) == 1, "Mounted server should appear exactly once in list_member_servers()"
