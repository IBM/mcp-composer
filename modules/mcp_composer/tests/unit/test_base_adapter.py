"""Test module for base_adapter.py"""

from abc import ABC
import pytest
from mcp_composer.core.settings.base_adapter import SecretAdapter


class TestSecretAdapter:
    """Test cases for SecretAdapter"""

    def test_secret_adapter_is_abstract(self):
        """Test that SecretAdapter is an abstract base class"""
        assert issubclass(SecretAdapter, ABC)

    def test_secret_adapter_abstract_methods(self):
        """Test that SecretAdapter has all required abstract methods"""
        abstract_methods = SecretAdapter.__abstractmethods__

        expected_methods = {
            "load_config",
            "save_config",
            "get_all_versions",
            "get_latest_version",
            "get_version_by_id",
            "rollback",
        }

        assert abstract_methods == expected_methods

    def test_cannot_instantiate_secret_adapter(self):
        """Test that SecretAdapter cannot be instantiated directly"""
        with pytest.raises(TypeError):
            SecretAdapter()

    def test_concrete_implementation_required(self):
        """Test that concrete implementations must implement all abstract methods"""

        class IncompleteSecretAdapter(SecretAdapter):
            def load_config(self, server_id: str):
                return {}

        # Should raise TypeError because not all abstract methods are implemented
        with pytest.raises(TypeError):
            IncompleteSecretAdapter()

    def test_complete_concrete_implementation(self):
        """Test that a complete concrete implementation works"""

        class MockSecretAdapter(SecretAdapter):
            def __init__(self):
                self.configs = {}
                self.versions = {}

            def load_config(self, server_id: str):
                return self.configs.get(server_id, {})

            def save_config(self, server_id: str, versions):
                self.versions[server_id] = versions

            def get_all_versions(self, server_id: str):
                return self.versions.get(server_id, [])

            def get_latest_version(self, server_id: str):
                versions = self.versions.get(server_id, [])
                return versions[-1] if versions else None

            def get_version_by_id(self, server_id: str, version_id: str):
                versions = self.versions.get(server_id, [])
                for version in versions:
                    if version.get("id") == version_id:
                        return version
                return None

            def rollback(self, server_id: str, version_id: str):
                version = self.get_version_by_id(server_id, version_id)
                if version is None:
                    raise ValueError(f"Version {version_id} not found")
                self.configs[server_id] = version
                return version

        # Should work without raising TypeError
        adapter = MockSecretAdapter()
        assert isinstance(adapter, SecretAdapter)

        # Test functionality
        adapter.save_config("server1", [{"id": "v1", "config": {"key": "value1"}}])
        assert adapter.get_all_versions("server1") == [{"id": "v1", "config": {"key": "value1"}}]
        assert adapter.get_latest_version("server1") == {
            "id": "v1",
            "config": {"key": "value1"},
        }

    def test_method_signatures(self):
        """Test that abstract methods have correct signatures"""
        from typing import Dict, List, Optional, Any

        # Test load_config
        sig = SecretAdapter.load_config.__annotations__
        assert "server_id" in sig
        assert sig["server_id"] == str
        assert "return" in sig
        assert sig["return"] == Dict[str, Any]

        # Test save_config
        sig = SecretAdapter.save_config.__annotations__
        assert "server_id" in sig
        assert sig["server_id"] == str
        assert "versions" in sig
        assert sig["versions"] == List[Dict[str, Any]]

        # Test get_all_versions
        sig = SecretAdapter.get_all_versions.__annotations__
        assert "server_id" in sig
        assert sig["server_id"] == str
        assert "return" in sig
        assert sig["return"] == List[Dict[str, Any]]

        # Test get_latest_version
        sig = SecretAdapter.get_latest_version.__annotations__
        assert "server_id" in sig
        assert sig["server_id"] == str
        assert "return" in sig
        assert sig["return"] == Optional[Dict[str, Any]]

        # Test get_version_by_id
        sig = SecretAdapter.get_version_by_id.__annotations__
        assert "server_id" in sig
        assert sig["server_id"] == str
        assert "version_id" in sig
        assert sig["version_id"] == str
        assert "return" in sig
        assert sig["return"] == Optional[Dict[str, Any]]

        # Test rollback
        sig = SecretAdapter.rollback.__annotations__
        assert "server_id" in sig
        assert sig["server_id"] == str
        assert "version_id" in sig
        assert sig["version_id"] == str
        assert "return" in sig
        assert sig["return"] == Dict[str, Any]

    def test_docstrings_exist(self):
        """Test that methods have docstrings"""
        # Test load_config docstring
        doc = SecretAdapter.load_config.__doc__
        assert doc is not None
        assert "Return the latest config for the server" in doc

        # Test save_config docstring
        doc = SecretAdapter.save_config.__doc__
        assert doc is not None
        assert "Save a list of versions for the given server" in doc

        # Test get_all_versions docstring
        doc = SecretAdapter.get_all_versions.__doc__
        assert doc is not None
        assert "Return all versions for a given server" in doc

        # Test get_latest_version docstring
        doc = SecretAdapter.get_latest_version.__doc__
        assert doc is not None
        assert "Return the latest version of the config" in doc

        # Test get_version_by_id docstring
        doc = SecretAdapter.get_version_by_id.__doc__
        assert doc is not None
        assert "Return a specific version by ID" in doc

        # Test rollback docstring
        doc = SecretAdapter.rollback.__doc__
        assert doc is not None
        assert "Roll back the server config to a previous version" in doc
        assert "Returns:" in doc
        assert "Raises:" in doc
        assert "ValueError:" in doc

    def test_class_docstring(self):
        """Test that SecretAdapter has class docstring"""
        doc = SecretAdapter.__doc__
        assert doc is not None
        assert "Abstract adapter interface for secret/config version storage" in doc

    def test_inheritance_chain(self):
        """Test that SecretAdapter properly inherits from ABC"""
        assert SecretAdapter.__bases__ == (ABC,)

        # Test that it's abstract
        assert hasattr(SecretAdapter, "__abstractmethods__")
        assert len(SecretAdapter.__abstractmethods__) > 0

    def test_method_abstraction(self):
        """Test that all methods are properly abstract"""
        for method_name in SecretAdapter.__abstractmethods__:
            method = getattr(SecretAdapter, method_name)
            assert hasattr(method, "__isabstractmethod__")
            assert method.__isabstractmethod__ is True

    def test_concrete_implementation_with_error_handling(self):
        """Test concrete implementation with proper error handling"""

        class ErrorHandlingSecretAdapter(SecretAdapter):
            def __init__(self):
                self.configs = {}
                self.versions = {}

            def load_config(self, server_id: str):
                return self.configs.get(server_id, {})

            def save_config(self, server_id: str, versions):
                if not isinstance(versions, list):
                    raise ValueError("Versions must be a list")
                self.versions[server_id] = versions

            def get_all_versions(self, server_id: str):
                return self.versions.get(server_id, [])

            def get_latest_version(self, server_id: str):
                versions = self.versions.get(server_id, [])
                return versions[-1] if versions else None

            def get_version_by_id(self, server_id: str, version_id: str):
                versions = self.versions.get(server_id, [])
                for version in versions:
                    if version.get("id") == version_id:
                        return version
                return None

            def rollback(self, server_id: str, version_id: str):
                version = self.get_version_by_id(server_id, version_id)
                if version is None:
                    raise ValueError(f"Version {version_id} not found for server {server_id}")
                self.configs[server_id] = version
                return version

        adapter = ErrorHandlingSecretAdapter()

        # Test error handling in save_config
        with pytest.raises(ValueError, match="Versions must be a list"):
            adapter.save_config("server1", "not_a_list")

        # Test error handling in rollback
        with pytest.raises(ValueError, match="Version v1 not found for server server1"):
            adapter.rollback("server1", "v1")

        # Test successful operations
        adapter.save_config("server1", [{"id": "v1", "config": {"key": "value1"}}])
        result = adapter.rollback("server1", "v1")
        assert result == {"id": "v1", "config": {"key": "value1"}}

    def test_concrete_implementation_with_complex_data(self):
        """Test concrete implementation with complex data structures"""

        class ComplexSecretAdapter(SecretAdapter):
            def __init__(self):
                self.configs = {}
                self.versions = {}

            def load_config(self, server_id: str):
                return self.configs.get(server_id, {})

            def save_config(self, server_id: str, versions):
                self.versions[server_id] = versions

            def get_all_versions(self, server_id: str):
                return self.versions.get(server_id, [])

            def get_latest_version(self, server_id: str):
                versions = self.versions.get(server_id, [])
                return versions[-1] if versions else None

            def get_version_by_id(self, server_id: str, version_id: str):
                versions = self.versions.get(server_id, [])
                for version in versions:
                    if version.get("id") == version_id:
                        return version
                return None

            def rollback(self, server_id: str, version_id: str):
                version = self.get_version_by_id(server_id, version_id)
                if version is None:
                    raise ValueError(f"Version {version_id} not found")
                self.configs[server_id] = version
                return version

        adapter = ComplexSecretAdapter()

        # Test with complex configuration data
        complex_config = {
            "id": "v1",
            "config": {
                "server": {"host": "localhost", "port": 8080, "ssl": True},
                "auth": {"type": "bearer", "token": "secret_token"},
                "tools": [
                    {"name": "tool1", "enabled": True},
                    {"name": "tool2", "enabled": False},
                ],
                "metadata": {
                    "created_by": "admin",
                    "created_at": "2023-01-01T00:00:00Z",
                    "tags": ["production", "api"],
                },
            },
        }

        adapter.save_config("complex_server", [complex_config])

        # Test get_all_versions
        versions = adapter.get_all_versions("complex_server")
        assert len(versions) == 1
        assert versions[0] == complex_config

        # Test get_latest_version
        latest = adapter.get_latest_version("complex_server")
        assert latest == complex_config

        # Test get_version_by_id
        version = adapter.get_version_by_id("complex_server", "v1")
        assert version == complex_config

        # Test rollback
        result = adapter.rollback("complex_server", "v1")
        assert result == complex_config

        # Test load_config after rollback
        loaded_config = adapter.load_config("complex_server")
        assert loaded_config == complex_config
