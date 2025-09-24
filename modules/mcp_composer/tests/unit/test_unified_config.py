#!/usr/bin/env python3
"""Unit tests for unified configuration system."""

import json
import tempfile
import yaml
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
import pytest
import asyncio

from mcp_composer.core.config.config_loader import ConfigLoader, ConfigManager
from mcp_composer.core.config.unified_config import (
    UnifiedConfig,
    ConfigSection,
    ConfigValidationError,
    ServerConfig,
    MiddlewareConfig,
    PromptConfig,
    ToolConfig
)


class TestConfigLoader:
    """Test cases for ConfigLoader class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.composer = Mock()
        self.loader = ConfigLoader(self.composer)

    def test_detect_file_type_json(self):
        """Test JSON file type detection."""
        assert self.loader._detect_file_type("config.json") == "json"
        assert self.loader._detect_file_type("test.JSON") == "json"
        assert self.loader._detect_file_type("data.json") == "json"

    def test_detect_file_type_yaml(self):
        """Test YAML file type detection."""
        assert self.loader._detect_file_type("config.yaml") == "yaml"
        assert self.loader._detect_file_type("config.yml") == "yaml"
        assert self.loader._detect_file_type("test.YAML") == "yaml"
        assert self.loader._detect_file_type("data.YML") == "yaml"

    def test_detect_file_type_unknown(self):
        """Test unknown file type defaults to JSON."""
        result = self.loader._detect_file_type("config.txt")
        assert result == "json"

    def test_load_file_data_json(self):
        """Test loading JSON file data."""
        json_data = {"test": "value", "number": 42}
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(json_data, f)
            temp_path = f.name

        try:
            result = self.loader._load_file_data(temp_path)
            assert result == json_data
        finally:
            Path(temp_path).unlink()

    def test_load_file_data_yaml(self):
        """Test loading YAML file data."""
        yaml_data = {"test": "value", "number": 42, "list": [1, 2, 3]}
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(yaml_data, f)
            temp_path = f.name

        try:
            result = self.loader._load_file_data(temp_path)
            assert result == yaml_data
        finally:
            Path(temp_path).unlink()

    def test_load_file_data_invalid_json(self):
        """Test loading invalid JSON file raises error."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("invalid json content {")
            temp_path = f.name

        try:
            with pytest.raises(ConfigValidationError) as exc_info:
                self.loader._load_file_data(temp_path)
            assert "Invalid JSON" in str(exc_info.value)
        finally:
            Path(temp_path).unlink()

    def test_load_file_data_invalid_yaml(self):
        """Test loading invalid YAML file raises error."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("invalid: yaml: content: [test")
            temp_path = f.name

        try:
            with pytest.raises(ConfigValidationError) as exc_info:
                self.loader._load_file_data(temp_path)
            assert "Invalid YAML" in str(exc_info.value)
        finally:
            Path(temp_path).unlink()

    def test_load_file_data_file_not_found(self):
        """Test loading non-existent file raises error."""
        with pytest.raises(ConfigValidationError) as exc_info:
            self.loader._load_file_data("nonexistent.json")
        assert "Failed to load configuration file" in str(exc_info.value)

    def test_detect_config_type_from_data_unified(self):
        """Test detecting unified configuration type."""
        config_data = {
            "servers": [{"id": "test", "type": "http", "endpoint": "http://test"}],
            "middleware": [{"name": "test", "kind": "test", "mode": "enabled"}],
            "prompts": [{"name": "test", "description": "test", "template": "test"}],
            "tools": {"test": {"openapi": "3.0.3"}}
        }
        
        result = self.loader._detect_config_type_from_data(config_data, "test.json")
        assert result == "all"

    def test_detect_config_type_from_data_tools(self):
        """Test detecting tools configuration type."""
        config_data = {
            "tool1": {"openapi": "3.0.3", "info": {"title": "Test"}},
            "tool2": {"tool_type": "curl", "name": "test"}
        }
        
        result = self.loader._detect_config_type_from_data(config_data, "test.json")
        assert result == "tools"

    def test_detect_config_type_from_data_servers(self):
        """Test detecting servers configuration type."""
        config_data = [
            {"id": "server1", "type": "http", "endpoint": "http://test1"},
            {"id": "server2", "type": "sse", "endpoint": "http://test2"}
        ]
        
        result = self.loader._detect_config_type_from_data(config_data, "test.json")
        assert result == "servers"

    def test_detect_config_type_from_data_middleware(self):
        """Test detecting middleware configuration type."""
        config_data = [
            {"name": "mw1", "kind": "test1", "mode": "enabled"},
            {"name": "mw2", "kind": "test2", "mode": "disabled"}
        ]
        
        result = self.loader._detect_config_type_from_data(config_data, "test.json")
        assert result == "middleware"

    def test_detect_config_type_from_data_prompts(self):
        """Test detecting prompts configuration type."""
        config_data = [
            {"name": "prompt1", "description": "test1", "template": "template1"},
            {"name": "prompt2", "description": "test2", "template": "template2"}
        ]
        
        result = self.loader._detect_config_type_from_data(config_data, "test.json")
        assert result == "prompts"

    def test_detect_config_type_from_data_empty_list(self):
        """Test detecting empty list raises error."""
        config_data = []
        
        with pytest.raises(ConfigValidationError) as exc_info:
            self.loader._detect_config_type_from_data(config_data, "test.json")
        assert "Empty configuration file" in str(exc_info.value)

    def test_detect_config_type_from_data_invalid_type(self):
        """Test detecting invalid data type raises error."""
        config_data = "invalid string"
        
        with pytest.raises(ConfigValidationError) as exc_info:
            self.loader._detect_config_type_from_data(config_data, "test.json")
        assert "Configuration must be a JSON object or array" in str(exc_info.value)

    def test_detect_config_type_from_data_unknown_dict(self):
        """Test detecting unknown dictionary raises error."""
        config_data = {"unknown": "value", "other": "data"}
        
        with pytest.raises(ConfigValidationError) as exc_info:
            self.loader._detect_config_type_from_data(config_data, "test.json")
        assert "Unable to detect configuration type" in str(exc_info.value)

    def test_looks_like_tools_config_true(self):
        """Test tools config detection returns true for valid tools config."""
        config_data = {
            "tool1": {"openapi": "3.0.3", "info": {"title": "Test"}},
            "tool2": {"tool_type": "curl", "name": "test"}
        }
        
        result = self.loader._looks_like_tools_config(config_data)
        assert result is True

    def test_looks_like_tools_config_false(self):
        """Test tools config detection returns false for non-tools config."""
        config_data = {
            "server1": {"id": "test", "type": "http", "endpoint": "http://test"},
            "server2": {"id": "test2", "type": "sse", "endpoint": "http://test2"},
            "server3": {"id": "test3", "type": "stdio", "endpoint": "stdio://test3"},
            "server4": {"id": "test4", "type": "http", "endpoint": "http://test4"},
            "server5": {"id": "test5", "type": "sse", "endpoint": "http://test5"},
            "server6": {"id": "test6", "type": "http", "endpoint": "http://test6"},
            "server7": {"id": "test7", "type": "sse", "endpoint": "http://test7"},
            "server8": {"id": "test8", "type": "stdio", "endpoint": "stdio://test8"}
        }
        
        result = self.loader._looks_like_tools_config(config_data)
        assert result is False

    def test_looks_like_tools_config_mixed_content(self):
        """Test tools config detection with mixed content."""
        config_data = {
            "tool1": {"openapi": "3.0.3", "info": {"title": "Test"}},
            "server1": {"id": "test", "type": "http", "endpoint": "http://test"},
            "tool2": {"tool_type": "curl", "name": "test"}
        }
        
        result = self.loader._looks_like_tools_config(config_data)
        assert result is True  # Should detect as tools due to majority

    def test_looks_like_tools_config_empty(self):
        """Test tools config detection with empty data."""
        result = self.loader._looks_like_tools_config({})
        assert result is False

    def test_is_tool_config_openapi(self):
        """Test OpenAPI tool config detection."""
        config_dict = {"openapi": "3.0.3", "info": {"title": "Test"}}
        result = self.loader._is_tool_config(config_dict)
        assert result is True

    def test_is_tool_config_curl(self):
        """Test curl tool config detection."""
        config_dict = {"tool_type": "curl", "name": "test"}
        result = self.loader._is_tool_config(config_dict)
        assert result is True

    def test_is_tool_config_script(self):
        """Test script tool config detection."""
        config_dict = {"tool_type": "script", "name": "test"}
        result = self.loader._is_tool_config(config_dict)
        assert result is True

    def test_is_tool_config_server(self):
        """Test server config is not detected as tool."""
        config_dict = {"id": "test", "type": "http", "endpoint": "http://test"}
        result = self.loader._is_tool_config(config_dict)
        assert result is False

    def test_is_tool_config_other_tool_patterns(self):
        """Test other tool pattern detection."""
        config_dict = {"name": "test", "description": "test", "endpoint": "http://test"}
        result = self.loader._is_tool_config(config_dict)
        assert result is True

    def test_is_tool_config_invalid_type(self):
        """Test non-dict input returns False."""
        result = self.loader._is_tool_config("not a dict")
        assert result is False

    def test_validate_and_convert_list_valid(self):
        """Test validating and converting valid list."""
        data_list = [
            {"id": "server1", "type": "http", "endpoint": "http://test1"},
            {"id": "server2", "type": "sse", "endpoint": "http://test2"}
        ]
        
        result = self.loader._validate_and_convert_list(data_list, ServerConfig, "servers")
        assert len(result) == 2
        assert all(isinstance(item, ServerConfig) for item in result)

    def test_validate_and_convert_list_invalid_item(self):
        """Test validating list with invalid item raises error."""
        data_list = [
            {"id": "server1", "type": "http", "endpoint": "http://test1"},
            "invalid string"
        ]
        
        with pytest.raises(ConfigValidationError) as exc_info:
            self.loader._validate_and_convert_list(data_list, ServerConfig, "servers")
        assert "must be a dictionary" in str(exc_info.value)

    def test_validate_and_convert_dict_tools_skip_non_tool(self):
        """Test tools dict validation skips non-tool entries."""
        data_dict = {
            "tool1": {"openapi": "3.0.3", "info": {"title": "Test"}},
            "server1": {"id": "test", "type": "http", "endpoint": "http://test"},
            "tool2": {"tool_type": "curl", "name": "test"}
        }
        
        result = self.loader._validate_and_convert_dict(data_dict, ToolConfig, "tools")
        assert len(result) == 2  # Only tools, server skipped
        assert "tool1" in result
        assert "tool2" in result
        assert "server1" not in result

    def test_validate_and_convert_dict_invalid_tool(self):
        """Test tools dict validation with invalid tool raises error."""
        data_dict = {
            "tool1": {"openapi": "3.0.3", "info": {"title": "Test"}},
            "invalid_tool": "not a dict"
        }
        
        # For tools config, non-tool entries are skipped, so this should not raise an error
        result = self.loader._validate_and_convert_dict(data_dict, ToolConfig, "tools")
        assert len(result) == 1  # Only tool1 should be processed
        assert "tool1" in result
        assert "invalid_tool" not in result

    def test_prepare_server_config_oauth2_mapping(self):
        """Test OAuth2 field mapping in server config."""
        server_config = Mock()
        server_config.model_dump.return_value = {
            "id": "test",
            "type": "http",
            "endpoint": "http://test",
            "auth_strategy": "oauth2",
            "auth": {
                "clientId": "test_client",
                "clientSecret": "test_secret",
                "refreshToken": "test_token"
            }
        }
        
        result = self.loader._prepare_server_config(server_config)
        
        assert result["auth_strategy"] == "oauth"
        assert result["auth"]["client_id"] == "test_client"
        assert result["auth"]["client_secret"] == "test_secret"
        assert result["auth"]["refresh_token"] == "test_token"
        assert "clientId" not in result["auth"]
        assert "clientSecret" not in result["auth"]
        assert "refreshToken" not in result["auth"]

    def test_prepare_server_config_no_oauth2(self):
        """Test server config without OAuth2 remains unchanged."""
        server_config = Mock()
        server_config.model_dump.return_value = {
            "id": "test",
            "type": "http",
            "endpoint": "http://test"
        }
        
        result = self.loader._prepare_server_config(server_config)
        assert result == server_config.model_dump.return_value

    @pytest.mark.asyncio
    async def test_apply_servers_success(self):
        """Test successful server application."""
        servers = [
            Mock(id="server1", type="http"),
            Mock(id="server2", type="sse")
        ]
        
        self.composer._mount_member_server = AsyncMock(return_value="success")
        
        result = await self.loader._apply_servers(servers)
        
        assert result["total"] == 2
        assert len(result["registered"]) == 2
        assert len(result["failed"]) == 0
        assert self.composer._mount_member_server.call_count == 2

    @pytest.mark.asyncio
    async def test_apply_servers_failure(self):
        """Test server application with failures."""
        servers = [
            Mock(id="server1", type="http"),
            Mock(id="server2", type="sse")
        ]
        
        self.composer._mount_member_server = AsyncMock(side_effect=[Exception("Error"), "success"])
        
        result = await self.loader._apply_servers(servers)
        
        assert result["total"] == 2
        assert len(result["registered"]) == 1
        assert len(result["failed"]) == 1
        assert result["failed"][0]["error"] == "Error"

    @pytest.mark.asyncio
    async def test_apply_tools_success(self):
        """Test successful tools application."""
        tools = {
            "tool1": Mock(model_dump=Mock(return_value={"openapi": "3.0.3"})),
            "tool2": Mock(model_dump=Mock(return_value={"tool_type": "curl", "name": "test"}))
        }
        
        self.composer.add_tools_from_openapi = AsyncMock()
        self.composer.add_tools_from_curl = AsyncMock()
        
        result = await self.loader._apply_tools(tools)
        
        assert result["total"] == 2
        assert len(result["registered"]) == 2
        assert len(result["failed"]) == 0
        self.composer.add_tools_from_openapi.assert_called_once()
        self.composer.add_tools_from_curl.assert_called_once()

    @pytest.mark.asyncio
    async def test_apply_tools_skip_non_tool(self):
        """Test tools application skips non-tool entries."""
        tools = {
            "tool1": Mock(model_dump=Mock(return_value={"openapi": "3.0.3"})),
            "server1": Mock(model_dump=Mock(return_value={"id": "test", "type": "http", "endpoint": "http://test"}))
        }
        
        self.composer.add_tools_from_openapi = AsyncMock()
        
        result = await self.loader._apply_tools(tools)
        
        assert result["total"] == 2
        assert len(result["registered"]) == 1
        assert len(result["skipped"]) == 1
        assert result["skipped"][0]["name"] == "server1"

    @pytest.mark.asyncio
    async def test_apply_tools_unknown_type(self):
        """Test tools application with unknown tool type."""
        tools = {
            "tool1": Mock(model_dump=Mock(return_value={"tool_type": "unknown", "name": "test"}))
        }
        
        result = await self.loader._apply_tools(tools)
        
        assert result["total"] == 1
        assert len(result["failed"]) == 1
        assert "Unknown tool type" in result["failed"][0]["error"]

    @pytest.mark.asyncio
    async def test_apply_prompts_success(self):
        """Test successful prompts application."""
        prompts = [
            Mock(name="prompt1", description="test1", template="template1", arguments=[]),
            Mock(name="prompt2", description="test2", template="template2", arguments=[])
        ]
        
        self.composer._prompt_manager.add_prompts = Mock(return_value=["prompt1", "prompt2"])
        
        result = await self.loader._apply_prompts(prompts)
        
        assert result["total"] == 2
        assert len(result["registered"]) == 2
        assert len(result["failed"]) == 0
        self.composer._prompt_manager.add_prompts.assert_called_once()

    def test_load_single_section_servers(self):
        """Test loading single section servers configuration."""
        config_data = [
            {"id": "server1", "type": "http", "endpoint": "http://test1"},
            {"id": "server2", "type": "sse", "endpoint": "http://test2"}
        ]
        
        result = self.loader._load_single_section(config_data, "servers", "test.json")
        
        assert isinstance(result, UnifiedConfig)
        assert len(result.servers) == 2
        assert len(result.middleware) == 0
        assert len(result.prompts) == 0
        assert len(result.tools) == 0

    def test_load_single_section_tools(self):
        """Test loading single section tools configuration."""
        config_data = {
            "tool1": {"openapi": "3.0.3", "info": {"title": "Test"}},
            "tool2": {"tool_type": "curl", "name": "test"}
        }
        
        result = self.loader._load_single_section(config_data, "tools", "test.json")
        
        assert isinstance(result, UnifiedConfig)
        assert len(result.servers) == 0
        assert len(result.middleware) == 0
        assert len(result.prompts) == 0
        assert len(result.tools) == 2

    def test_load_single_section_invalid_type(self):
        """Test loading single section with invalid type raises error."""
        config_data = [{"id": "server1", "type": "http", "endpoint": "http://test1"}]
        
        with pytest.raises(ConfigValidationError) as exc_info:
            self.loader._load_single_section(config_data, "invalid", "test.json")
        assert "Unsupported config type" in str(exc_info.value)

    def test_load_single_section_invalid_data_type(self):
        """Test loading single section with invalid data type raises error."""
        config_data = "invalid string"
        
        with pytest.raises(ConfigValidationError) as exc_info:
            self.loader._load_single_section(config_data, "servers", "test.json")
        assert "must be a list or dictionary" in str(exc_info.value)


class TestConfigManager:
    """Test cases for ConfigManager class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.composer = Mock()
        self.manager = ConfigManager(self.composer)

    @pytest.mark.asyncio
    async def test_load_and_apply_success(self):
        """Test successful load and apply."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"servers": [{"id": "test", "type": "http", "endpoint": "http://test"}]}, f)
            temp_path = f.name

        try:
            with patch.object(self.manager.loader, 'apply_config', new_callable=AsyncMock) as mock_apply:
                mock_apply.return_value = {"servers": {"registered": 1, "failed": 0}}
                
                result = await self.manager.load_and_apply(temp_path, config_type="all")
                
                assert "servers" in result
                mock_apply.assert_called_once()
        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    async def test_load_and_apply_failure(self):
        """Test load and apply with failure."""
        with pytest.raises(ConfigValidationError):
            await self.manager.load_and_apply("nonexistent.json")

    def test_validate_config_file_valid(self):
        """Test validating valid configuration file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"servers": [{"id": "test", "type": "http", "endpoint": "http://test"}]}, f)
            temp_path = f.name

        try:
            result = self.manager.validate_config_file(temp_path)
            assert result is True
        finally:
            Path(temp_path).unlink()

    def test_validate_config_file_invalid(self):
        """Test validating invalid configuration file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("invalid json")
            temp_path = f.name

        try:
            result = self.manager.validate_config_file(temp_path)
            assert result is False
        finally:
            Path(temp_path).unlink()


class TestUnifiedConfigIntegration:
    """Integration tests for unified configuration system."""

    def setup_method(self):
        """Set up test fixtures."""
        self.composer = Mock()
        self.loader = ConfigLoader(self.composer)

    def test_full_unified_config_json(self):
        """Test loading full unified configuration from JSON."""
        config_data = {
            "servers": [
                {"id": "server1", "type": "http", "endpoint": "http://test1"},
                {"id": "server2", "type": "sse", "endpoint": "http://test2"}
            ],
            "middleware": [
                {"name": "mw1", "kind": "mcp_composer.middleware.test.TestMiddleware", "mode": "enabled", "priority": 10, "applied_hooks": ["on_call_tool"]}
            ],
            "prompts": [
                {"name": "prompt1", "description": "test1", "template": "template1"}
            ],
            "tools": {
                "tool1": {
                    "openapi": "3.0.3", 
                    "info": {"title": "Test"},
                    "paths": {
                        "/test": {
                            "get": {
                                "summary": "Test endpoint",
                                "operationId": "test_operation"
                            }
                        }
                    }
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name

        try:
            result = self.loader.load_from_file(temp_path, "all")
            
            assert isinstance(result, UnifiedConfig)
            assert len(result.servers) == 2
            assert len(result.middleware) == 1
            assert len(result.prompts) == 1
            assert len(result.tools) == 1
        finally:
            Path(temp_path).unlink()

    def test_full_unified_config_yaml(self):
        """Test loading full unified configuration from YAML."""
        config_data = {
            "servers": [
                {"id": "server1", "type": "http", "endpoint": "http://test1"},
                {"id": "server2", "type": "sse", "endpoint": "http://test2"}
            ],
            "middleware": [
                {"name": "mw1", "kind": "mcp_composer.middleware.test.TestMiddleware", "mode": "enabled", "priority": 10, "applied_hooks": ["on_call_tool"]}
            ],
            "prompts": [
                {"name": "prompt1", "description": "test1", "template": "template1"}
            ],
            "tools": {
                "tool1": {
                    "openapi": "3.0.3", 
                    "info": {"title": "Test"},
                    "paths": {
                        "/test": {
                            "get": {
                                "summary": "Test endpoint",
                                "operationId": "test_operation"
                            }
                        }
                    }
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name

        try:
            result = self.loader.load_from_file(temp_path, "all")
            
            assert isinstance(result, UnifiedConfig)
            assert len(result.servers) == 2
            assert len(result.middleware) == 1
            assert len(result.prompts) == 1
            assert len(result.tools) == 1
        finally:
            Path(temp_path).unlink()

    def test_mixed_content_tools_config(self):
        """Test handling mixed content in tools configuration."""
        config_data = {
            "tool1": {"openapi": "3.0.3", "info": {"title": "Test"}},
            "server1": {"id": "test", "type": "http", "endpoint": "http://test"},
            "tool2": {"tool_type": "curl", "name": "test"},
            "server_list": [{"id": "test2", "type": "sse", "endpoint": "http://test2"}]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name

        try:
            result = self.loader.load_from_file(temp_path, "tools")
            
            assert isinstance(result, UnifiedConfig)
            assert len(result.tools) == 2  # Only tools, servers skipped
            assert "tool1" in result.tools
            assert "tool2" in result.tools
            assert "server1" not in result.tools
            assert "server_list" not in result.tools
        finally:
            Path(temp_path).unlink()

    def test_auto_detect_config_type(self):
        """Test auto-detection of configuration type."""
        # Test servers
        servers_data = [{"id": "server1", "type": "http", "endpoint": "http://test1"}]
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(servers_data, f)
            temp_path = f.name

        try:
            result = self.loader.detect_config_type(temp_path)
            assert result == "servers"
        finally:
            Path(temp_path).unlink()

        # Test tools
        tools_data = {"tool1": {"openapi": "3.0.3", "info": {"title": "Test"}}}
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(tools_data, f)
            temp_path = f.name

        try:
            result = self.loader.detect_config_type(temp_path)
            assert result == "tools"
        finally:
            Path(temp_path).unlink()

    def test_file_caching(self):
        """Test file caching functionality."""
        config_data = {"servers": [{"id": "server1", "type": "http", "endpoint": "http://test1"}]}
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name

        try:
            # First load
            result1 = self.loader.load_from_file(temp_path, "all")
            
            # Second load should use cache
            with patch('builtins.open') as mock_open:
                result2 = self.loader.load_from_file(temp_path, "all")
                mock_open.assert_not_called()  # Should not open file again
            
            assert result1.servers[0].id == result2.servers[0].id
        finally:
            Path(temp_path).unlink()


if __name__ == "__main__":
    pytest.main([__file__])
