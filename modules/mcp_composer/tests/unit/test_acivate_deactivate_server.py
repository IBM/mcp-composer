from fastmcp.exceptions import ToolError
import pytest

from mcp_composer.core.composer import MCPComposer
from mcp_composer.store.fake_database import FakeDatabase

# pylint: disable=protected-access,redefined-outer-name


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
        "endpoint": "https://mcp-server-fetch.1vgzmntiwjzl.eu-es.codeengine.appdomain.cloud/sse",
    }


@pytest.mark.asyncio
async def test_activate_mcp_server_success(fake_db, server_config):
    server_config["status"] = "deactivated"
    composer = MCPComposer("composer", config=[server_config], database_config=fake_db)
    composer._server_manager.add_server_db(server_config)

    result = await composer.activate_mcp_server(server_config["id"])

    assert f"Server '{server_config['id']}' activated" in result
    reloaded = composer._server_manager.load_all_servers_db()
    assert any(
        s["id"] == server_config["id"] and s["status"] == "active" for s in reloaded
    )


@pytest.mark.asyncio
async def test_activate_mcp_server_invalid_id(fake_db):
    composer = MCPComposer("composer", config=[], database_config=fake_db)

    with pytest.raises(ToolError):
        await composer.activate_mcp_server("invalid-server-id")


@pytest.mark.asyncio
async def test_deactivate_mcp_server_success(fake_db, server_config):
    server_config["status"] = "active"
    composer = MCPComposer("composer", config=[server_config], database_config=fake_db)
    await composer.setup_member_servers()

    # Confirm it's mounted
    assert composer._server_manager.get_member(server_config["id"]) is not None

    # Run deactivation
    result = await composer.deactivate_mcp_server(server_config["id"])
    assert "deactivated" in result

    # Confirm it's unmounted
    assert composer._server_manager.get_member(server_config["id"]) is None

    # Confirm DB updated
    updated = composer._server_manager.load_all_servers_db()
    match = next((s for s in updated if s["id"] == server_config["id"]), None)
    assert match and match["status"] == "deactivated"


@pytest.mark.asyncio
async def test_deactivate_mcp_server_twice(fake_db, server_config):
    server_config["status"] = "active"
    composer = MCPComposer("composer", config=[server_config], database_config=fake_db)
    await composer.setup_member_servers()

    await composer.deactivate_mcp_server(server_config["id"])

    with pytest.raises(ToolError) as excinfo:
        await composer.deactivate_mcp_server(server_config["id"])

    assert "already deactivated" in str(excinfo.value)
