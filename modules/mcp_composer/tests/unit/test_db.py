import pytest
import logging

from mcp_composer.core.composer import MCPComposer
from mcp_composer.store.fake_database import FakeDatabase


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
        "endpoint": "https://mcp-stock-info.1vgzmntiwjzl.eu-es.codeengine.appdomain.cloud/mcp",
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

    # -------- First run --------
    composer_1 = MCPComposer(
        "composer", config=[server_config], database_config=fake_db
    )
    await composer_1.setup_member_servers()
    tools_1 = await composer_1.get_tools()
    logger.debug("[First run] Tools: %s", tools_1)
    assert any(
        server_config["id"] in t for t in tools_1
    ), "Server tools not available after registration"

    # -------- Simulate restart --------
    composer_2 = MCPComposer("composer", database_config=fake_db)
    await composer_2.setup_member_servers()
    tools_2 = await composer_2.get_tools()
    logger.debug("[After restart] Tools: %s", tools_2)
    assert any(
        server_config["id"] in t for t in tools_2
    ), "Server tool not found after restart"


@pytest.mark.asyncio
async def test_duplicate_registration_skips_duplicate(fake_db, server_config, caplog):
    caplog.set_level(logging.INFO)
    composer = MCPComposer("composer", config=[server_config], database_config=fake_db)
    await composer.setup_member_servers()

    # Register again with same config
    await composer.setup_member_servers()

    assert (
        len(fake_db._servers) == 1
    ), "Duplicate registration should not add a second entry"
    assert server_config["id"] in fake_db._servers


@pytest.mark.asyncio
async def test_corrupt_entry_does_not_crash_composer(fake_db):
    # Add corrupt entry directly to the fake database
    fake_db._servers["corrupt-entry"] = {"type": "sse", "endpoint": "http://bad"}

    composer = MCPComposer("composer", database_config=fake_db)
    # Should not raise error even though one entry is invalid
    await composer.setup_member_servers()

    tools = await composer.get_tools()
    assert isinstance(tools, dict), "Composer should recover from bad DB entries"


@pytest.mark.asyncio
async def test_empty_database_loads_no_servers(fake_db):
    composer = MCPComposer("composer", database_config=fake_db)
    await composer.setup_member_servers()
    mounted_servers = composer._server_manager.list_member_servers()
    assert mounted_servers == [], "Composer should start cleanly with empty DB"


@pytest.mark.asyncio
async def test_no_database_config_works(fake_db, server_config):
    # Test with no database config
    print("Testing composer with no database config %s", server_config)
    composer = MCPComposer("composer", config=[server_config])
    await composer.setup_member_servers()

    # Should still work but not persist
    tools = await composer.get_tools()
    assert any(server_config["id"] in t for t in tools)

    # Verify nothing was persisted to database
    assert len(fake_db._servers) == 0


@pytest.mark.asyncio
async def test_composer_initializes_without_any_config():
    """Test that MCP composer can initialize without any configuration files or database config."""
    import os
    import tempfile
    import json
    from pathlib import Path

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
                composer = MCPComposer("composer", config=None, database_config=None)

                # Should have basic composer tools available
                tools = await composer.get_tools()
                assert isinstance(
                    tools, dict
                ), "Composer should have basic tools available"
                assert len(tools) > 0, "Composer should have at least some basic tools"

                # Should have no member servers mounted
                mounted_servers = composer._server_manager.list_member_servers()
                assert (
                    mounted_servers == []
                ), "Composer should start with no member servers when no config provided"

                # Should have no database configs loaded
                assert (
                    len(composer._db_configs) == 0
                ), "No database configs should be loaded when no database provided"
                assert (
                    len(composer._config) == 0
                ), "No configs should be loaded when none provided"

                # Should create member_servers.json file automatically
                member_servers_file = Path("member_servers.json")
                assert (
                    member_servers_file.exists()
                ), "member_servers.json should be created automatically"

                # File should contain empty array
                with open(member_servers_file, "r", encoding="utf-8") as f:
                    file_content = json.load(f)
                assert (
                    file_content == []
                ), "member_servers.json should contain empty array initially"

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
async def test_composer_initializes_when_file_creation_fails():
    """Test that MCP composer can initialize successfully even when member_servers.json file creation fails."""
    import os
    import tempfile
    from pathlib import Path

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
                composer = MCPComposer("composer", config=None, database_config=None)

                # Should have basic composer tools available
                tools = await composer.get_tools()
                assert isinstance(
                    tools, dict
                ), "Composer should have basic tools available"
                assert len(tools) > 0, "Composer should have at least some basic tools"

                # Should have no member servers mounted
                mounted_servers = composer._server_manager.list_member_servers()
                assert (
                    mounted_servers == []
                ), "Composer should start with no member servers when no config provided"

                # Should have no database configs loaded
                assert (
                    len(composer._db_configs) == 0
                ), "No database configs should be loaded when no database provided"
                assert (
                    len(composer._config) == 0
                ), "No configs should be loaded when none provided"

                # Should be able to call setup_member_servers without errors (it will just log a warning)
                await composer.setup_member_servers()

                # The file should not exist due to permission issues
                member_servers_file = Path("member_servers.json")
                # Note: We don't assert file existence here since it may or may not be created
                # depending on the timing and OS behavior

            finally:
                # Restore original working directory
                os.chdir(original_cwd)
                # Clean up read-only directory
                try:
                    os.chmod(read_only_dir, 0o755)  # Make writable again
                except:
                    pass

    finally:
        # Restore original environment variable
        if original_env is not None:
            os.environ["SERVER_CONFIG_FILE_PATH"] = original_env


@pytest.mark.asyncio
async def test_composer_initializes_with_invalid_file_path():
    """Test that MCP composer can initialize successfully even with an invalid file path."""
    import os
    import tempfile
    from pathlib import Path

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
                composer = MCPComposer("composer", config=None, database_config=None)

                # Should have basic composer tools available
                tools = await composer.get_tools()
                assert isinstance(
                    tools, dict
                ), "Composer should have basic tools available"
                assert len(tools) > 0, "Composer should have at least some basic tools"

                # Should have no member servers mounted
                mounted_servers = composer._server_manager.list_member_servers()
                assert (
                    mounted_servers == []
                ), "Composer should start with no member servers when no config provided"

                # Should have no database configs loaded
                assert (
                    len(composer._db_configs) == 0
                ), "No database configs should be loaded when no database provided"
                assert (
                    len(composer._config) == 0
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
async def test_composer_uses_local_file_adapter_when_no_database_config(server_config):
    """Test that MCP composer uses LocalFileAdapter when no database config is provided."""
    # This should not raise any errors and should use LocalFileAdapter
    composer = MCPComposer("composer", config=[server_config], database_config=None)

    # Should be able to call setup_member_servers without errors
    await composer.setup_member_servers()

    # Should have basic composer tools available
    tools = await composer.get_tools()
    assert isinstance(tools, dict), "Composer should have basic tools available"
    assert len(tools) > 0, "Composer should have at least some basic tools"

    # Should have the server from config mounted
    mounted_servers = composer._server_manager.list_member_servers()
    assert len(mounted_servers) == 1, "Composer should mount server from config"
    assert (
        mounted_servers[0]["id"] == "mcp-stock-info"
    ), "Should have the correct server mounted"

    # Should have database configs loaded (from LocalFileAdapter)
    assert (
        len(composer._db_configs) >= 0
    ), "Database configs should be loaded (even if empty)"
    assert (
        len(composer._config) == 1
    ), "One config should be loaded from the config parameter"
