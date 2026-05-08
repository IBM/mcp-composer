"""Test module for ISV token org extraction functionality"""

import json
from unittest.mock import Mock, patch, AsyncMock
import pytest

from mcp_composer.core.auth.jwt.isv_token_validator import ISVTokenValidator


class TestISVOrgExtraction:
    """Test cases for org extraction from ISV tokens"""

    @pytest.fixture
    def mock_isv_token_with_org(self):
        """Create a mock ISV token (JWT) with platform_attributes containing org"""
        # This would be a real JWT in production, but for testing we'll mock the decoded claims
        return "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyQGV4YW1wbGUuY29tIiwicGxhdGZvcm1fYXR0cmlidXRlcyI6IntcInByb2R1Y3RfaWRcIjpcImFzcGVyYVwiLFwicHJvZHVjdF9vcmlnaW5fdXJsXCI6XCJodHRwczovL2FzcGVyYS5pYm1hc3BlcmEuY29tXCJ9In0.signature"

    @pytest.fixture
    def validator(self):
        """Create ISVTokenValidator instance"""
        return ISVTokenValidator(environment="test")

    def test_extract_org_from_isv_token_success(self, validator):
        """Test successful org extraction from ISV token"""
        # Mock the JWT decode to return claims with platform_attributes
        platform_attrs = {
            "product_id": "aspera",
            "product_origin_url": "https://aspera.ibmaspera.com",
        }

        mock_claims = {
            "sub": "user@example.com",
            "platform_attributes": json.dumps(platform_attrs),
        }

        with patch(
            "mcp_composer.core.auth.jwt.jwt_utils.decode_jwt_without_verification"
        ) as mock_decode:
            mock_decode.return_value = mock_claims

            org = validator._extract_org_from_isv_token("mock-token")

            assert org == "aspera"
            mock_decode.assert_called_once_with("mock-token")

    def test_extract_org_from_different_products(self, validator):
        """Test org extraction for different product origins"""
        test_cases = [
            ("https://aspera.ibmaspera.com", "aspera"),
            ("https://instana.ibm.com", "instana"),
            ("https://turbonomic.ibm.com", "turbonomic"),
            ("https://apptio.ibm.com", "apptio"),
        ]

        for origin_url, expected_org in test_cases:
            platform_attrs = {
                "product_id": expected_org,
                "product_origin_url": origin_url,
            }

            mock_claims = {"platform_attributes": json.dumps(platform_attrs)}

            with patch(
                "mcp_composer.core.auth.jwt.jwt_utils.decode_jwt_without_verification"
            ) as mock_decode:
                mock_decode.return_value = mock_claims

                org = validator._extract_org_from_isv_token("mock-token")

                assert org == expected_org, f"Failed for {origin_url}"

    def test_extract_org_missing_platform_attributes(self, validator):
        """Test org extraction when platform_attributes is missing"""
        mock_claims = {
            "sub": "user@example.com"
            # No platform_attributes
        }

        with patch(
            "mcp_composer.core.auth.jwt.jwt_utils.decode_jwt_without_verification"
        ) as mock_decode:
            mock_decode.return_value = mock_claims

            org = validator._extract_org_from_isv_token("mock-token")

            assert org is None

    def test_extract_org_missing_product_origin_url(self, validator):
        """Test org extraction when product_origin_url is missing"""
        platform_attrs = {
            "product_id": "aspera"
            # No product_origin_url
        }

        mock_claims = {"platform_attributes": json.dumps(platform_attrs)}

        with patch(
            "mcp_composer.core.auth.jwt.jwt_utils.decode_jwt_without_verification"
        ) as mock_decode:
            mock_decode.return_value = mock_claims

            org = validator._extract_org_from_isv_token("mock-token")

            assert org is None

    def test_extract_org_invalid_json_in_platform_attributes(self, validator):
        """Test org extraction when platform_attributes contains invalid JSON"""
        mock_claims = {"platform_attributes": "invalid-json{{"}

        with patch(
            "mcp_composer.core.auth.jwt.jwt_utils.decode_jwt_without_verification"
        ) as mock_decode:
            mock_decode.return_value = mock_claims

            org = validator._extract_org_from_isv_token("mock-token")

            assert org is None

    def test_extract_org_decode_failure(self, validator):
        """Test org extraction when JWT decode fails"""
        with patch(
            "mcp_composer.core.auth.jwt.jwt_utils.decode_jwt_without_verification"
        ) as mock_decode:
            mock_decode.return_value = None

            org = validator._extract_org_from_isv_token("invalid-token")

            assert org is None

    def test_extract_org_with_complex_url(self, validator):
        """Test org extraction with complex URLs containing paths and query params"""
        test_cases = [
            ("https://aspera.ibmaspera.com/path/to/resource?param=value", "aspera"),
            ("https://subdomain.aspera.ibmaspera.com", "subdomain"),
            ("http://localhost:8080", "localhost"),
        ]

        for origin_url, expected_org in test_cases:
            platform_attrs = {"product_origin_url": origin_url}

            mock_claims = {"platform_attributes": json.dumps(platform_attrs)}

            with patch(
                "mcp_composer.core.auth.jwt.jwt_utils.decode_jwt_without_verification"
            ) as mock_decode:
                mock_decode.return_value = mock_claims

                org = validator._extract_org_from_isv_token("mock-token")

                assert org == expected_org, f"Failed for {origin_url}"

    @pytest.mark.asyncio
    async def test_exchange_cookie_includes_org_in_response(self, validator):
        """Test that exchange_cookie_for_token includes org in the response"""
        platform_attrs = {
            "product_id": "aspera",
            "product_origin_url": "https://aspera.ibmaspera.com",
        }

        mock_claims = {"platform_attributes": json.dumps(platform_attrs)}

        # Mock the HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "test-access-token",
            "token_type": "Bearer",
            "expires_in": 3600,
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None

            with patch(
                "mcp_composer.core.auth.jwt.jwt_utils.decode_jwt_without_verification"
            ) as mock_decode:
                mock_decode.return_value = mock_claims

                result = await validator.exchange_cookie_for_token("test-session-id")

                # Verify org was added to response
                assert "org" in result
                assert result["org"] == "aspera"
                assert result["access_token"] == "test-access-token"

    @pytest.mark.asyncio
    async def test_exchange_cookie_without_org_still_works(self, validator):
        """Test that exchange_cookie_for_token works even if org extraction fails"""
        # Mock JWT decode to return None (extraction failure)
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "test-access-token",
            "token_type": "Bearer",
            "expires_in": 3600,
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None

            with patch(
                "mcp_composer.core.auth.jwt.jwt_utils.decode_jwt_without_verification"
            ) as mock_decode:
                mock_decode.return_value = None  # Decode fails

                result = await validator.exchange_cookie_for_token("test-session-id")

                # Verify response still works, just without org
                assert "access_token" in result
                assert result["access_token"] == "test-access-token"
                # org key should not be present if extraction failed
                assert "org" not in result


# Made with Bob
