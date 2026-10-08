"""Unit tests for S3 OpenAPI spec loading functionality"""

import json
from unittest.mock import AsyncMock, MagicMock, patch, Mock

import pytest

from mcp_composer.core.utils.utils import load_spec_from_url


class TestS3SpecLoading:
    """Test S3 URL detection and spec loading"""

    @pytest.fixture
    def sample_spec(self):
        """Sample OpenAPI specification"""
        return {
            "openapi": "3.0.0",
            "info": {"title": "Test API", "version": "1.0.0"},
            "paths": {"/test": {"get": {"summary": "Test endpoint"}}},
        }

    @pytest.mark.asyncio
    async def test_s3_virtual_hosted_style_url_detection(self, sample_spec):
        """Test detection and parsing of S3 virtual-hosted style URLs"""
        s3_url = (
            "https://example-openapi-specs.s3.us-east-1.amazonaws.com/api-spec.json"
        )

        # Mock boto3 at import time
        mock_boto3 = MagicMock()
        mock_s3_client = MagicMock()
        mock_boto3.client.return_value = mock_s3_client

        # Mock S3 response
        mock_response = {
            "Body": MagicMock(
                read=MagicMock(return_value=json.dumps(sample_spec).encode("utf-8"))
            )
        }
        mock_s3_client.get_object.return_value = mock_response

        with patch.dict(
            "sys.modules", {"boto3": mock_boto3, "botocore.exceptions": MagicMock()}
        ):
            # Call the function
            result = await load_spec_from_url("https://api.example.com", s3_url)

            # Verify boto3 was called correctly
            mock_boto3.client.assert_called_once_with("s3", region_name="us-east-1")
            mock_s3_client.get_object.assert_called_once_with(
                Bucket="example-openapi-specs", Key="api-spec.json"
            )

            # Verify the spec was loaded correctly
            assert result == sample_spec

    @pytest.mark.asyncio
    async def test_s3_path_style_url_detection(self, sample_spec):
        """Test detection and parsing of S3 path-style URLs"""
        s3_url = (
            "https://s3.eu-west-1.amazonaws.com/my-specs/services/api/v1/openapi.json"
        )

        # Mock boto3 at import time
        mock_boto3 = MagicMock()
        mock_s3_client = MagicMock()
        mock_boto3.client.return_value = mock_s3_client

        # Mock S3 response
        mock_response = {
            "Body": MagicMock(
                read=MagicMock(return_value=json.dumps(sample_spec).encode("utf-8"))
            )
        }
        mock_s3_client.get_object.return_value = mock_response

        with patch.dict(
            "sys.modules", {"boto3": mock_boto3, "botocore.exceptions": MagicMock()}
        ):
            # Call the function
            result = await load_spec_from_url("https://api.example.com", s3_url)

            # Verify boto3 was called correctly
            mock_boto3.client.assert_called_once_with("s3", region_name="eu-west-1")
            mock_s3_client.get_object.assert_called_once_with(
                Bucket="my-specs", Key="services/api/v1/openapi.json"
            )

            # Verify the spec was loaded correctly
            assert result == sample_spec

    @pytest.mark.asyncio
    async def test_s3_access_denied_error(self):
        """Test handling of S3 access denied errors"""
        s3_url = "https://bucket-name.s3.us-east-1.amazonaws.com/spec.json"

        # Create a proper ClientError that inherits from Exception
        class MockClientError(Exception):
            def __init__(self, error_response, operation_name):
                self.response = error_response
                super().__init__(
                    f"An error occurred ({error_response['Error']['Code']}) when calling the {operation_name} operation"
                )

        # Mock boto3 and botocore with proper exception
        mock_boto3 = MagicMock()
        mock_s3_client = MagicMock()
        mock_boto3.client.return_value = mock_s3_client

        error_response = {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}}
        mock_s3_client.get_object.side_effect = MockClientError(
            error_response, "GetObject"
        )

        # Create mock botocore module with ClientError
        mock_botocore_module = MagicMock()
        mock_botocore_exceptions = MagicMock()
        mock_botocore_exceptions.ClientError = MockClientError
        mock_botocore_module.exceptions = mock_botocore_exceptions

        with patch.dict(
            "sys.modules",
            {
                "boto3": mock_boto3,
                "botocore": mock_botocore_module,
                "botocore.exceptions": mock_botocore_exceptions,
            },
        ):
            # Verify the error is raised with proper message
            with pytest.raises(ValueError) as exc_info:
                await load_spec_from_url("https://api.example.com", s3_url)

            assert "AccessDenied" in str(exc_info.value)
            assert "bucket-name" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_s3_bucket_not_found_error(self):
        """Test handling of S3 bucket not found errors"""
        s3_url = "https://nonexistent-bucket.s3.us-west-2.amazonaws.com/spec.json"

        # Create a proper ClientError that inherits from Exception
        class MockClientError(Exception):
            def __init__(self, error_response, operation_name):
                self.response = error_response
                super().__init__(
                    f"An error occurred ({error_response['Error']['Code']}) when calling the {operation_name} operation"
                )

        # Mock boto3 and botocore with proper exception
        mock_boto3 = MagicMock()
        mock_s3_client = MagicMock()
        mock_boto3.client.return_value = mock_s3_client

        error_response = {
            "Error": {
                "Code": "NoSuchBucket",
                "Message": "The specified bucket does not exist",
            }
        }
        mock_s3_client.get_object.side_effect = MockClientError(
            error_response, "GetObject"
        )

        # Create mock botocore module with ClientError
        mock_botocore_module = MagicMock()
        mock_botocore_exceptions = MagicMock()
        mock_botocore_exceptions.ClientError = MockClientError
        mock_botocore_module.exceptions = mock_botocore_exceptions

        with patch.dict(
            "sys.modules",
            {
                "boto3": mock_boto3,
                "botocore": mock_botocore_module,
                "botocore.exceptions": mock_botocore_exceptions,
            },
        ):
            # Verify the error is raised with proper message
            with pytest.raises(ValueError) as exc_info:
                await load_spec_from_url("https://api.example.com", s3_url)

            assert "NoSuchBucket" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_s3_invalid_json_error(self):
        """Test handling of invalid JSON in S3 object"""
        s3_url = "https://bucket-name.s3.us-east-1.amazonaws.com/invalid.json"

        # Create a proper ClientError that inherits from Exception
        class MockClientError(Exception):
            def __init__(self, error_response, operation_name):
                self.response = error_response
                super().__init__(
                    f"An error occurred ({error_response['Error']['Code']}) when calling the {operation_name} operation"
                )

        # Mock boto3
        mock_boto3 = MagicMock()
        mock_s3_client = MagicMock()
        mock_boto3.client.return_value = mock_s3_client

        # Mock S3 response with invalid JSON
        mock_response = {
            "Body": MagicMock(read=MagicMock(return_value=b"not valid json {"))
        }
        mock_s3_client.get_object.return_value = mock_response

        # Create mock botocore module with ClientError
        mock_botocore_module = MagicMock()
        mock_botocore_exceptions = MagicMock()
        mock_botocore_exceptions.ClientError = MockClientError
        mock_botocore_module.exceptions = mock_botocore_exceptions

        with patch.dict(
            "sys.modules",
            {
                "boto3": mock_boto3,
                "botocore": mock_botocore_module,
                "botocore.exceptions": mock_botocore_exceptions,
            },
        ):
            # Verify the error is raised with proper message
            with pytest.raises(ValueError) as exc_info:
                await load_spec_from_url("https://api.example.com", s3_url)

            assert "Invalid JSON" in str(exc_info.value)
            assert "bucket-name" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_boto3_not_installed_error(self, sample_spec):
        """Test error handling when boto3 is not installed"""
        s3_url = "https://bucket-name.s3.us-east-1.amazonaws.com/spec.json"

        # Remove boto3 from sys.modules to simulate it not being installed
        with patch.dict("sys.modules", {"boto3": None}):
            with pytest.raises(ValueError) as exc_info:
                await load_spec_from_url("https://api.example.com", s3_url)

            assert "boto3 is not installed" in str(exc_info.value)
            assert "pip install mcp-composer[aws]" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_standard_http_url_still_works(self, sample_spec):
        """Test that standard HTTP URLs continue to work (backward compatibility)"""
        http_url = "https://api.example.com/openapi.json"

        with patch("httpx.AsyncClient") as mock_client_class:
            # Mock HTTP response
            mock_response = MagicMock()
            mock_response.json.return_value = sample_spec
            mock_response.raise_for_status = MagicMock()

            # Create async context manager mock
            mock_client_instance = MagicMock()
            mock_client_instance.get = AsyncMock(return_value=mock_response)

            # Setup context manager
            mock_client_class.return_value.__aenter__ = AsyncMock(
                return_value=mock_client_instance
            )
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

            # Call the function
            result = await load_spec_from_url("https://api.example.com", http_url)

            # Verify httpx was used (not boto3)
            mock_client_instance.get.assert_called_once_with(http_url)
            assert result == sample_spec

    @pytest.mark.asyncio
    async def test_standard_https_url_still_works(self, sample_spec):
        """Test that standard HTTPS URLs continue to work (backward compatibility)"""
        https_url = "https://raw.githubusercontent.com/user/repo/main/openapi.json"

        with patch("httpx.AsyncClient") as mock_client_class:
            # Mock HTTP response
            mock_response = MagicMock()
            mock_response.json.return_value = sample_spec
            mock_response.raise_for_status = MagicMock()

            # Create async context manager mock
            mock_client_instance = MagicMock()
            mock_client_instance.get = AsyncMock(return_value=mock_response)

            # Setup context manager
            mock_client_class.return_value.__aenter__ = AsyncMock(
                return_value=mock_client_instance
            )
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

            # Call the function
            result = await load_spec_from_url("https://api.example.com", https_url)

            # Verify httpx was used (not boto3)
            mock_client_instance.get.assert_called_once_with(https_url)
            assert result == sample_spec

    @pytest.mark.asyncio
    async def test_s3_url_with_nested_path(self, sample_spec):
        """Test S3 URL with deeply nested path"""
        s3_url = "https://my-bucket.s3.ap-south-1.amazonaws.com/specs/v2/services/api/openapi.json"

        # Mock boto3
        mock_boto3 = MagicMock()
        mock_s3_client = MagicMock()
        mock_boto3.client.return_value = mock_s3_client

        # Mock S3 response
        mock_response = {
            "Body": MagicMock(
                read=MagicMock(return_value=json.dumps(sample_spec).encode("utf-8"))
            )
        }
        mock_s3_client.get_object.return_value = mock_response

        with patch.dict(
            "sys.modules", {"boto3": mock_boto3, "botocore.exceptions": MagicMock()}
        ):
            # Call the function
            result = await load_spec_from_url("https://api.example.com", s3_url)

            # Verify the nested path was parsed correctly
            mock_s3_client.get_object.assert_called_once_with(
                Bucket="my-bucket", Key="specs/v2/services/api/openapi.json"
            )
            assert result == sample_spec

    @pytest.mark.asyncio
    async def test_s3_url_with_special_characters_in_key(self, sample_spec):
        """Test S3 URL with special characters in the key"""
        s3_url = (
            "https://bucket-name.s3.us-east-1.amazonaws.com/specs/api-v1.0_final.json"
        )

        # Mock boto3
        mock_boto3 = MagicMock()
        mock_s3_client = MagicMock()
        mock_boto3.client.return_value = mock_s3_client

        # Mock S3 response
        mock_response = {
            "Body": MagicMock(
                read=MagicMock(return_value=json.dumps(sample_spec).encode("utf-8"))
            )
        }
        mock_s3_client.get_object.return_value = mock_response

        with patch.dict(
            "sys.modules", {"boto3": mock_boto3, "botocore.exceptions": MagicMock()}
        ):
            # Call the function
            result = await load_spec_from_url("https://api.example.com", s3_url)

            # Verify the key with special characters was handled correctly
            mock_s3_client.get_object.assert_called_once_with(
                Bucket="bucket-name", Key="specs/api-v1.0_final.json"
            )
            assert result == sample_spec


# Made with Bob
