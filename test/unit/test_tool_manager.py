import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from mcp_composer.tools.tool_manager import MCPToolManager
from mcp_composer.member_servers.member_server import MemberMCPServer, HealthStatus
from fastmcp.exceptions import ToolError

@pytest.fixture
def tool_manager():
    server_manager = MagicMock()
    database = MagicMock()
    return MCPToolManager(server_manager=server_manager, database=database)

def test_unmount_removes_server(tool_manager):
    mock_server = MagicMock()
    mock_server.prefix = 'server1'
    tool_manager._mounted_servers = [mock_server, MagicMock(prefix='other')]
    tool_manager.unmount('server1')
    assert all(s.prefix != 'server1' for s in tool_manager._mounted_servers)

def test_filter_tools_removes_and_updates():
    tool_manager = MCPToolManager(server_manager=MagicMock(), database=MagicMock())
    tool1 = MagicMock()
    tool2 = MagicMock()
    tools = {'a': tool1, 'b': tool2}
    member1 = MagicMock(health_status=HealthStatus.healthy, disabled_tools=['a'], tools_description={'b': 'desc'})
    tool_manager.server_manager.list.return_value = [member1]
    filtered = tool_manager.filter_tools(tools)
    assert 'a' not in filtered
    assert filtered['b'].description == 'desc'

def test_filter_tools_handles_no_config():
    tool_manager = MCPToolManager(server_manager=MagicMock(), database=MagicMock())
    tool_manager.server_manager.list.return_value = []
    tools = {'a': MagicMock()}
    assert tool_manager.filter_tools(tools) == tools

def test_filter_tools_handles_unhealthy():
    tool_manager = MCPToolManager(server_manager=MagicMock(), database=MagicMock())
    member1 = MagicMock(health_status=HealthStatus.unhealthy, disabled_tools=['a'], tools_description={})
    tool_manager.server_manager.list.return_value = [member1]
    tools = {'a': MagicMock()}
    assert tool_manager.filter_tools(tools) == tools

def test_filter_tools_exception():
    tool_manager = MCPToolManager(server_manager=MagicMock(), database=MagicMock())
    tool_manager.server_manager.list.side_effect = Exception('fail')
    with pytest.raises(Exception):
        tool_manager.filter_tools({'a': MagicMock()})

@pytest.mark.asyncio
async def test_load_custom_tools_handles_import(monkeypatch):
    tool_manager = MCPToolManager(server_manager=MagicMock(), database=MagicMock())
    monkeypatch.setattr('mcp_composer.tools.tool_manager.custom_tools', None)
    monkeypatch.setattr('mcp_composer.tools.tool_manager.generate_tool_from_curl', AsyncMock(return_value=[]))
    monkeypatch.setattr('mcp_composer.tools.tool_manager.generate_tool_from_open_api', AsyncMock(return_value={}))
    result = await tool_manager.load_custom_tools()
    assert isinstance(result, dict)

@pytest.mark.asyncio
async def test_fetch_server_tools_and_update_desc():
    tool_manager = MCPToolManager(server_manager=MagicMock(), database=MagicMock())
    mock_server = MagicMock()
    mock_server.id = 's1'
    mounted = MagicMock(prefix='s1')
    mounted.server.get_tools = AsyncMock(return_value={'t1': MagicMock()})
    tool_manager._mounted_servers = [mounted]
    result = await tool_manager.fetch_server_tools(mock_server, remove=['s1_t1'], description={'s1_t1': 'desc'})
    assert 's1_t1' not in result or result['s1_t1'].description == 'desc'

@pytest.mark.asyncio
async def test_get_all_tools_specific(monkeypatch):
    tool_manager = MCPToolManager(server_manager=MagicMock(), database=MagicMock())
    tool_manager.server_manager.get.return_value = MagicMock()
    tool_manager.server_manager.get_document.return_value = MagicMock()
    monkeypatch.setattr('mcp_composer.tools.tool_manager.get_server_doc_info', lambda doc: ([], {}))
    monkeypatch.setattr('mcp_composer.tools.tool_manager.MCPToolManager.fetch_server_tools', AsyncMock(return_value={'a': MagicMock()}))
    result = await tool_manager.get_all_tools(server_id='s1')
    assert 'a' in result

@pytest.mark.asyncio
async def test_get_all_tools_default(monkeypatch):
    tool_manager = MCPToolManager(server_manager=MagicMock(), database=MagicMock())
    monkeypatch.setattr('mcp_composer.tools.tool_manager.MCPToolManager.get_tools', AsyncMock(return_value={'a': MagicMock()}))
    result = await tool_manager.get_all_tools()
    assert 'a' in result 