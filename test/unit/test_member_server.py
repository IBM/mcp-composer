import pytest
from mcp_composer.core.member_servers.member_server import MemberMCPServer, HealthStatus
from unittest.mock import MagicMock
from mcp_composer.core.utils.validator import (
    ServerConfigValidator,
    AllServersValidator,
    ValidationError,
)


def test_member_mcp_server_instantiation():
    config = {
        "foo": "bar",
        "open_api": {"endpoint": "http://api", "spec_url": "http://spec"},
    }
    server = MemberMCPServer(id="test", type="openapi", config=config)
    assert server.id == "test"
    assert server.type == "openapi"
    assert server.config == config
    assert server.health_status == HealthStatus.healthy
    assert server.server is None
    assert isinstance(server.tags, set)
    assert isinstance(server.disabled_tools, list)
    assert isinstance(server.tools_description, dict)


def test_set_and_get_server():
    mcp_mock = MagicMock()
    server = MemberMCPServer(id="test", type="openapi", config={})
    server.set_server(mcp_mock)
    assert server.server is mcp_mock
    assert server.get_server() is mcp_mock


def test_get_server_raises_if_not_set():
    server = MemberMCPServer(id="test", type="openapi", config={})
    with pytest.raises(RuntimeError):
        server.get_server()


def test_to_dict_excludes_server():
    mcp_mock = MagicMock()
    server = MemberMCPServer(id="test", type="openapi", config={})
    server.set_server(mcp_mock)
    d = server.to_dict()
    assert "server" not in d
    assert d["id"] == "test"
    assert d["type"] == "openapi"


def test_server_config_validator_valid_openapi():
    config = {
        "id": "srv1",
        "type": "openapi",
        "open_api": {
            "endpoint": "http://api",
            "spec_url": "http://spec",
        },
    }
    validator = ServerConfigValidator(config)
    validator.validate()  # Should not raise


def test_server_config_validator_openapi_missing_endpoint():
    config = {
        "id": "srv1",
        "type": "openapi",
        "open_api": {
            "spec_url": "http://spec",
        },
    }
    validator = ServerConfigValidator(config)
    with pytest.raises(ValueError):
        validator.validate()


def test_server_config_validator_openapi_both_specs():
    config = {
        "id": "srv1",
        "type": "openapi",
        "open_api": {
            "endpoint": "http://api",
            "spec_url": "http://spec",
            "spec_filepath": "/tmp/spec.json",
        },
    }
    validator = ServerConfigValidator(config)
    with pytest.raises(ValueError):
        validator.validate()


def test_server_config_validator_stdio_missing_command():
    config = {
        "id": "srv1",
        "type": "stdio",
        "args": ["run"],
    }
    validator = ServerConfigValidator(config)
    with pytest.raises(ValidationError):
        validator.validate()


def test_server_config_validator_auth_missing_auth():
    config = {
        "id": "srv1",
        "type": "client",
        "auth_strategy": "apikey",
    }
    validator = ServerConfigValidator(config)
    with pytest.raises(ValidationError):
        validator.validate()


def test_server_config_validator_auth_missing_key():
    config = {
        "id": "srv1",
        "type": "client",
        "auth_strategy": "apikey",
        "auth": {},
    }
    validator = ServerConfigValidator(config)
    with pytest.raises(ValidationError):
        validator.validate()


def test_all_servers_validator_valid():
    configs = [
        {
            "id": "srv1",
            "type": "openapi",
            "open_api": {
                "endpoint": "http://api",
                "spec_url": "http://spec",
            },
        },
        {
            "id": "srv2",
            "type": "stdio",
            "command": "uv",
            "args": ["run"],
        },
    ]
    validator = AllServersValidator(configs)
    validator.validate_all()  # Should not raise


def test_all_servers_validator_invalid():
    configs = [
        {
            "id": "srv1",
            "type": "openapi",
            "open_api": {
                "spec_url": "http://spec",
            },
        }
    ]
    validator = AllServersValidator(configs)
    with pytest.raises(ValueError):
        validator.validate_all()
