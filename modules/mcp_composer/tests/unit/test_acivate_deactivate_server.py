from unittest.mock import AsyncMock, MagicMock, patch

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
    """Mock server configuration for testing without live endpoints"""
    return {
        "id": "test-server",
        "type": "http",
        "endpoint": "http://127.0.0.1:9999/mcp",
    }


@pytest.mark.asyncio
async def test_activate_mcp_server_success(fake_db, server_config):
    """Test activating a deactivated server"""
    server_config["status"] = "deactivated"
    composer = MCPComposer("composer", config=[server_config], database_config=fake_db)
    composer._server_manager.add_server_db(server_config)

    # Mock the _mount_and_register_server method to avoid actual server connection
    with patch.object(
        composer._server_manager,
        "_mount_and_register_server",
        new=AsyncMock(return_value="Server 'test-server' mounted successfully."),
    ):
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
    """Test deactivating an active server"""
    server_config["status"] = "active"

    # Mock the server builder to avoid actual server connection
    with patch(
        "mcp_composer.core.member_servers.server_manager.MCPServerBuilder"
    ) as mock_builder_class:
        mock_server = AsyncMock()
        mock_server.get_tools = AsyncMock(return_value={})

        mock_builder = MagicMock()
        mock_builder.build = AsyncMock(return_value=mock_server)
        mock_builder_class.return_value = mock_builder

        composer = MCPComposer(
            "composer", config=[server_config], database_config=fake_db
        )
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
    """Test that deactivating a server twice raises an error"""
    server_config["status"] = "active"

    # Mock the server builder to avoid actual server connection
    with patch(
        "mcp_composer.core.member_servers.server_manager.MCPServerBuilder"
    ) as mock_builder_class:
        mock_server = AsyncMock()
        mock_server.get_tools = AsyncMock(return_value={})

        mock_builder = MagicMock()
        mock_builder.build = AsyncMock(return_value=mock_server)
        mock_builder_class.return_value = mock_builder

        composer = MCPComposer(
            "composer", config=[server_config], database_config=fake_db
        )
        await composer.setup_member_servers()

        await composer.deactivate_mcp_server(server_config["id"])

        with pytest.raises(ToolError) as excinfo:
            await composer.deactivate_mcp_server(server_config["id"])

        assert "already deactivated" in str(excinfo.value)
