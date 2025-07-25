import unittest
import pytest
import os
import json
from mcp_composer.utils import ValidationError, AllServersValidator


class TestComposer(unittest.TestCase):
    def test_valid_servers_file(self):
        """Test that a valid servers file does not raise a ValidationError."""
        current_dir = os.path.dirname(__file__)
        path = os.path.join(current_dir, "./../data/member_servers.json")
        # Assumes file is in the root or test dir

        with open(path, "r") as f:
            servers = json.load(f)

        # Act / Assert
        try:
            AllServersValidator(servers).validate_all()
        except ValidationError as e:
            self.fail(f"Validation failed unexpectedly: {e}")

    def test_invalid_missing_auth_strategy(self, tmp_path):
        """Test that a server without an auth_strategy raises a ValidationError."""
        # Arrange
        servers = [
            {
                "id": "invalid-server",
                "type": "client",
                "endpoint": "https://example.com",
                "auth_strategy": "apikey",
                # Missing "auth"
            }
        ]

        # Act / Assert
        with pytest.raises(
            ValidationError, match="Missing 'auth' for server with id 'invalid-server'"
        ):
            AllServersValidator(servers).validate_all()

    def test_invalid_openapi_missing_fields(self, tmp_path):
        """Test that an OpenAPI server without required fields raises a ValidationError."""
        # Arrange
        servers = [
            {
                "id": "broken-openapi",
                "type": "openapi",
                # "endpoint" is missing
                "openapi_url": "https://docs.example.com/openapi.json",
            }
        ]

        # Act / Assert
        with pytest.raises(
            ValidationError,
            match="Missing required field\\(s\\) for 'openapi' type in server 'broken-openapi': endpoint",
        ):
            AllServersValidator(servers).validate_all()

    def test_client_type_missing_endpoint(self):
        """Test that a client type server without an endpoint raises a ValidationError."""
        servers = [
            {
                "id": "client-no-endpoint",
                "type": "client",
                # missing "endpoint"
            }
        ]

        with self.assertRaisesRegex(
            ValidationError,
            "Missing 'endpoint' for 'client' type in server 'client-no-endpoint'",
        ):
            AllServersValidator(servers).validate_all()


if __name__ == "__main__":
    unittest.main()
