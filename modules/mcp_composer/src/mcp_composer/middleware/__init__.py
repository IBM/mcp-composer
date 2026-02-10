"""
Middleware module for MCP Composer.

This module provides various middleware implementations including:
- Prompt injection protection
- Circuit breaker patterns
- Concurrency limiting
- Rate limiting
- PII and secrets handling
- XML to JSON conversion
"""

from .prompt_injection import PromptInjectionMiddleware
from .circuit_breaker import CircuitBreakerMiddleware
from .concurrency import ConcurrencyLimiterMiddleware
from .rate_limit_filter import RateLimitingMiddleware
from .pii_middleware import SecretsAndPIIMiddleware, RedactionStrategy
from .xml2json import FormatXml2Json
from .json_extraction_middleware import JSONExtractionMiddleware
from .error_sanitization_middleware import ErrorSanitizationMiddleware
from .session_aware_middleware import SessionAwareMiddleware

__all__ = [
    "PromptInjectionMiddleware",
    "CircuitBreakerMiddleware",
    "ConcurrencyLimiterMiddleware",
    "RateLimitingMiddleware",
    "SecretsAndPIIMiddleware",
    "RedactionStrategy",
    "FormatXml2Json",
    "JSONExtractionMiddleware",
    "ErrorSanitizationMiddleware",
    "SessionAwareMiddleware",
]
