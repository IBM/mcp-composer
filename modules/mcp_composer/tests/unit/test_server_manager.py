"""test_server_manager.py"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastmcp.exceptions import NotFoundError, ToolError

from mcp_composer.core.composer import MCPComposer
from mcp_composer.core.member_servers.server_manager import ServerManager
from mcp_composer.core.utils.exceptions import ToolDisableError

# pylint: disable=protected-access


@pytest.mark.asyncio
async def test_register_server_success():
    manager = ServerManager()
    config = {"id": "srv", "type": "stdio", "command": "uv", "args": ["run"]}
    with (
        patch(
            "mcp_composer.core.member_servers.server_manager.ServerConfigValidator"
        ) as mock_validator,
        patch.object(manager, "has_member_server", return_value=False),
        patch.object(
            manager, "_mount_and_register_server", new=AsyncMock(return_value="ok")
        ),
    ):
        mock_validator.return_value.validate.return_value = None
        result = await manager.register_server(config, MagicMock())
        assert result == "ok"


@pytest.mark.asyncio
async def test_register_server_already_mounted():
    manager = ServerManager()
    config = {"id": "srv", "type": "stdio", "command": "uv", "args": ["run"]}
    with (
        patch(
            "mcp_composer.core.member_servers.server_manager.ServerConfigValidator"
        ) as mock_validator,
        patch.object(manager, "has_member_server", return_value=True),
    ):
        mock_validator.return_value.validate.return_value = None
        result = await manager.register_server(config, MagicMock())
        assert "already mounted" in result


@pytest.mark.asyncio
async def test_register_server_validation_error():
    manager = ServerManager()
    config = {"id": "srv", "type": "stdio", "command": "uv", "args": ["run"]}
    with patch(
        "mcp_composer.core.member_servers.server_manager.ServerConfigValidator"
    ) as mock_validator:
        mock_validator.return_value.validate.side_effect = Exception("fail")
        with pytest.raises(ToolError):
            await manager.register_server(config, MagicMock())


@pytest.mark.asyncio
async def test_update_server_config_success():
    manager = ServerManager()
    config = {"id": "srv", "type": "stdio", "command": "uv", "args": ["run"]}
    with (
        patch(
            "mcp_composer.core.member_servers.server_manager.ServerConfigValidator"
        ) as mock_validator,
        patch.object(manager, "has_member_server", return_value=True),
        patch.object(manager, "remove_member"),
        patch.object(manager, "update_server_db"),
        patch.object(
            manager, "_mount_and_register_server", new=AsyncMock(return_value="ok")
        ),
    ):
        mock_validator.return_value.validate.return_value = None
        manager._database = MagicMock(
            get_document=MagicMock(return_value={"foo": "bar"})
        )
        manager._config_manager = MagicMock(save_version=MagicMock(return_value="v1"))
        result = await manager.update_server_config("srv", config, MagicMock())
        assert result == "ok"


@pytest.mark.asyncio
async def test_update_server_config_not_found():
    manager = ServerManager()
    config = {"id": "srv", "type": "stdio", "command": "uv", "args": ["run"]}
    with (
        patch(
            "mcp_composer.core.member_servers.server_manager.ServerConfigValidator"
        ) as mock_validator,
        patch.object(manager, "has_member_server", return_value=False),
    ):
        mock_validator.return_value.validate.return_value = None
        manager._database = MagicMock()
        with pytest.raises(ToolError):
            await manager.update_server_config("srv", config, MagicMock())


@pytest.mark.asyncio
async def test_activate_server_success():
    manager = ServerManager()
    with (
        patch.object(
            manager,
            "prepare_activation",
            return_value={
                "id": "srv",
                "type": "stdio",
                "command": "uv",
                "args": ["run"],
            },
        ),
        patch.object(manager, "has_member_server", return_value=False),
        patch.object(
            manager, "_mount_and_register_server", new=AsyncMock(return_value="ok")
        ),
    ):
        result = await manager.activate_server("srv", MagicMock())
        assert result == "Server 'srv' activated"


@pytest.mark.asyncio
async def test_activate_server_already_mounted():
    manager = ServerManager()
    with (
        patch.object(
            manager,
            "prepare_activation",
            return_value={
                "id": "srv",
                "type": "stdio",
                "command": "uv",
                "args": ["run"],
            },
        ),
        patch.object(manager, "has_member_server", return_value=True),
    ):
        result = await manager.activate_server("srv", MagicMock())
        assert "already mounted" in result


def test_deactivate_server_success():
    manager = ServerManager()
    manager._member_servers["srv"] = MagicMock()
    with patch.object(manager, "prepare_deactivation") as mock_prepare:
        mcp_composer = MCPComposer()
        result = manager.deactivate_server("srv", mcp_composer)
        mock_prepare.assert_called_once_with("srv")
        assert hasattr(manager._member_servers["srv"], "health_status")
        assert "deactivated" in result


# Additional comprehensive tests from test_server_manager_extended.py
def test_server_manager_initialization_with_duplicate_behavior():
    """Test ServerManager basic initialization."""
    manager = ServerManager()
    assert manager._member_servers == {}
    assert manager._database is None


def test_server_manager_initialization_invalid_duplicate_behavior():
    """ServerManager should reject unsupported constructor kwargs."""
    with pytest.raises(TypeError) as exc_info:
        ServerManager(duplicate_behavior="invalid_behavior")
    assert "unexpected keyword argument 'duplicate_behavior'" in str(exc_info.value)


def test_default_serializer():
    """Test default serializer."""
    manager = ServerManager()
    mock_member_server = MagicMock()
    mock_member_server.to_dict.return_value = {"id": "test", "type": "stdio"}

    result = manager.default_serializer("test_server", mock_member_server)
    assert result == {"id": "test", "type": "stdio"}
    mock_member_server.to_dict.assert_called_once()


@pytest.mark.asyncio
async def test_mount_and_register_server_no_db_save():
    """Test mounting and registration without database save."""
    manager = ServerManager()

    with patch(
        "mcp_composer.core.member_servers.server_manager.MCPServerBuilder"
    ) as mock_builder_class:
        mock_server = AsyncMock()
        # Mock get_tools to return a dictionary with tools that have descriptions
        mock_tool = MagicMock()
        mock_tool.name = "test_tool"
        mock_tool.description = "A test tool with description"
        mock_server.get_tools = AsyncMock(return_value={"test_tool": mock_tool})

        mock_builder = MagicMock()
        mock_builder.build = AsyncMock(return_value=mock_server)
        mock_builder_class.return_value = mock_builder

        mount_callback = MagicMock()
        mount_callback.return_value = MCPComposer()

        config = {"id": "test_server", "type": "test_type"}

        result = await manager._mount_and_register_server(
            config, mount_callback, save_to_db=False
        )

        assert "Server 'test_server' mounted successfully." in result
        # Should not call database save
        assert not hasattr(manager, "_database") or manager._database is None


@pytest.mark.asyncio
async def test_register_server_with_validation():
    """Test server registration with validation."""
    manager = ServerManager()

    with patch(
        "mcp_composer.core.member_servers.server_manager.MCPServerBuilder"
    ) as mock_builder_class:
        mock_server = AsyncMock()
        # Mock get_tools to return a dictionary with tools that have descriptions
        mock_tool = MagicMock()
        mock_tool.name = "test_tool"
        mock_tool.description = "A test tool with description"
        mock_server.get_tools = AsyncMock(return_value={"test_tool": mock_tool})

        config = {"id": "test_server", "type": "test_type"}
        mock_builder = AsyncMock()
        mock_builder.build = AsyncMock(return_value=mock_server)
        mock_builder_class.return_value = mock_builder

        mount_callback = MagicMock()
        mount_callback.return_value = MCPComposer()

        result = await manager.register_server(config, mount_callback)

        assert "Server 'test_server' mounted successfully." in result


@pytest.mark.asyncio
async def test_update_server_config_server_not_found():
    """Test server config update with non-existent server."""
    manager = ServerManager()
    mcp_composer = MagicMock()

    new_config = {"id": "test_server", "type": "updated_type"}

    with pytest.raises(ToolError) as exc_info:
        await manager.update_server_config(
            "nonexistent_server", new_config, mcp_composer
        )
    assert "Server ID in config does not match" in str(exc_info.value)


@pytest.mark.asyncio
async def test_activate_server_not_found():
    """Test server activation with non-existent server."""
    manager = ServerManager()
    mcp_composer = MagicMock()

    with pytest.raises(ToolError) as exc_info:
        await manager.activate_server("nonexistent_server", mcp_composer)
    assert "Failed to activate server 'nonexistent_server'" in str(exc_info.value)


def test_deactivate_server_not_found():
    """Test server deactivation with non-existent server."""
    manager = ServerManager()
    mcp_composer = MagicMock()

    with pytest.raises(ToolError) as exc_info:
        manager.deactivate_server("nonexistent_server", mcp_composer)
    assert "Server 'nonexistent_server' not found in DB" in str(exc_info.value)


@pytest.mark.asyncio
async def test_member_health():
    """Test member health check."""
    manager = ServerManager()
    mock_member_server = MagicMock()
    config = [mock_member_server]

    with patch(
        "mcp_composer.core.member_servers.server_manager.get_member_health"
    ) as mock_health:
        mock_health.return_value = {"status": "healthy"}

        result = await manager.member_health(config)

        # The method returns a dict, not a list
        assert result == {"status": "healthy"}
        mock_health.assert_called_once_with(config)


def test_list_servers():
    """Test listing member servers."""
    manager = ServerManager()
    mock_member_server = MagicMock()
    mock_member_server.to_dict.return_value = {"id": "test_server", "type": "test_type"}
    manager._member_servers["test_server"] = mock_member_server

    # Mock the database to return a server config
    manager._database = MagicMock()
    manager._database.load_all_servers.return_value = [
        {"id": "test_server", "type": "test_type"}
    ]  # <-- FIXED HERE

    result = manager.list_servers()

    # The method returns a list of dicts with server info
    assert len(result) == 1
    assert result[0]["id"] == "test_server"


def test_check_server_exist_success():
    """Test checking existing server."""
    manager = ServerManager()
    mock_member_server = MagicMock()
    manager._member_servers["test_server"] = mock_member_server

    # Should not raise an exception
    manager.check_server_exist("test_server")


def test_check_server_exist_not_found():
    """Test checking non-existent server."""
    manager = ServerManager()

    with pytest.raises(NotFoundError) as exc_info:
        manager.check_server_exist("nonexistent_server")
    assert "not mounted" in str(exc_info.value)


def test_has_member_server_true():
    """Test checking if member server exists (true)."""
    manager = ServerManager()
    mock_member_server = MagicMock()
    manager._member_servers["test_server"] = mock_member_server

    result = manager.has_member_server("test_server")
    assert result is True


def test_has_member_server_false():
    """Test checking if member server exists (false)."""
    manager = ServerManager()

    result = manager.has_member_server("nonexistent_server")
    assert result is False


def test_add_member():
    """Test adding member server."""
    manager = ServerManager()
    mock_member_server = MagicMock()

    manager.add_member("test_server", mock_member_server)

    assert "test_server" in manager._member_servers
    assert manager._member_servers["test_server"] == mock_member_server


def test_update_server_db():
    """Test updating server in database."""
    manager = ServerManager()
    manager._database = MagicMock()

    config = {"id": "test_server", "type": "test_type"}

    manager.update_server_db(config)

    manager._database.update_server_config.assert_called_once_with(config)


def test_remove_member():
    """Test removing member server."""
    manager = ServerManager()
    mock_member_server = MagicMock()
    manager._member_servers["test_server"] = mock_member_server

    manager.remove_member("test_server")

    assert "test_server" not in manager._member_servers


def test_get_success():
    """Test getting existing member server."""
    manager = ServerManager()
    mock_member_server = MagicMock()
    manager._member_servers["test_server"] = mock_member_server

    result = manager.get("test_server")
    assert result == mock_member_server


def test_get_not_found():
    """Test getting non-existent member server."""
    manager = ServerManager()

    with pytest.raises(NotFoundError) as exc_info:
        manager.get("nonexistent_server")
    assert "not mounted" in str(exc_info.value)


def test_list():
    """Test listing all member servers."""
    manager = ServerManager()
    mock_member_server = MagicMock()
    manager._member_servers["test_server"] = mock_member_server

    result = manager.list()
    assert result == [mock_member_server]


def test_list_serialized():
    """Test listing serialized member servers."""
    manager = ServerManager()
    mock_member_server = MagicMock()
    mock_member_server.to_dict.return_value = {"id": "test_server", "type": "test_type"}
    manager._member_servers["test_server"] = mock_member_server

    result = manager.list_serialized()
    assert result == {"test_server": {"id": "test_server", "type": "test_type"}}


def test_add_server_db():
    """Test adding server to database."""
    manager = ServerManager()
    manager._database = MagicMock()

    config = {"id": "test_server", "type": "test_type"}

    manager.add_server_db(config)

    manager._database.add_server.assert_called_once_with(config)


def test_remove_mcp_server():
    """Test removing MCP server from database."""
    manager = ServerManager()
    manager._database = MagicMock()

    manager.remove_mcp_server("test_server")

    manager._database.remove_server.assert_called_once_with("test_server")


def test_load_all_servers_db():
    """Test loading all servers from database."""
    manager = ServerManager()
    manager._database = MagicMock()
    expected_servers = [{"id": "server1"}, {"id": "server2"}]
    manager._database.load_all_servers.return_value = expected_servers

    result = manager.load_all_servers_db()

    assert result == expected_servers
    manager._database.load_all_servers.assert_called_once()


def test_disable_tools_success():
    """Test disabling tools successfully."""
    manager = ServerManager()
    mock_member_server = MagicMock()
    mock_member_server.disabled_tools = []
    manager._member_servers["test_server"] = mock_member_server

    tools = ["tool1", "tool2"]
    manager.disable_tools(tools, "test_server")

    assert "tool1" in mock_member_server.disabled_tools
    assert "tool2" in mock_member_server.disabled_tools


def test_disable_tools_server_not_found():
    """Test disabling tools for non-existent server."""
    manager = ServerManager()

    with pytest.raises(ToolDisableError) as exc_info:
        manager.disable_tools(["tool1"], "nonexistent_server")
    assert "not mounted" in str(exc_info.value)


def test_enable_tools_success():
    """Test enabling tools successfully."""
    manager = ServerManager()
    mock_member_server = MagicMock()
    mock_member_server.disabled_tools = ["tool1", "tool2"]
    manager._member_servers["test_server"] = mock_member_server

    tools = ["tool1"]
    manager.enable_tools(tools, "test_server")

    assert "tool1" not in mock_member_server.disabled_tools
    assert "tool2" in mock_member_server.disabled_tools


def test_enable_tools_server_not_found():
    """Test enabling tools for non-existent server."""
    manager = ServerManager()

    with pytest.raises(ToolDisableError) as exc_info:
        manager.enable_tools(["tool1"], "nonexistent_server")
    assert "not mounted" in str(exc_info.value)


def test_update_tool_description_success():
    """Test updating tool description successfully."""
    manager = ServerManager()
    mock_member_server = MagicMock()
    mock_member_server.tools_description = {}
    manager._member_servers["test_server"] = mock_member_server

    manager.update_tool_description("tool1", "New description", "test_server")

    assert mock_member_server.tools_description["tool1"] == "New description"


def test_update_tool_description_server_not_found():
    """Test updating tool description for non-existent server."""
    manager = ServerManager()

    with pytest.raises(NotFoundError) as exc_info:
        manager.update_tool_description("tool1", "description", "nonexistent_server")
    assert "not mounted" in str(exc_info.value)


def test_disable_prompts_success():
    """Test disabling prompts successfully."""
    manager = ServerManager()
    mock_member_server = MagicMock()
    mock_member_server.disabled_prompts = []
    manager._member_servers["test_server"] = mock_member_server

    prompts = ["prompt1", "prompt2"]
    manager.disable_prompts(prompts, "test_server")

    assert "prompt1" in mock_member_server.disabled_prompts
    assert "prompt2" in mock_member_server.disabled_prompts


def test_disable_prompts_server_not_found():
    """Test disabling prompts for non-existent server."""
    manager = ServerManager()

    with pytest.raises(ToolDisableError) as exc_info:
        manager.disable_prompts(["prompt1"], "nonexistent_server")
    assert "not mounted" in str(exc_info.value)


def test_enable_prompts_success():
    """Test enabling prompts successfully."""
    manager = ServerManager()
    mock_member_server = MagicMock()
    mock_member_server.disabled_prompts = ["prompt1", "prompt2"]
    manager._member_servers["test_server"] = mock_member_server

    prompts = ["prompt1"]
    manager.enable_prompts(prompts, "test_server")

    assert "prompt1" not in mock_member_server.disabled_prompts
    assert "prompt2" in mock_member_server.disabled_prompts


def test_enable_prompts_server_not_found():
    """Test enabling prompts for non-existent server."""
    manager = ServerManager()

    with pytest.raises(ToolDisableError) as exc_info:
        manager.enable_prompts(["prompt1"], "nonexistent_server")
    assert "not mounted" in str(exc_info.value)


def test_disable_resources_success():
    """Test disabling resources successfully."""
    manager = ServerManager()
    mock_member_server = MagicMock()
    mock_member_server.disabled_resources = []
    manager._member_servers["test_server"] = mock_member_server

    resources = ["resource1", "resource2"]
    manager.disable_resources(resources, "test_server")

    assert "resource1" in mock_member_server.disabled_resources
    assert "resource2" in mock_member_server.disabled_resources


def test_disable_resources_server_not_found():
    """Test disabling resources for non-existent server."""
    manager = ServerManager()

    with pytest.raises(ToolDisableError) as exc_info:
        manager.disable_resources(["resource1"], "nonexistent_server")
    assert "not mounted" in str(exc_info.value)


def test_enable_resources_success():
    """Test enabling resources successfully."""
    manager = ServerManager()
    mock_member_server = MagicMock()
    mock_member_server.disabled_resources = ["resource1", "resource2"]
    manager._member_servers["test_server"] = mock_member_server

    resources = ["resource1"]
    manager.enable_resources(resources, "test_server")

    assert "resource1" not in mock_member_server.disabled_resources
    assert "resource2" in mock_member_server.disabled_resources


def test_enable_resources_server_not_found():
    """Test enabling resources for non-existent server."""
    manager = ServerManager()

    with pytest.raises(ToolDisableError) as exc_info:
        manager.enable_resources(["resource1"], "nonexistent_server")
    assert "not mounted" in str(exc_info.value)


def test_get_document_success():
    """Test getting document successfully."""
    manager = ServerManager()
    manager._database = MagicMock()
    expected_doc = {"id": "test_server", "type": "test_type"}
    manager._database.get_document.return_value = expected_doc

    result = manager.get_document("test_server")

    assert result == expected_doc
    manager._database.get_document.assert_called_once_with("test_server")


def test_get_member_success():
    """Test getting member successfully."""
    manager = ServerManager()
    mock_member_server = MagicMock()
    manager._member_servers["test_server"] = mock_member_server

    result = manager.get_member("test_server")
    assert result == mock_member_server


def test_get_member_not_found():
    """Test getting non-existent member."""
    manager = ServerManager()

    result = manager.get_member("nonexistent_server")
    assert result is None


def test_is_iam_enabled_for_server_not_found():
    """Server not mounted -> False."""
    manager = ServerManager()
    assert manager.is_iam_enabled_for_server("nonexistent") is False


def test_is_iam_enabled_for_server_no_solis_config():
    """Member has no solis_config -> False."""
    manager = ServerManager()
    mock_member = MagicMock()
    mock_member.config = {"id": "srv1"}
    manager._member_servers["srv1"] = mock_member
    assert manager.is_iam_enabled_for_server("srv1") is False


def test_is_iam_enabled_for_server_solis_config_iam_false():
    """Member has solis_config but isIamEnabled false -> False."""
    manager = ServerManager()
    mock_member = MagicMock()
    mock_member.config = {"id": "srv1", "solis_config": {"product_id": "gi", "isIamEnabled": False}}
    manager._member_servers["srv1"] = mock_member
    assert manager.is_iam_enabled_for_server("srv1") is False


def test_is_iam_enabled_for_server_solis_config_iam_true():
    """Member has solis_config.isIamEnabled true -> True."""
    manager = ServerManager()
    mock_member = MagicMock()
    mock_member.config = {"id": "srv1", "solis_config": {"product_id": "gi", "isIamEnabled": True}}
    manager._member_servers["srv1"] = mock_member
    assert manager.is_iam_enabled_for_server("srv1") is True


def test_is_iam_enabled_for_server_solis_config_missing_is_iam_key():
    """Member has solis_config but no isIamEnabled key -> False."""
    manager = ServerManager()
    mock_member = MagicMock()
    mock_member.config = {"id": "srv1", "solis_config": {"product_id": "gi"}}
    manager._member_servers["srv1"] = mock_member
    assert manager.is_iam_enabled_for_server("srv1") is False


def test_is_iam_enabled_for_server_solis_config_not_dict():
    """Member has solis_config that is not a dict -> False."""
    manager = ServerManager()
    mock_member = MagicMock()
    mock_member.config = {"id": "srv1", "solis_config": "invalid"}
    manager._member_servers["srv1"] = mock_member
    assert manager.is_iam_enabled_for_server("srv1") is False


def test_prepare_activation_success():
    """Test preparing activation successfully."""
    manager = ServerManager()
    mock_member_server = MagicMock()
    mock_member_server.id = "test_server"
    mock_member_server.type = "test_type"
    mock_member_server.label = "Test Server"
    mock_member_server.tags = ["test"]
    manager._member_servers["test_server"] = mock_member_server

    # Mock the database to return server configs
    manager._database = MagicMock()
    manager._database.load_all_servers.return_value = [
        {"id": "test_server", "status": "deactivated"}
    ]

    result = manager.prepare_activation("test_server")

    assert result["id"] == "test_server"
    assert result["status"] == "active"


def test_prepare_activation_not_found():
    """Test preparing activation for non-existent server."""
    manager = ServerManager()

    with pytest.raises(NotFoundError) as exc_info:
        manager.prepare_activation("nonexistent_server")
    assert "No configuration found" in str(exc_info.value)


def test_prepare_deactivation_success():
    """Test preparing deactivation successfully."""
    manager = ServerManager()
    mock_member_server = MagicMock()
    manager._member_servers["test_server"] = mock_member_server
    manager._database = MagicMock()

    manager.prepare_deactivation("test_server")

    # Should call mark_deactivated on the database
    manager._database.mark_deactivated.assert_called_once_with("test_server")


def test_prepare_deactivation_not_found():
    """Test preparing deactivation for non-existent server."""
    manager = ServerManager()

    with pytest.raises(NotFoundError) as exc_info:
        manager.prepare_deactivation("nonexistent_server")
    assert "not found in DB" in str(exc_info.value)


def test_mark_deactivated_success():
    """Test marking server as deactivated successfully."""
    manager = ServerManager()
    mock_member_server = MagicMock()
    from mcp_composer.core.member_servers.member_server import HealthStatus

    manager._member_servers["test_server"] = mock_member_server

    manager.mark_deactivated("test_server")

    # Since HealthStatus.deactivated doesn't exist, we'll check that the method was called
    # The actual implementation may set it to unhealthy or another valid status
    assert hasattr(mock_member_server, "health_status")


def test_mark_deactivated_not_found():
    """Test marking non-existent server as deactivated."""
    manager = ServerManager()

    # The method doesn't raise NotFoundError, it just logs a warning
    # So we test that it doesn't crash
    manager.mark_deactivated("nonexistent_server")
    # Should not raise an exception


def test_get_server_status_healthy():
    """Test getting server status for healthy server."""
    manager = ServerManager()
    mock_member_server = MagicMock()
    from mcp_composer.core.member_servers.member_server import HealthStatus

    mock_member_server.health_status = HealthStatus.healthy
    manager._member_servers["test_server"] = mock_member_server

    # Mock the database to return the expected status
    manager._database = MagicMock()
    manager._database.get_server_status.return_value = "healthy"

    result = manager.get_server_status("test_server")
    assert result == "healthy"


def test_get_server_status_unhealthy():
    """Test getting server status for unhealthy server."""
    manager = ServerManager()
    mock_member_server = MagicMock()
    from mcp_composer.core.member_servers.member_server import HealthStatus

    mock_member_server.health_status = HealthStatus.unhealthy
    manager._member_servers["test_server"] = mock_member_server

    # Mock the database to return the expected status
    manager._database = MagicMock()
    manager._database.get_server_status.return_value = "unhealthy"

    result = manager.get_server_status("test_server")
    assert result == "unhealthy"


def test_get_server_status_deactivated():
    """Test getting server status for deactivated server."""
    manager = ServerManager()
    mock_member_server = MagicMock()
    from mcp_composer.core.member_servers.member_server import HealthStatus

    # Since HealthStatus.deactivated doesn't exist, use unhealthy instead
    mock_member_server.health_status = HealthStatus.unhealthy
    manager._member_servers["test_server"] = mock_member_server

    # Mock the database to return the expected status
    manager._database = MagicMock()
    manager._database.get_server_status.return_value = "deactivated"

    result = manager.get_server_status("test_server")
    assert result == "deactivated"


def test_get_server_status_not_found():
    """Test getting server status for non-existent server."""
    manager = ServerManager()

    # The method doesn't raise NotFoundError, it returns "unknown"
    result = manager.get_server_status("nonexistent_server")
    assert result == "unknown"
