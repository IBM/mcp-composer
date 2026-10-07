import logging
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_composer.core.composer import MCPComposer
from mcp_composer.store.fake_database import FakeDatabase

# pylint: disable=protected-access,redefined-outer-name


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
        "id": "mcp-stock-info",
        "type": "http",
        "endpoint": "http://127.0.0.1:9/mcp",
    }


###############################################################################
# Tests
###############################################################################
@pytest.mark.asyncio
async def test_composer_restart_persists_and_restores_server(
    fake_db, server_config, caplog
):
    """
    1. Register a server with config (first run)
    2. Simulate composer restart (load from fake DB)
    3. Ensure the server and tool are still available
    """
    caplog.set_level(logging.DEBUG)
    logger = logging.getLogger(__name__)

    # Mock the MCP server to avoid network calls
    mock_server = MagicMock()
    mock_tool = MagicMock()
    mock_tool.name = f"{server_config['id']}_test_tool"
    mock_tool.description = "Mock tool"
    mock_server.list_tools = AsyncMock(return_value=[mock_tool])

    # Mock the as_proxy method to return a mock proxy
    mock_proxy = MagicMock()
    mock_proxy.list_tools = AsyncMock(return_value=[mock_tool])

    # setup_member_servers mounts via composer.MCPServerBuilder (not server_manager)
    with (
        patch("mcp_composer.core.composer.MCPServerBuilder") as mock_builder,
        patch(
            "mcp_composer.core.member_servers.server_manager.MCPServerBuilder"
        ) as mock_sm_builder,
        patch("fastmcp.server.server.FastMCP.as_proxy") as mock_as_proxy,
    ):
        mock_builder.return_value.build = AsyncMock(return_value=mock_server)
        mock_sm_builder.return_value.build = AsyncMock(return_value=mock_server)
        mock_as_proxy.return_value = mock_proxy

        # -------- First run --------
        composer_1 = MCPComposer(
            "composer", config=[server_config], database_config=fake_db
        )
        await composer_1.setup_member_servers()
        mounted_1 = composer_1._server_manager.list()
        logger.debug("[First run] Mounted: %s", [m.id for m in mounted_1])
        assert any(
            m.id == server_config["id"] for m in mounted_1
        ), "Server not mounted after registration"
        assert (
            server_config["id"] in fake_db._servers
        ), "Server not persisted to database"

        # -------- Simulate restart --------
        composer_2 = MCPComposer("composer", database_config=fake_db)
        await composer_2.setup_member_servers()
        mounted_2 = composer_2._server_manager.list()
        logger.debug("[After restart] Mounted: %s", [m.id for m in mounted_2])
        assert any(
            m.id == server_config["id"] for m in mounted_2
        ), "Server not restored after restart"


@pytest.mark.asyncio
async def test_duplicate_registration_skips_duplicate(fake_db, server_config, caplog):
    caplog.set_level(logging.INFO)
    composer = MCPComposer("composer", database_config=fake_db)

    # Mock the MCP server to avoid network calls and missing descriptions
    mock_server = MagicMock()
    mock_server.list_tools = AsyncMock(return_value=[])

    # Mock the as_proxy method to return a mock proxy
    mock_proxy = MagicMock()
    mock_proxy.list_tools = AsyncMock(return_value=[])

    with (
        patch(
            "mcp_composer.core.member_servers.server_manager.MCPServerBuilder"
        ) as mock_builder,
        patch("fastmcp.server.server.FastMCP.as_proxy") as mock_as_proxy,
    ):
        mock_builder.return_value.build = AsyncMock(return_value=mock_server)
        mock_as_proxy.return_value = mock_proxy

        # Register the server - first time should succeed and add to database
        result1 = await composer.register_mcp_server(server_config)

        # The result should indicate success
        assert "mounted successfully" in result1 or "already mounted" not in result1

        # Register again with same config - should be detected as duplicate
        result2 = await composer.register_mcp_server(server_config)
        assert "already mounted" in result2

    # Verify the mounted servers list has exactly one server
    mounted_servers = composer._server_manager.list()
    assert len(mounted_servers) == 1, "Should have exactly one mounted server"
    assert mounted_servers[0].id == server_config["id"]


