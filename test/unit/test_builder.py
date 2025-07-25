import pytest
from unittest.mock import patch
from mcp_composer.member_servers.builder import MCPServerBuilder
from mcp_composer.utils import MemberServerType, ConfigKey

@pytest.mark.asyncio
async def test_build_from_client_success():
    config = {ConfigKey.ID: 'srv', ConfigKey.TYPE: MemberServerType.CLIENT, ConfigKey.ENDPOINT: 'http://api'}
    builder = MCPServerBuilder(config)
    with patch('mcp_composer.member_servers.builder.Client') as mock_client, \
         patch('mcp_composer.member_servers.builder.FastMCP') as mock_fastmcp:
        mock_fastmcp.as_proxy.return_value = 'proxy'
        result = await builder._build_from_client()
        assert result == 'proxy'

@pytest.mark.asyncio
async def test_build_from_transport_http():
    config = {ConfigKey.ID: 'srv', ConfigKey.TYPE: MemberServerType.HTTP, ConfigKey.ENDPOINT: 'http://api'}
    builder = MCPServerBuilder(config)
    with patch('mcp_composer.member_servers.builder.StreamableHttpTransport') as mock_transport, \
         patch('mcp_composer.member_servers.builder.Client') as mock_client, \
         patch('mcp_composer.member_servers.builder.FastMCP') as mock_fastmcp:
        mock_fastmcp.as_proxy.return_value = 'proxy'
        result = await builder._build_from_transport(MemberServerType.HTTP)
        assert result == 'proxy'

@pytest.mark.asyncio
async def test_build_from_transport_invalid():
    config = {ConfigKey.ID: 'srv', ConfigKey.TYPE: 'invalid'}
    builder = MCPServerBuilder(config)
    with pytest.raises(ValueError):
        await builder._build_from_transport('invalid')

@pytest.mark.asyncio
async def test_build_invalid_type():
    config = {ConfigKey.ID: 'srv', ConfigKey.TYPE: 'invalid'}
    builder = MCPServerBuilder(config)
    with pytest.raises(ValueError):
        await builder.build() 