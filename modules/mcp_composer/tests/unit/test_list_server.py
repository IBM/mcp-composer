import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_composer.core.composer import MCPComposer
from mcp_composer.store.fake_database import FakeDatabase

# pylint: disable=protected-access,redefined-outer-name


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
    composer = MCPComposer("composer", config=[], database_config=fake_db)

    members = composer._server_manager.list()
    assert members == [], "Expected no mounted servers on fresh start"


@pytest.mark.asyncio
async def test_list_member_servers_populated(fake_db, server_config):
    """After mounting a server, it must appear in list_servers()."""
    # Mock the MCP server to avoid network calls
    mock_server = MagicMock()
    mock_server.list_tools = AsyncMock(return_value=[])

    with patch(
        "mcp_composer.core.member_servers.server_manager.MCPServerBuilder"
    ) as mock_builder:
        mock_builder.return_value.build = AsyncMock(return_value=mock_server)

        composer = MCPComposer(
            "composer", config=[server_config], database_config=fake_db
        )
        await composer.setup_member_servers()

        members = composer._server_manager.list_servers()

        # basic shape checks
        assert isinstance(members, list)
        assert all(
            "id" in m and "server_name" in m and "status" in m for m in members
        ), "List items must expose 'id', 'server_name', and 'status'"

        # ensure our test server is present exactly once
        hits = [m for m in members if m["id"] == server_config["id"]]
        assert (
            len(hits) == 1
        ), "Mounted server should appear exactly once in list_servers()"


@pytest.mark.asyncio
async def test_update_server_config_saves_version(
    fake_db, server_config, tmp_path, monkeypatch
):
    version_file = tmp_path / "config_versions.json"
    monkeypatch.setenv("VERSION_CONFIG_FILE_PATH", str(version_file))

    # Mock the MCP server builder and FastMCP.as_proxy to avoid network calls
    with (
        patch(
            "mcp_composer.core.member_servers.server_manager.MCPServerBuilder"
        ) as mock_builder,
        patch("fastmcp.server.server.FastMCP.as_proxy") as mock_as_proxy,
    ):
        # Create a mock server that can be used by FastMCP.as_proxy()
        mock_server = MagicMock()
        mock_server.list_tools = AsyncMock(return_value=[])

        # Mock the as_proxy method to return a mock proxy
        mock_proxy = MagicMock()
        mock_proxy.list_tools = AsyncMock(return_value=[])
        mock_as_proxy.return_value = mock_proxy

        mock_builder.return_value.build = AsyncMock(return_value=mock_server)

        composer = MCPComposer(database_config=fake_db)

        original_config = {**server_config, "label": "Initial Label", "tags": ["v1"]}
        await composer.register_mcp_server(original_config)

        updated_config = {**server_config, "label": "Updated Label", "tags": ["v2"]}
        await composer.update_mcp_server_config(server_config["id"], updated_config)

        assert version_file.exists()
        with open(version_file, encoding="utf-8") as f:
            history = json.load(f)

        assert server_config["id"] in history
        assert history[server_config["id"]][0]["config"]["label"] == "Initial Label"
        assert "version_id" in history[server_config["id"]][0]


@pytest.mark.asyncio
async def test_multiple_updates_accumulate_versions(
    fake_db, server_config, tmp_path, monkeypatch
):
    version_file = tmp_path / "config_versions.json"
    monkeypatch.setenv("VERSION_CONFIG_FILE_PATH", str(version_file))

    # Mock the MCP server builder and FastMCP.as_proxy to avoid network calls
    with (
        patch(
            "mcp_composer.core.member_servers.server_manager.MCPServerBuilder"
        ) as mock_builder,
        patch("fastmcp.server.server.FastMCP.as_proxy") as mock_as_proxy,
    ):
        # Create a mock server that can be used by FastMCP.as_proxy()
        mock_server = MagicMock()
        mock_server.list_tools = AsyncMock(return_value=[])

        # Mock the as_proxy method to return a mock proxy
        mock_proxy = MagicMock()
        mock_proxy.list_tools = AsyncMock(return_value=[])
        mock_as_proxy.return_value = mock_proxy

        mock_builder.return_value.build = AsyncMock(return_value=mock_server)

        composer = MCPComposer(database_config=fake_db)

        base_config = {**server_config, "label": "Initial Label", "tags": ["v1"]}
        await composer.register_mcp_server(base_config)

        await composer.update_mcp_server_config(
            server_config["id"],
            {**server_config, "label": "Updated Label 1", "tags": ["v2"]},
        )

        await composer.update_mcp_server_config(
            server_config["id"],
            {**server_config, "label": "Updated Label 2", "tags": ["v3"]},
        )

        with open(version_file, encoding="utf-8") as f:
            history = json.load(f)

        versions = history[server_config["id"]]
        assert len(versions) == 2
        assert versions[0]["config"]["label"] == "Initial Label"
        assert versions[1]["config"]["label"] == "Updated Label 1"


@pytest.mark.asyncio
async def test_rollback_restores_previous_version(
    fake_db, server_config, tmp_path, monkeypatch
):
    version_file = tmp_path / "config_versions.json"
    monkeypatch.setenv("VERSION_CONFIG_FILE_PATH", str(version_file))

    # Mock the MCP server builder and FastMCP.as_proxy to avoid network calls
    with (
        patch(
            "mcp_composer.core.member_servers.server_manager.MCPServerBuilder"
        ) as mock_builder,
        patch("fastmcp.server.server.FastMCP.as_proxy") as mock_as_proxy,
    ):
        # Create a mock server that can be used by FastMCP.as_proxy()
        mock_server = MagicMock()
        mock_server.list_tools = AsyncMock(return_value=[])

        # Mock the as_proxy method to return a mock proxy
        mock_proxy = MagicMock()
        mock_proxy.list_tools = AsyncMock(return_value=[])
        mock_as_proxy.return_value = mock_proxy

        mock_builder.return_value.build = AsyncMock(return_value=mock_server)

        composer = MCPComposer(database_config=fake_db)

        await composer.register_mcp_server(
            {**server_config, "label": "Initial Label", "tags": ["v1"]}
        )

        await composer.update_mcp_server_config(
            server_config["id"],
            {**server_config, "label": "Updated Label 1", "tags": ["v2"]},
        )

        await composer.update_mcp_server_config(
            server_config["id"],
            {**server_config, "label": "Updated Label 2", "tags": ["v3"]},
        )

        # Rollback
        versions = composer._server_config_manager.config_manager.get_all_versions(
            server_config["id"]
        )
        rollback_config = composer._server_config_manager.config_manager.rollback(
            server_config["id"], versions[0]["version_id"]
        )

        assert rollback_config["label"] == "Initial Label"
        assert rollback_config["tags"] == ["v1"]

        await composer.update_mcp_server_config(server_config["id"], rollback_config)
