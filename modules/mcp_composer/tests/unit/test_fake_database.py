"""Test module for fake_database.py"""

import pytest
from mcp_composer.store.fake_database import FakeDatabase


class TestFakeDatabase:
    """Test cases for FakeDatabase"""

    @pytest.fixture
    def fake_db(self):
        """Create a fresh FakeDatabase instance for each test"""
        return FakeDatabase()

    def test_fake_database_initialization(self, fake_db):
        """Test FakeDatabase initialization"""
        assert fake_db._servers == {}
        assert fake_db._tools == []

    def test_load_all_servers_empty(self, fake_db):
        """Test loading all servers when database is empty"""
        servers = fake_db.load_all_servers()
        assert servers == []

    def test_load_all_servers_with_data(self, fake_db):
        """Test loading all servers with data"""
        server1 = {"id": "server1", "name": "Test Server 1"}
        server2 = {"id": "server2", "name": "Test Server 2"}

        fake_db._servers["server1"] = server1
        fake_db._servers["server2"] = server2

        servers = fake_db.load_all_servers()
        assert len(servers) == 2
        assert server1 in servers
        assert server2 in servers

    def test_add_server(self, fake_db):
        """Test adding a server"""
        server_config = {"id": "test-server", "name": "Test Server"}
        fake_db.add_server(server_config)

        assert "test-server" in fake_db._servers
        assert fake_db._servers["test-server"] == server_config

    def test_add_server_overwrite(self, fake_db):
        """Test adding a server overwrites existing one"""
        server1 = {"id": "test-server", "name": "Original Server"}
        server2 = {"id": "test-server", "name": "Updated Server"}

        fake_db.add_server(server1)
        fake_db.add_server(server2)

        assert fake_db._servers["test-server"] == server2

    def test_remove_server_existing(self, fake_db):
        """Test removing an existing server"""
        server_config = {"id": "test-server", "name": "Test Server"}
        fake_db._servers["test-server"] = server_config

        fake_db.remove_server("test-server")

        assert "test-server" not in fake_db._servers

    def test_remove_server_nonexistent(self, fake_db):
        """Test removing a non-existent server"""
        fake_db.remove_server("nonexistent-server")
        # Should not raise an exception

    def test_reset(self, fake_db):
        """Test resetting the database"""
        # Add some data
        fake_db._servers["server1"] = {"id": "server1"}
        fake_db._tools = [{"name": "tool1"}]

        fake_db.reset()

        assert fake_db._servers == {}
        assert fake_db._tools == []

    def test_mark_deactivated_existing_server(self, fake_db):
        """Test marking an existing server as deactivated"""
        server_config = {"id": "test-server", "name": "Test Server", "status": "active"}
        fake_db._servers["test-server"] = server_config

        fake_db.mark_deactivated("test-server")

        assert fake_db._servers["test-server"]["status"] == "deactivated"

    def test_mark_deactivated_nonexistent_server(self, fake_db):
        """Test marking a non-existent server as deactivated"""
        fake_db.mark_deactivated("nonexistent-server")
        # Should not raise an exception

    def test_get_server_status_active(self, fake_db):
        """Test getting status of active server"""
        server_config = {"id": "test-server", "name": "Test Server", "status": "active"}
        fake_db._servers["test-server"] = server_config

        status = fake_db.get_server_status("test-server")
        assert status == "active"

    def test_get_server_status_deactivated(self, fake_db):
        """Test getting status of deactivated server"""
        server_config = {
            "id": "test-server",
            "name": "Test Server",
            "status": "deactivated",
        }
        fake_db._servers["test-server"] = server_config

        status = fake_db.get_server_status("test-server")
        assert status == "deactivated"

    def test_get_server_status_no_status_field(self, fake_db):
        """Test getting status when server has no status field"""
        server_config = {"id": "test-server", "name": "Test Server"}
        fake_db._servers["test-server"] = server_config

        status = fake_db.get_server_status("test-server")
        assert status == "active"  # Default status

    def test_get_server_status_nonexistent(self, fake_db):
        """Test getting status of non-existent server"""
        status = fake_db.get_server_status("nonexistent-server")
        assert status == "unknown"

    def test_get_document_existing(self, fake_db):
        """Test getting document of existing server"""
        server_config = {"id": "test-server", "name": "Test Server"}
        fake_db._servers["test-server"] = server_config

        document = fake_db.get_document("test-server")
        assert document == server_config

    def test_get_document_nonexistent(self, fake_db):
        """Test getting document of non-existent server"""
        document = fake_db.get_document("nonexistent-server")
        assert document == {}

    def test_disable_tools(self, fake_db):
        """Test disabling tools"""
        fake_db._tools = [
            {"name": "tool1", "server_id": "server1"},
            {"name": "tool2", "server_id": "server1"},
            {"name": "tool3", "server_id": "server2"},
        ]

        fake_db.disable_tools(["tool1", "tool2"], "server1")

        assert len(fake_db._tools) == 1
        assert fake_db._tools[0]["name"] == "tool3"

    def test_disable_tools_nonexistent(self, fake_db):
        """Test disabling non-existent tools"""
        fake_db._tools = [{"name": "tool1", "server_id": "server1"}]

        fake_db.disable_tools(["nonexistent-tool"], "server1")

        assert len(fake_db._tools) == 1  # Should remain unchanged

    def test_enable_tools_new_tools(self, fake_db):
        """Test enabling new tools"""
        fake_db._tools = [{"name": "existing-tool", "server_id": "server1"}]

        fake_db.enable_tools(["new-tool1", "new-tool2"], "server1")

        assert len(fake_db._tools) == 3
        tool_names = [t["name"] for t in fake_db._tools]
        assert "new-tool1" in tool_names
        assert "new-tool2" in tool_names

    def test_enable_tools_existing_tools(self, fake_db):
        """Test enabling existing tools (should not duplicate)"""
        fake_db._tools = [{"name": "existing-tool", "server_id": "server1"}]

        fake_db.enable_tools(["existing-tool"], "server1")

        assert len(fake_db._tools) == 1  # Should not duplicate

    def test_update_tool_description(self, fake_db):
        """Test updating tool description"""
        fake_db._tools = [
            {"name": "tool1", "server_id": "server1", "description": "old description"}
        ]

        fake_db.update_tool_description("tool1", "new description", "server1")

        assert fake_db._tools[0]["description"] == "new description"

    def test_update_tool_description_nonexistent(self, fake_db):
        """Test updating description of non-existent tool"""
        fake_db._tools = [
            {"name": "tool1", "server_id": "server1", "description": "old"}
        ]

        fake_db.update_tool_description(
            "nonexistent-tool", "new description", "server1"
        )

        # Should not change existing tool
        assert fake_db._tools[0]["description"] == "old"

    def test_disable_prompts(self, fake_db):
        """Test disabling prompts"""
        server_config = {"id": "server1", "name": "Test Server"}
        fake_db._servers["server1"] = server_config

        fake_db.disable_prompts(["prompt1", "prompt2"], "server1")

        assert "disabled_prompts" in fake_db._servers["server1"]
        assert fake_db._servers["server1"]["disabled_prompts"] == ["prompt1", "prompt2"]

    def test_disable_prompts_existing_disabled(self, fake_db):
        """Test disabling prompts when some are already disabled"""
        server_config = {
            "id": "server1",
            "name": "Test Server",
            "disabled_prompts": ["existing"],
        }
        fake_db._servers["server1"] = server_config

        fake_db.disable_prompts(["prompt1"], "server1")

        assert "prompt1" in fake_db._servers["server1"]["disabled_prompts"]
        assert "existing" in fake_db._servers["server1"]["disabled_prompts"]

    def test_disable_prompts_nonexistent_server(self, fake_db):
        """Test disabling prompts for non-existent server"""
        fake_db.disable_prompts(["prompt1"], "nonexistent-server")
        # Should not raise an exception

    def test_enable_prompts(self, fake_db):
        """Test enabling prompts"""
        server_config = {
            "id": "server1",
            "name": "Test Server",
            "disabled_prompts": ["prompt1", "prompt2"],
        }
        fake_db._servers["server1"] = server_config

        fake_db.enable_prompts(["prompt1"], "server1")

        assert fake_db._servers["server1"]["disabled_prompts"] == ["prompt1"]

    def test_enable_prompts_nonexistent_server(self, fake_db):
        """Test enabling prompts for non-existent server"""
        fake_db.enable_prompts(["prompt1"], "nonexistent-server")
        # Should not raise an exception

    def test_disable_resources(self, fake_db):
        """Test disabling resources"""
        server_config = {"id": "server1", "name": "Test Server"}
        fake_db._servers["server1"] = server_config

        fake_db.disable_resources(["resource1", "resource2"], "server1")

        assert "disabled_resources" in fake_db._servers["server1"]
        assert fake_db._servers["server1"]["disabled_resources"] == [
            "resource1",
            "resource2",
        ]

    def test_disable_resources_existing_disabled(self, fake_db):
        """Test disabling resources when some are already disabled"""
        server_config = {
            "id": "server1",
            "name": "Test Server",
            "disabled_resources": ["existing"],
        }
        fake_db._servers["server1"] = server_config

        fake_db.disable_resources(["resource1"], "server1")

        assert "resource1" in fake_db._servers["server1"]["disabled_resources"]
        assert "existing" in fake_db._servers["server1"]["disabled_resources"]

    def test_disable_resources_nonexistent_server(self, fake_db):
        """Test disabling resources for non-existent server"""
        fake_db.disable_resources(["resource1"], "nonexistent-server")
        # Should not raise an exception

    def test_enable_resources(self, fake_db):
        """Test enabling resources"""
        server_config = {
            "id": "server1",
            "name": "Test Server",
            "disabled_resources": ["resource1", "resource2"],
        }
        fake_db._servers["server1"] = server_config

        fake_db.enable_resources(["resource1"], "server1")

        assert fake_db._servers["server1"]["disabled_resources"] == ["resource1"]

    def test_enable_resources_nonexistent_server(self, fake_db):
        """Test enabling resources for non-existent server"""
        fake_db.enable_resources(["resource1"], "nonexistent-server")
        # Should not raise an exception

    def test_update_server_config(self, fake_db):
        """Test updating server config"""
        original_config = {"id": "server1", "name": "Original Name"}
        updated_config = {"id": "server1", "name": "Updated Name", "new_field": "value"}

        fake_db._servers["server1"] = original_config
        fake_db.update_server_config(updated_config)

        assert fake_db._servers["server1"] == updated_config

    def test_update_server_config_new_server(self, fake_db):
        """Test updating config for new server"""
        new_config = {"id": "new-server", "name": "New Server"}

        fake_db.update_server_config(new_config)

        assert fake_db._servers["new-server"] == new_config

    def test_fake_database_inheritance(self, fake_db):
        """Test that FakeDatabase inherits from DatabaseInterface"""
        from mcp_composer.store.database import DatabaseInterface

        assert isinstance(fake_db, DatabaseInterface)

    def test_comprehensive_workflow(self, fake_db):
        """Test a comprehensive workflow with the fake database"""
        # Add servers
        server1 = {"id": "server1", "name": "Server 1", "status": "active"}
        server2 = {"id": "server2", "name": "Server 2", "status": "active"}

        fake_db.add_server(server1)
        fake_db.add_server(server2)

        # Verify servers are loaded
        servers = fake_db.load_all_servers()
        assert len(servers) == 2

        # Enable tools
        fake_db.enable_tools(["tool1", "tool2"], "server1")
        fake_db.enable_tools(["tool3"], "server2")

        assert len(fake_db._tools) == 3

        # Update tool description
        fake_db.update_tool_description("tool1", "Updated description", "server1")

        # Disable some tools
        fake_db.disable_tools(["tool2"], "server1")

        assert len(fake_db._tools) == 2

        # Disable prompts and resources
        fake_db.disable_prompts(["prompt1"], "server1")
        fake_db.disable_resources(["resource1"], "server1")

        # Mark server as deactivated
        fake_db.mark_deactivated("server1")

        assert fake_db.get_server_status("server1") == "deactivated"
        assert fake_db.get_server_status("server2") == "active"

        # Get document
        doc = fake_db.get_document("server1")
        assert doc["status"] == "deactivated"
        assert "disabled_prompts" in doc
        assert "disabled_resources" in doc
