"""Test module for database.py"""

import pytest
from abc import ABC
from mcp_composer.store.database import DatabaseInterface


class TestDatabaseInterface:
    """Test cases for DatabaseInterface abstract class"""

    def test_database_interface_is_abstract(self):
        """Test that DatabaseInterface is an abstract base class"""
        assert issubclass(DatabaseInterface, ABC)

    def test_database_interface_abstract_methods(self):
        """Test that DatabaseInterface has all required abstract methods"""
        abstract_methods = DatabaseInterface.__abstractmethods__

        expected_methods = {
            "load_all_servers",
            "add_server",
            "remove_server",
            "get_document",
            "enable_tools",
            "disable_tools",
            "update_tool_description",
            "enable_prompts",
            "disable_prompts",
            "enable_resources",
            "disable_resources",
            "mark_deactivated",
            "get_server_status",
            "update_server_config",
            "load_all_resources",
            "upsert_resource",
            "delete_resource",
            "load_all_prompts",
            "add_prompt",
            "remove_prompt",
            "get_prompt",
        }

        assert abstract_methods == expected_methods

    def test_cannot_instantiate_database_interface(self):
        """Test that DatabaseInterface cannot be instantiated directly"""
        with pytest.raises(TypeError):
            DatabaseInterface()

    def test_concrete_implementation_required(self):
        """Test that concrete implementations must implement all abstract methods"""

        class IncompleteDatabase(DatabaseInterface):
            def load_all_servers(self):
                return []

        # Should raise TypeError because not all abstract methods are implemented
        with pytest.raises(TypeError):
            IncompleteDatabase()

    def test_complete_concrete_implementation(self):
        """Test that a complete concrete implementation works"""

        class MockDatabase(DatabaseInterface):
            def load_all_servers(self):
                return []

            def add_server(self, config):
                pass

            def remove_server(self, server_id):
                pass

            def get_document(self, server_id):
                return {}

            def enable_tools(self, tools, server_id):
                pass

            def disable_tools(self, tools, server_id):
                pass

            def update_tool_description(self, tool, description, server_id):
                pass

            def enable_prompts(self, prompts, server_id):
                pass

            def disable_prompts(self, prompts, server_id):
                pass

            def enable_resources(self, resources, server_id):
                pass

            def disable_resources(self, resources, server_id):
                pass

            def mark_deactivated(self, server_id):
                pass

            def get_server_status(self, server_id):
                return "active"

            def update_server_config(self, config):
                pass

            def load_all_resources(self):
                return []

            def upsert_resource(self, record):
                pass

            def delete_resource(self, storage_id):
                pass

            def load_all_prompts(self):
                return []

            def add_prompt(self, prompt):
                pass

            def remove_prompt(self, prompt_name):
                pass

            def get_prompt(self, prompt_name):
                return {}

        # Should work without raising TypeError
        db = MockDatabase()
        assert isinstance(db, DatabaseInterface)
        assert db.load_all_servers() == []
        assert db.get_server_status("test") == "active"

    def test_method_signatures(self):
        """Test that abstract methods have correct signatures"""
        from typing import List, Dict

        # Test load_all_servers
        sig = DatabaseInterface.load_all_servers.__annotations__
        assert "return" in sig
        assert sig["return"] == List[Dict]

        # Test add_server
        sig = DatabaseInterface.add_server.__annotations__
        assert "config" in sig
        assert sig["config"] == Dict

        # Test remove_server
        sig = DatabaseInterface.remove_server.__annotations__
        assert "server_id" in sig
        assert sig["server_id"] == str  # noqa: E721

        # Test get_document
        sig = DatabaseInterface.get_document.__annotations__
        assert "server_id" in sig
        assert sig["server_id"] == str  # noqa: E721
        assert "return" in sig
        assert sig["return"] == Dict

        # Test enable_tools
        sig = DatabaseInterface.enable_tools.__annotations__
        assert "tools" in sig
        assert sig["tools"] == list[str]
        assert "server_id" in sig
        assert sig["server_id"] == str  # noqa: E721

        # Test disable_tools
        sig = DatabaseInterface.disable_tools.__annotations__
        assert "tools" in sig
        assert sig["tools"] == list[str]
        assert "server_id" in sig
        assert sig["server_id"] == str  # noqa: E721

        # Test update_tool_description
        sig = DatabaseInterface.update_tool_description.__annotations__
        assert "tool" in sig
        assert sig["tool"] == str  # noqa: E721
        assert "description" in sig
        assert sig["description"] == str  # noqa: E721
        assert "server_id" in sig
        assert sig["server_id"] == str  # noqa: E721

        # Test enable_prompts
        sig = DatabaseInterface.enable_prompts.__annotations__
        assert "prompts" in sig
        assert sig["prompts"] == list[str]
        assert "server_id" in sig
        assert sig["server_id"] == str  # noqa: E721

        # Test disable_prompts
        sig = DatabaseInterface.disable_prompts.__annotations__
        assert "prompts" in sig
        assert sig["prompts"] == list[str]
        assert "server_id" in sig
        assert sig["server_id"] == str  # noqa: E721

        # Test enable_resources
        sig = DatabaseInterface.enable_resources.__annotations__
        assert "resources" in sig
        assert sig["resources"] == list[str]
        assert "server_id" in sig
        assert sig["server_id"] == str  # noqa: E721

        # Test disable_resources
        sig = DatabaseInterface.disable_resources.__annotations__
        assert "resources" in sig
        assert sig["resources"] == list[str]
        assert "server_id" in sig
        assert sig["server_id"] == str  # noqa: E721

        # Test mark_deactivated
        sig = DatabaseInterface.mark_deactivated.__annotations__
        assert "server_id" in sig
        assert sig["server_id"] == str  # noqa: E721

        # Test get_server_status
        sig = DatabaseInterface.get_server_status.__annotations__
        assert "server_id" in sig
        assert sig["server_id"] == str  # noqa: E721
        assert "return" in sig
        assert sig["return"] == str  # noqa: E721

        # Test update_server_config
        sig = DatabaseInterface.update_server_config.__annotations__
        assert "config" in sig
        assert sig["config"] == dict  # noqa: E721

        # Test load_all_resources
        sig = DatabaseInterface.load_all_resources.__annotations__
        assert "return" in sig
        assert sig["return"] == List[Dict]

        # Test upsert_resource
        sig = DatabaseInterface.upsert_resource.__annotations__
        assert "resource" in sig
        assert sig["resource"] == Dict

        # Test delete_resource
        sig = DatabaseInterface.delete_resource.__annotations__
        assert "resource_id" in sig
        assert sig["resource_id"] == str  # noqa: E721

    def test_inheritance_chain(self):
        """Test that DatabaseInterface properly inherits from ABC"""
        assert DatabaseInterface.__bases__ == (ABC,)

        # Test that it's abstract
        assert hasattr(DatabaseInterface, "__abstractmethods__")
        assert len(DatabaseInterface.__abstractmethods__) > 0

    def test_method_abstraction(self):
        """Test that all methods are properly abstract"""
        for method_name in DatabaseInterface.__abstractmethods__:
            method = getattr(DatabaseInterface, method_name)
            assert hasattr(method, "__isabstractmethod__")
            assert method.__isabstractmethod__ is True
