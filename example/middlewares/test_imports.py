#!/usr/bin/env python3
"""
Test script to verify all middleware imports work correctly.
"""


def test_imports():
    """Test importing all middleware components."""
    print("Testing middleware imports...")

    try:
        from mcp_composer.middleware.circuit_breaker import CircuitBreakerMiddleware

        print("✅ CircuitBreakerMiddleware imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import CircuitBreakerMiddleware: {e}")

    try:
        from mcp_composer.middleware.concurrency import ConcurrencyLimiterMiddleware

        print("✅ ConcurrencyLimiterMiddleware imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import ConcurrencyLimiterMiddleware: {e}")

    try:
        from mcp_composer.middleware.rate_limit import RateLimiterMiddleware

        print("✅ RateLimiterMiddleware imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import RateLimiterMiddleware: {e}")

    try:
        from mcp_composer.middleware.prompt_injection import PromptInjectionMiddleware

        print("✅ PromptInjectionMiddleware imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import PromptInjectionMiddleware: {e}")

    try:
        from mcp_composer.middleware.stop_pii import (
            SecretsAndPIIMiddleware,
            RedactionStrategy,
        )

        print("✅ SecretsAndPIIMiddleware and RedactionStrategy imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import SecretsAndPIIMiddleware: {e}")

    try:
        from mcp_composer.middleware.xml2json import FormatXml2Json

        print("✅ FormatXml2Json imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import FormatXml2Json: {e}")

    try:
        from mcp_composer.middleware import (
            CircuitBreakerMiddleware,
            ConcurrencyLimiterMiddleware,
            RateLimiterMiddleware,
            PromptInjectionMiddleware,
            SecretsAndPIIMiddleware,
            RedactionStrategy,
            FormatXml2Json,
        )

        print("✅ All middleware imported from package successfully")
    except ImportError as e:
        print(f"❌ Failed to import from package: {e}")


def test_fastmcp_imports():
    """Test FastMCP imports used by middleware."""
    print("\nTesting FastMCP imports...")

    try:
        from fastmcp import FastMCP

        print("✅ FastMCP imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import FastMCP: {e}")

    try:
        from fastmcp.exceptions import ToolError

        print("✅ ToolError imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import ToolError: {e}")

    try:
        from fastmcp.server.middleware import Middleware, MiddlewareContext, CallNext

        print("✅ Middleware classes imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import Middleware classes: {e}")


if __name__ == "__main__":
    test_fastmcp_imports()
    test_imports()
    print("\n✅ Import tests completed!")
