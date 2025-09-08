"""Test module for mcp_stdio.py"""

import pytest
from pydantic import ValidationError
from mcp_composer.core.models.mcp_stdio import MCPServerStdio


class TestMCPServerStdio:
    """Test cases for MCPServerStdio model"""

    def test_mcp_server_stdio_creation_with_required_fields(self):
        """Test creating MCPServerStdio with required fields only"""
        server = MCPServerStdio(id="test-server", type="stdio", args=["server.py"])

        assert server.id == "test-server"
        assert server.type == "stdio"
        assert server.args == ["server.py"]
        assert server.env is None
        assert server.cwd is None

    def test_mcp_server_stdio_creation_with_all_fields(self):
        """Test creating MCPServerStdio with all fields"""
        server = MCPServerStdio(
            id="test-server",
            type="stdio",
            args=["server.py", "--port", "8080"],
            env={"DEBUG": "true", "API_KEY": "secret"},
            cwd="/path/to/server",
        )

        assert server.id == "test-server"
        assert server.type == "stdio"
        assert server.args == ["server.py", "--port", "8080"]
        assert server.env == {"DEBUG": "true", "API_KEY": "secret"}
        assert server.cwd == "/path/to/server"

    def test_mcp_server_stdio_creation_with_empty_args(self):
        """Test creating MCPServerStdio with empty args list"""
        server = MCPServerStdio(id="test-server", type="stdio", args=[])

        assert server.id == "test-server"
        assert server.type == "stdio"
        assert server.args == []

    def test_mcp_server_stdio_creation_with_none_env(self):
        """Test creating MCPServerStdio with None env"""
        server = MCPServerStdio(
            id="test-server", type="stdio", args=["server.py"], env=None
        )

        assert server.env is None

    def test_mcp_server_stdio_creation_with_none_cwd(self):
        """Test creating MCPServerStdio with None cwd"""
        server = MCPServerStdio(
            id="test-server", type="stdio", args=["server.py"], cwd=None
        )

        assert server.cwd is None

    def test_mcp_server_stdio_missing_required_fields(self):
        """Test that missing required fields raise ValidationError"""
        with pytest.raises(ValidationError):
            MCPServerStdio()

    def test_mcp_server_stdio_missing_id(self):
        """Test that missing id raises ValidationError"""
        with pytest.raises(ValidationError):
            MCPServerStdio(type="stdio", args=["server.py"])

    def test_mcp_server_stdio_missing_type(self):
        """Test that missing type raises ValidationError"""
        with pytest.raises(ValidationError):
            MCPServerStdio(id="test-server", args=["server.py"])

    def test_mcp_server_stdio_missing_args(self):
        """Test that missing args raises ValidationError"""
        with pytest.raises(ValidationError):
            MCPServerStdio(id="test-server", type="stdio")

    def test_mcp_server_stdio_model_validation(self):
        """Test model validation with various data types"""
        # Test with string args
        with pytest.raises(ValidationError):
            MCPServerStdio(
                id="test-server",
                type="stdio",
                args="server.py",  # Should be list, not string
            )

        # Test with invalid env type
        with pytest.raises(ValidationError):
            MCPServerStdio(
                id="test-server",
                type="stdio",
                args=["server.py"],
                env="invalid",  # Should be dict, not string
            )

    def test_mcp_server_stdio_field_descriptions(self):
        """Test that field descriptions are properly set"""
        # Get field info
        id_field = MCPServerStdio.model_fields["id"]
        type_field = MCPServerStdio.model_fields["type"]
        args_field = MCPServerStdio.model_fields["args"]
        env_field = MCPServerStdio.model_fields["env"]
        cwd_field = MCPServerStdio.model_fields["cwd"]

        assert "Name of the mcp server" in id_field.description
        assert "Type of mcp server" in type_field.description
        assert "List of arguments" in args_field.description
        assert "environment variables" in env_field.description
        assert "Working directory" in cwd_field.description

    def test_mcp_server_stdio_json_serialization(self):
        """Test JSON serialization and deserialization"""
        server = MCPServerStdio(
            id="test-server",
            type="stdio",
            args=["server.py", "--debug"],
            env={"DEBUG": "true"},
            cwd="/path/to/server",
        )

        # Serialize to dict
        server_dict = server.model_dump()

        assert server_dict["id"] == "test-server"
        assert server_dict["type"] == "stdio"
        assert server_dict["args"] == ["server.py", "--debug"]
        assert server_dict["env"] == {"DEBUG": "true"}
        assert server_dict["cwd"] == "/path/to/server"

        # Deserialize from dict
        server_from_dict = MCPServerStdio(**server_dict)
        assert server_from_dict == server

    def test_mcp_server_stdio_equality(self):
        """Test equality comparison"""
        server1 = MCPServerStdio(id="test-server", type="stdio", args=["server.py"])

        server2 = MCPServerStdio(id="test-server", type="stdio", args=["server.py"])

        server3 = MCPServerStdio(
            id="different-server", type="stdio", args=["server.py"]
        )

        assert server1 == server2
        assert server1 != server3
