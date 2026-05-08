"""Tests for parallel ISV operations optimization."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.exceptions import HTTPException

from mcp_composer.core.auth.jwt.isv_token_validator import (
    ISVEnvironmentConfig,
    ISVTokenCache,
    ISVTokenValidator,
)


@pytest.fixture
def mock_request():
    """Create a mock request with session cookie."""
    request = MagicMock()
    request.headers = {
        "cookie": "mcsp-glb-iam=test-session-id-123"
    }
    return request


@pytest.fixture
def isv_validator():
    """Create ISV validator with cache enabled."""
    config = ISVEnvironmentConfig(environment="prod")
    validator = ISVTokenValidator(
        environment="prod",
        cache_enabled=True,
        cache_ttl=7200,
        fetch_instances=True,
    )
    return validator


class TestParallelISVOperations:
    """Test parallel execution of token exchange and instance fetching."""

    @pytest.mark.asyncio
    async def test_parallel_execution_on_cache_miss(self, isv_validator, mock_request):
        """Test that token exchange and instance fetch run in parallel on cache miss."""
        # Mock the API calls with delays to simulate network latency
        async def mock_exchange_token(session_id):
            await asyncio.sleep(0.5)  # Simulate 500ms API call
            return {
                "access_token": "test-token",
                "token_type": "Bearer",
                "expires_in": 7200,
            }

        async def mock_fetch_instances(session_id, filter_by_product_id=None):
            await asyncio.sleep(0.5)  # Simulate 500ms API call
            return [
                {
                    "id": "instance-1",
                    "subscription": {"productId": "lakehouse"},
                }
            ]

        with patch.object(
            isv_validator, "exchange_cookie_for_token", side_effect=mock_exchange_token
        ), patch.object(
            isv_validator, "fetch_user_instances", side_effect=mock_fetch_instances
        ):
            # Measure execution time
            start_time = time.time()
            result = await isv_validator.validate_request(mock_request)
            elapsed_time = time.time() - start_time

            # Verify result
            assert result["access_token"] == "test-token"
            assert len(result["user_instances"]) == 1
            assert result["user_instances"][0]["id"] == "instance-1"

            # Verify parallel execution: should take ~0.5s (parallel) not ~1.0s (sequential)
            # Allow some overhead for test execution
            assert elapsed_time < 0.8, (
                f"Parallel execution should take <0.8s, took {elapsed_time:.2f}s. "
                "This suggests sequential execution."
            )
            assert elapsed_time >= 0.5, (
                f"Execution should take at least 0.5s (API call time), took {elapsed_time:.2f}s"
            )

    @pytest.mark.asyncio
    async def test_sequential_vs_parallel_performance(
        self, isv_validator, mock_request
    ):
        """Compare sequential vs parallel execution times."""
        # Mock API calls with realistic delays
        async def mock_exchange_token(session_id):
            await asyncio.sleep(0.3)  # 300ms
            return {
                "access_token": "test-token",
                "token_type": "Bearer",
                "expires_in": 7200,
            }

        async def mock_fetch_instances(session_id, filter_by_product_id=None):
            await asyncio.sleep(0.4)  # 400ms
            return [{"id": "instance-1", "subscription": {"productId": "lakehouse"}}]

        with patch.object(
            isv_validator, "exchange_cookie_for_token", side_effect=mock_exchange_token
        ), patch.object(
            isv_validator, "fetch_user_instances", side_effect=mock_fetch_instances
        ):
            # Test parallel execution (current implementation)
            start_time = time.time()
            await isv_validator.validate_request(mock_request)
            parallel_time = time.time() - start_time

            # Expected: ~0.4s (max of 0.3s and 0.4s) + overhead
            assert parallel_time < 0.6, f"Parallel execution took {parallel_time:.2f}s"

            # Calculate expected sequential time
            sequential_time = 0.3 + 0.4  # 700ms
            improvement = ((sequential_time - parallel_time) / sequential_time) * 100

            print(f"\nPerformance Improvement:")
            print(f"  Sequential (expected): {sequential_time:.2f}s")
            print(f"  Parallel (actual): {parallel_time:.2f}s")
            print(f"  Improvement: {improvement:.1f}%")

            # Verify at least 30% improvement
            assert improvement >= 30, (
                f"Expected at least 30% improvement, got {improvement:.1f}%"
            )

    @pytest.mark.asyncio
    async def test_cached_token_only_fetches_instances(
        self, isv_validator, mock_request
    ):
        """Test that only instances are fetched when token is cached."""
        # Pre-populate token cache
        session_id = "test-session-id-123"
        isv_validator.cache.set(session_id, "cached-token", 7200)

        async def mock_fetch_instances(session_id, filter_by_product_id=None):
            await asyncio.sleep(0.3)
            return [{"id": "instance-1", "subscription": {"productId": "lakehouse"}}]

        exchange_mock = AsyncMock()
        with patch.object(
            isv_validator, "exchange_cookie_for_token", exchange_mock
        ), patch.object(
            isv_validator, "fetch_user_instances", side_effect=mock_fetch_instances
        ):
            result = await isv_validator.validate_request(mock_request)

            # Verify token exchange was NOT called
            exchange_mock.assert_not_called()

            # Verify cached token was used
            assert result["access_token"] == "cached-token"
            assert result["cached"] is True

            # Verify instances were fetched
            assert len(result["user_instances"]) == 1

    @pytest.mark.asyncio
    async def test_cached_instances_only_fetches_token(
        self, isv_validator, mock_request
    ):
        """Test that only token is fetched when instances are cached."""
        # Pre-populate instance cache
        session_id = "test-session-id-123"
        cached_instances = [
            {"id": "instance-1", "subscription": {"productId": "lakehouse"}}
        ]
        isv_validator.cache.set_instances(session_id, cached_instances, 7200)

        async def mock_exchange_token(session_id):
            await asyncio.sleep(0.3)
            return {
                "access_token": "new-token",
                "token_type": "Bearer",
                "expires_in": 7200,
            }

        instances_mock = AsyncMock()
        with patch.object(
            isv_validator, "exchange_cookie_for_token", side_effect=mock_exchange_token
        ), patch.object(isv_validator, "fetch_user_instances", instances_mock):
            result = await isv_validator.validate_request(mock_request)

            # Verify instance fetch was NOT called
            instances_mock.assert_not_called()

            # Verify token was fetched
            assert result["access_token"] == "new-token"
            assert result["cached"] is False

            # Verify cached instances were used
            assert result["user_instances"] == cached_instances

    @pytest.mark.asyncio
    async def test_both_cached_no_api_calls(self, isv_validator, mock_request):
        """Test that no API calls are made when both token and instances are cached."""
        # Pre-populate both caches
        session_id = "test-session-id-123"
        isv_validator.cache.set(session_id, "cached-token", 7200)
        cached_instances = [
            {"id": "instance-1", "subscription": {"productId": "lakehouse"}}
        ]
        isv_validator.cache.set_instances(session_id, cached_instances, 7200)

        exchange_mock = AsyncMock()
        instances_mock = AsyncMock()

        with patch.object(
            isv_validator, "exchange_cookie_for_token", exchange_mock
        ), patch.object(isv_validator, "fetch_user_instances", instances_mock):
            start_time = time.time()
            result = await isv_validator.validate_request(mock_request)
            elapsed_time = time.time() - start_time

            # Verify no API calls were made
            exchange_mock.assert_not_called()
            instances_mock.assert_not_called()

            # Verify cached data was used
            assert result["access_token"] == "cached-token"
            assert result["cached"] is True
            assert result["user_instances"] == cached_instances

            # Verify fast execution (< 50ms)
            assert elapsed_time < 0.05, (
                f"Cached execution should be <50ms, took {elapsed_time*1000:.1f}ms"
            )

    @pytest.mark.asyncio
    async def test_parallel_execution_handles_errors(
        self, isv_validator, mock_request
    ):
        """Test that errors in parallel execution are properly handled."""

        async def mock_exchange_token(session_id):
            await asyncio.sleep(0.1)
            raise HTTPException(status_code=403, detail="Token exchange failed")

        async def mock_fetch_instances(session_id, filter_by_product_id=None):
            await asyncio.sleep(0.1)
            return [{"id": "instance-1", "subscription": {"productId": "lakehouse"}}]

        with patch.object(
            isv_validator, "exchange_cookie_for_token", side_effect=mock_exchange_token
        ), patch.object(
            isv_validator, "fetch_user_instances", side_effect=mock_fetch_instances
        ):
            # Should raise the exception from token exchange
            with pytest.raises(HTTPException) as exc_info:
                await isv_validator.validate_request(mock_request)

            assert exc_info.value.status_code == 403
            assert "Token exchange failed" in str(exc_info.value.detail)


class TestCacheEfficiency:
    """Test cache hit rates and efficiency."""

    @pytest.mark.asyncio
    async def test_cache_reduces_api_calls(self, isv_validator, mock_request):
        """Test that cache significantly reduces API calls."""
        call_count = {"token": 0, "instances": 0}

        async def mock_exchange_token(session_id):
            call_count["token"] += 1
            await asyncio.sleep(0.1)
            return {
                "access_token": f"token-{call_count['token']}",
                "token_type": "Bearer",
                "expires_in": 7200,
            }

        async def mock_fetch_instances(session_id, filter_by_product_id=None):
            call_count["instances"] += 1
            await asyncio.sleep(0.1)
            return [{"id": f"instance-{call_count['instances']}"}]

        with patch.object(
            isv_validator, "exchange_cookie_for_token", side_effect=mock_exchange_token
        ), patch.object(
            isv_validator, "fetch_user_instances", side_effect=mock_fetch_instances
        ):
            # First call - cache miss
            result1 = await isv_validator.validate_request(mock_request)
            assert call_count["token"] == 1
            assert call_count["instances"] == 1

            # Second call - cache hit
            result2 = await isv_validator.validate_request(mock_request)
            assert call_count["token"] == 1  # No additional call
            assert call_count["instances"] == 1  # No additional call

            # Verify cached data is returned
            assert result2["access_token"] == result1["access_token"]
            assert result2["user_instances"] == result1["user_instances"]
            assert result2["cached"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

# Made with Bob