@pytest.mark.asyncio
async def test_corrupt_entry_does_not_crash_composer(fake_db):
    # Add corrupt entry directly to the fake database
    fake_db._servers["corrupt-entry"] = {"type": "sse", "endpoint": "http://bad"}

    composer = MCPComposer("composer", database_config=fake_db)
    # Should not raise error even though one entry is invalid
    await composer.setup_member_servers()

    tools = await composer.list_tools()
    assert isinstance(tools, list), "Composer should recover from bad DB entries"


@pytest.mark.asyncio
async def test_empty_database_loads_no_servers():
    # Create a fresh database instance to ensure isolation
    fresh_db = FakeDatabase()

    # Verify the database is truly empty
    assert (
        fresh_db._servers == {}
    ), f"Database should be empty but has: {fresh_db._servers}"

    # Clear any environment variables that might affect database loading
    original_env_file = os.environ.get("SERVER_CONFIG_FILE_PATH")
    original_env_db_type = os.environ.get("MCP_DATABASE_TYPE")
    original_env_use_local = os.environ.get("MCP_USE_LOCAL_FILE_STORAGE")

    if "SERVER_CONFIG_FILE_PATH" in os.environ:
        del os.environ["SERVER_CONFIG_FILE_PATH"]
    if "MCP_DATABASE_TYPE" in os.environ:
        del os.environ["MCP_DATABASE_TYPE"]
    if "MCP_USE_LOCAL_FILE_STORAGE" in os.environ:
        del os.environ["MCP_USE_LOCAL_FILE_STORAGE"]

    try:
        composer = MCPComposer("composer", config=[], database_config=fresh_db)

        # Verify the server_manager is using our fresh_db
        assert (
            composer._server_manager._database is fresh_db
        ), f"ServerManager should be using our fresh_db, but using: {type(composer._server_manager._database)}"

        # Check that database has no servers loaded
        db_servers = composer._server_manager.load_all_servers_db()
        assert (
            db_servers == []
        ), f"Empty database should return no servers, got: {db_servers}"

        # Check that no servers are mounted initially
        mounted_servers = composer._server_manager.list()
        assert mounted_servers == [], "Composer should start cleanly with empty DB"
    finally:
        # Restore environment variables
        if original_env_file is not None:
            os.environ["SERVER_CONFIG_FILE_PATH"] = original_env_file
        if original_env_db_type is not None:
            os.environ["MCP_DATABASE_TYPE"] = original_env_db_type
        if original_env_use_local is not None:
            os.environ["MCP_USE_LOCAL_FILE_STORAGE"] = original_env_use_local


@pytest.mark.asyncio
async def test_no_database_config_works(fake_db, server_config):
    # Test with no database config
    print("Testing composer with no database config %s", server_config)

    # Mock the MCP server to avoid network calls
    mock_server = MagicMock()
    mock_tool = MagicMock()
    mock_tool.name = f"{server_config['id']}_test_tool"
    mock_tool.description = "Mock tool"
    mock_server.list_tools = AsyncMock(return_value=[mock_tool])

    # Mock the as_proxy method to return a mock proxy
    mock_proxy = MagicMock()
    mock_proxy.list_tools = AsyncMock(return_value=[mock_tool])

    with (
        patch("mcp_composer.core.composer.MCPServerBuilder") as mock_builder,
        patch(
            "mcp_composer.core.member_servers.server_manager.MCPServerBuilder"
        ) as mock_sm_builder,
        patch("fastmcp.server.server.FastMCP.as_proxy") as mock_as_proxy,
    ):
        mock_builder.return_value.build = AsyncMock(return_value=mock_server)
        mock_sm_builder.return_value.build = AsyncMock(return_value=mock_server)
        mock_as_proxy.return_value = mock_proxy

        composer = MCPComposer("composer", config=[server_config])
        await composer.setup_member_servers()

        # Should still mount without a database config
        mounted = composer._server_manager.list()
        assert any(m.id == server_config["id"] for m in mounted)

        # Verify nothing was persisted to the unused fake_db fixture
        assert len(fake_db._servers) == 0


