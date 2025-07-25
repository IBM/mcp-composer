import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from mcp_composer.member_servers.server_manager import ServerManager
from fastmcp.exceptions import NotFoundError, ToolError

@pytest.mark.asyncio
async def test_register_server_success():
    manager = ServerManager()
    config = {'id': 'srv', 'type': 'stdio', 'command': 'uv', 'args': ['run']}
    with patch('mcp_composer.member_servers.server_manager.ServerConfigValidator') as mock_validator, \
         patch.object(manager, 'has_member_server', return_value=False), \
         patch.object(manager, '_mount_and_register_server', new=AsyncMock(return_value='ok')):
        mock_validator.return_value.validate.return_value = None
        result = await manager.register_server(config, MagicMock())
        assert result == 'ok'

@pytest.mark.asyncio
async def test_register_server_already_mounted():
    manager = ServerManager()
    config = {'id': 'srv', 'type': 'stdio', 'command': 'uv', 'args': ['run']}
    with patch('mcp_composer.member_servers.server_manager.ServerConfigValidator') as mock_validator, \
         patch.object(manager, 'has_member_server', return_value=True):
        mock_validator.return_value.validate.return_value = None
        result = await manager.register_server(config, MagicMock())
        assert "already mounted" in result

@pytest.mark.asyncio
async def test_register_server_validation_error():
    manager = ServerManager()
    config = {'id': 'srv', 'type': 'stdio', 'command': 'uv', 'args': ['run']}
    with patch('mcp_composer.member_servers.server_manager.ServerConfigValidator') as mock_validator:
        mock_validator.return_value.validate.side_effect = Exception('fail')
        with pytest.raises(ToolError):
            await manager.register_server(config, MagicMock())

@pytest.mark.asyncio
async def test_update_server_config_success():
    manager = ServerManager()
    config = {'id': 'srv', 'type': 'stdio', 'command': 'uv', 'args': ['run']}
    with patch('mcp_composer.member_servers.server_manager.ServerConfigValidator') as mock_validator, \
         patch.object(manager, 'has_member_server', return_value=True), \
         patch.object(manager, 'remove_member'), \
         patch.object(manager, 'update_server_db'), \
         patch.object(manager, '_mount_and_register_server', new=AsyncMock(return_value='ok')):
        mock_validator.return_value.validate.return_value = None
        manager._database = MagicMock(get_document=MagicMock(return_value={'foo': 'bar'}))
        manager._config_manager = MagicMock(save_version=MagicMock(return_value='v1'))
        result = await manager.update_server_config('srv', config, MagicMock(), MagicMock())
        assert result == 'ok'

@pytest.mark.asyncio
async def test_update_server_config_not_found():
    manager = ServerManager()
    config = {'id': 'srv', 'type': 'stdio', 'command': 'uv', 'args': ['run']}
    with patch('mcp_composer.member_servers.server_manager.ServerConfigValidator') as mock_validator, \
         patch.object(manager, 'has_member_server', return_value=False):
        mock_validator.return_value.validate.return_value = None
        manager._database = MagicMock()
        with pytest.raises(NotFoundError):
            await manager.update_server_config('srv', config, MagicMock(), MagicMock())

@pytest.mark.asyncio
async def test_activate_server_success():
    manager = ServerManager()
    with patch.object(manager, 'prepare_activation', return_value={'id': 'srv', 'type': 'stdio', 'command': 'uv', 'args': ['run']}), \
         patch.object(manager, 'has_member_server', return_value=False), \
         patch.object(manager, '_mount_and_register_server', new=AsyncMock(return_value='ok')):
        result = await manager.activate_server('srv', MagicMock())
        assert result == 'ok'

@pytest.mark.asyncio
async def test_activate_server_already_mounted():
    manager = ServerManager()
    with patch.object(manager, 'prepare_activation', return_value={'id': 'srv', 'type': 'stdio', 'command': 'uv', 'args': ['run']}), \
         patch.object(manager, 'has_member_server', return_value=True):
        result = await manager.activate_server('srv', MagicMock())
        assert "already mounted" in result


def test_deactivate_server_success():
    manager = ServerManager()
    with patch.object(manager, 'prepare_deactivation'), \
         patch('mcp_composer.member_servers.server_manager.NotFoundError', side_effect=Exception('fail')):
        cb = MagicMock()
        result = manager.deactivate_server('srv', cb)
        cb.assert_called_once_with('srv')
        assert "deactivated" in result 