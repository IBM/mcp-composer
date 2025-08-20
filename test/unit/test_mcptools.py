import pytest
from mcp_composer_client import mcptools
from unittest.mock import patch, mock_open, MagicMock
import os


def test_mcp_base_config():
    cfg = mcptools.MCPBaseConfig(description="desc", filters=None, excludes=None)
    assert cfg.description == "desc"
    assert cfg.enabled is True


def test_mcp_remote_config():
    cfg = mcptools.MCPRemoteConfig(
        description="desc", mcp_composer_url="url", type="sse", filters=None, excludes=None
    )
    assert cfg.mcp_composer_url == "url"
    assert cfg.type == "sse"


def test_tools_init_env(monkeypatch):
    monkeypatch.setenv("USER_CONFIG_FILE", "no")
    monkeypatch.setenv("MCP_BASE_URL", "http://test")
    tools = mcptools.Tools()
    assert "MCP_composer" in tools._config


@patch("builtins.open", new_callable=mock_open, read_data="remote_servers: {}\nstdio_servers: {}\noas_servers: {}\n")
def test_tools_init_file(mock_file, monkeypatch):
    monkeypatch.setenv("USER_CONFIG_FILE", "yes")
    tools = mcptools.Tools()
    assert isinstance(tools._config, dict)