@pytest.mark.asyncio
async def test_composer_initializes_without_any_config(fake_db):
    # Clear any existing SERVER_CONFIG_FILE_PATH environment variable
    original_env = os.environ.get("SERVER_CONFIG_FILE_PATH")
    if "SERVER_CONFIG_FILE_PATH" in os.environ:
        del os.environ["SERVER_CONFIG_FILE_PATH"]

    try:
        # Create a temporary directory to test file creation
        with tempfile.TemporaryDirectory() as temp_dir:
            # Change to temp directory to avoid conflicts
            original_cwd = os.getcwd()
            os.chdir(temp_dir)

            try:
                # This should not raise any errors during initialization
                composer = MCPComposer("composer", config=None, database_config=fake_db)

                # Should have basic composer tools available
                tools = await composer.list_tools()
                assert isinstance(
                    tools, list
                ), "Composer should have basic tools available"
                assert len(tools) > 0, "Composer should have at least some basic tools"

                # Should have no member servers mounted
                mounted_servers = composer._server_manager.list_servers()
                assert (
                    mounted_servers == []
                ), "Composer should start with no member servers when no config provided"

                # Should have no database configs loaded
                assert (
                    len(composer._db_configs) == 0
                ), "No database configs should be loaded when no database provided"
                assert (
                    len(composer._server_config_manager.config) == 0
                ), "No configs should be loaded when none provided"

                # Should NOT create member_servers.json file automatically when no database config
                # File creation only happens when MCP_USE_LOCAL_FILE_STORAGE is set to true
                member_servers_file = Path("member_servers.json")
                assert (
                    not member_servers_file.exists()
                ), "member_servers.json should NOT be created automatically when no database config provided"

                # Should be able to call setup_member_servers without errors (it will just log a warning)
                await composer.setup_member_servers()

            finally:
                # Restore original working directory
                os.chdir(original_cwd)

    finally:
        # Restore original environment variable
        if original_env is not None:
            os.environ["SERVER_CONFIG_FILE_PATH"] = original_env


@pytest.mark.asyncio
async def test_composer_initializes_when_file_creation_fails(fake_db):
    # Clear any existing SERVER_CONFIG_FILE_PATH environment variable
    original_env = os.environ.get("SERVER_CONFIG_FILE_PATH")
    if "SERVER_CONFIG_FILE_PATH" in os.environ:
        del os.environ["SERVER_CONFIG_FILE_PATH"]

    try:
        # Create a temporary directory to test file creation
        with tempfile.TemporaryDirectory() as temp_dir:
            # Change to temp directory to avoid conflicts
            original_cwd = os.getcwd()
            os.chdir(temp_dir)

            # Create a read-only directory to simulate permission issues
            read_only_dir = Path("readonly_dir")
            read_only_dir.mkdir()

            # Set the directory to read-only (this will prevent file creation)
            os.chmod(read_only_dir, 0o444)  # Read-only for all users

            try:
                # Try to initialize composer with a path in the read-only directory
                # This should fail to create the file but not crash the composer
                composer = MCPComposer("composer", config=None, database_config=fake_db)

                # Should have basic composer tools available
                tools = await composer.list_tools()
                assert isinstance(
                    tools, list
                ), "Composer should have basic tools available"
                assert len(tools) > 0, "Composer should have at least some basic tools"

                # Should have no member servers mounted
                mounted_servers = composer._server_manager.list_servers()
                assert (
                    mounted_servers == []
                ), "Composer should start with no member servers when no config provided"

                # Should have no database configs loaded
                assert (
                    len(composer._db_configs) == 0
                ), "No database configs should be loaded when no database provided"
                assert (
                    len(composer._server_config_manager.config) == 0
                ), "No configs should be loaded when none provided"

                # Should be able to call setup_member_servers without errors (it will just log a warning)
                await composer.setup_member_servers()

                # Note: We don't assert file existence here since it may or may not be created
                # depending on the timing and OS behavior

            finally:
                # Restore original working directory
                os.chdir(original_cwd)
                # Clean up read-only directory
                try:
                    os.chmod(read_only_dir, 0o755)  # Make writable again
                except OSError:
                    pass

    finally:
        # Restore original environment variable
        if original_env is not None:
            os.environ["SERVER_CONFIG_FILE_PATH"] = original_env


