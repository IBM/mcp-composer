import pytest
from unittest.mock import patch, MagicMock
from mcp_composer.composer import MCPComposer

@patch('mcp_composer.composer.ConfigManager')
@patch('mcp_composer.composer.get_version_adapter')
@patch('mcp_composer.composer.ServerManager')
@patch('mcp_composer.composer.MCPToolManager')
@patch('mcp_composer.composer.LocalFileAdapter')
@patch('mcp_composer.composer.MCPPromptManager')
def test_mcpcomposer_init(
    mock_prompt_manager,
    mock_local_file_adapter,
    mock_tool_manager,
    mock_server_manager,
    mock_get_version_adapter,
    mock_config_manager
):
    # Arrange
    mock_get_version_adapter.return_value = MagicMock()
    mock_config_manager.return_value = MagicMock()
    mock_server_manager.return_value = MagicMock(load_all_servers_db=MagicMock(return_value=[]))
    mock_tool_manager.return_value = MagicMock()
    mock_local_file_adapter.return_value = MagicMock()
    mock_prompt_manager.return_value = MagicMock()

    # Act
    composer = MCPComposer()

    # Assert
    assert isinstance(composer, MCPComposer)
    assert hasattr(composer, '_server_manager')
    assert hasattr(composer, '_tool_manager')
    assert hasattr(composer, '_config_manager')
    assert hasattr(composer, '_prompt_manager')

def test_mcpcomposer_config_validation():
    # Valid config
    with patch('mcp_composer.composer.ConfigManager'), \
         patch('mcp_composer.composer.get_version_adapter'), \
         patch('mcp_composer.composer.ServerManager'), \
         patch('mcp_composer.composer.MCPToolManager'), \
         patch('mcp_composer.composer.LocalFileAdapter'), \
         patch('mcp_composer.composer.MCPPromptManager'), \
         patch('mcp_composer.composer.AllServersValidator') as mock_validator:
        mock_validator.return_value.validate_all.return_value = True
        config = [{'id': 'server1', 'name': 'TestServer'}]
        composer = MCPComposer(config=config)
        assert composer._config == config
