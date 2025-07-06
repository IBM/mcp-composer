import pytest
from mcp_composer import MCPComposer
from mcp_composer.store.fake_database import FakeDatabase
from mcp_composer.member_servers.member_server import MemberMCPServer


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
        "endpoint": "https://mcp-server-fetch.1vgzmntiwjzl.eu-es.codeengine.appdomain.cloud/sse",
    }


###############################################################################
# Tests
###############################################################################


@pytest.mark.asyncio
async def test_list_member_servers_empty(fake_db):
    """Composer should return an empty list when no servers are mounted."""
    composer = MCPComposer("composer", database_config=fake_db)
    await composer.setup_member_servers()

    members = composer._server_manager.list_member_servers()
    assert members == [], "Expected no mounted servers on fresh start"


@pytest.mark.asyncio
async def test_list_member_servers_populated(fake_db, server_config):
    """After mounting a server, it must appear in list_member_servers()."""
    composer = MCPComposer("composer", config=[server_config], database_config=fake_db)
    await composer.setup_member_servers()

    members = composer._server_manager.list_member_servers()

    # basic shape checks
    assert isinstance(members, list)
    assert all("id" in m and "server_name" in m and "status" in m for m in members), (
    "List items must expose 'id', 'server_name', and 'status'"
    )

    # ensure our test server is present exactly once
    hits = [m for m in members if m["id"] == server_config["id"]]
    assert len(hits) == 1, (
        "Mounted server should appear exactly once in list_member_servers()"
    )

@pytest.mark.asyncio
async def test_update_server_config_successfully(fake_db, server_config):
    # Setup
    composer = MCPComposer(database_config=fake_db)

    # Register original config
    original_config = {
        **server_config,  # Use Python unpacking
        "label": "Initial Label",
        "tags": ["v1"]
    }
    await composer.register_mcp_server(original_config)

    # Update config
    updated_config = {
        **server_config,
        "label": "Updated Label",
        "tags": ["v2", "v3"]
    }

    result = await composer.update_mcp_server_config("list-test-server", updated_config)

    assert "successfully" in result

    member: MemberMCPServer | None = composer._server_manager.get_member("list-test-server")
    assert member.config["label"] == "Updated Label"
    assert "v2" in member.config["tags"]
    assert "v3" in member.config["tags"]