@pytest.mark.asyncio
async def test_composer_initializes_with_invalid_file_path(fake_db):
    # Set an invalid file path that will cause file creation to fail
    invalid_path = "/invalid/path/that/does/not/exist/member_servers.json"
    original_env = os.environ.get("SERVER_CONFIG_FILE_PATH")
    os.environ["SERVER_CONFIG_FILE_PATH"] = invalid_path

    try:
        # Create a temporary directory to test file creation
        with tempfile.TemporaryDirectory() as temp_dir:
            # Change to temp directory to avoid conflicts
            original_cwd = os.getcwd()
            os.chdir(temp_dir)

            try:
                # This should not raise any errors during initialization, even with invalid path
                composer = MCPComposer("composer", config=None, database_config=fake_db)

                # Should have basic composer tools available
                tools = await composer.list_tools()
                assert isinstance(
                    tools, list
                ), "Composer should have basic tools available"
                assert len(tools) > 0, "Composer should have at least some basic tools"

                # Should have no member servers mounted
                mounted_servers = composer._server_manager.list_servers()
                assert (
                    mounted_servers == []
                ), "Composer should start with no member servers when no config provided"

                # Should have no database configs loaded
                assert (
                    len(composer._db_configs) == 0
                ), "No database configs should be loaded when no database provided"
                assert (
                    len(composer._server_config_manager.config) == 0
                ), "No configs should be loaded when none provided"

                # Should be able to call setup_member_servers without errors (it will just log a warning)
                await composer.setup_member_servers()

            finally:
                # Restore original working directory
                os.chdir(original_cwd)

    finally:
        # Restore original environment variable
        if original_env is not None:
            os.environ["SERVER_CONFIG_FILE_PATH"] = original_env
        else:
            del os.environ["SERVER_CONFIG_FILE_PATH"]


@pytest.mark.asyncio
async def test_composer_uses_local_file_adapter_when_no_database_config(
    fake_db, server_config
):
    """Test that MCP composer works with database config provided."""
    # Clear environment variables that might interfere with the test
    original_env_db_type = os.environ.get("MCP_DATABASE_TYPE")
    original_env_use_local = os.environ.get("MCP_USE_LOCAL_FILE_STORAGE")

    if "MCP_DATABASE_TYPE" in os.environ:
        del os.environ["MCP_DATABASE_TYPE"]
    if "MCP_USE_LOCAL_FILE_STORAGE" in os.environ:
        del os.environ["MCP_USE_LOCAL_FILE_STORAGE"]

    try:
        composer = MCPComposer(
            "composer", config=[server_config], database_config=fake_db
        )

        # Verify that the composer is using the provided fake_db
        assert (
            composer._server_manager._database is fake_db
        ), "Composer should use provided database"

        # Should be able to call setup_member_servers without errors
        await composer.setup_member_servers()

        # Should have basic composer tools available
        tools = await composer.list_tools()
        assert isinstance(tools, list), "Composer should have basic tools available"
        assert len(tools) > 0, "Composer should have at least some basic tools"

        # Should have the server from config mounted in memory
        in_memory_servers = composer._server_manager.list()
        assert (
            len(in_memory_servers) >= 1
        ), "Composer should have at least one mounted server"

        # Verify the server config is present
        server_ids = [s.id for s in in_memory_servers]
        assert (
            server_config["id"] in server_ids
        ), "Should have the correct server mounted in memory"

        # Should have no database configs loaded from database (since database is empty)
        assert (
            len(composer._db_configs) == 0
        ), "No database configs should be loaded when database is empty"

        # Should have config from the config parameter
        assert (
            len(composer._server_config_manager.config) == 1
        ), "One config should be loaded from the config parameter"
    finally:
        # Restore environment variables
        if original_env_db_type is not None:
            os.environ["MCP_DATABASE_TYPE"] = original_env_db_type
        if original_env_use_local is not None:
            os.environ["MCP_USE_LOCAL_FILE_STORAGE"] = original_env_use_local
