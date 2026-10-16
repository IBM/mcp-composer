"""Common validation utilities and decorators for MCP Composer.

This module provides reusable validation functions and decorators that can be
used throughout the codebase to ensure data integrity and consistency.

Examples:
    Basic validation:
        >>> validate_non_empty_string("test", "field_name")
        'test'
        >>> validate_url("https://example.com")
        'https://example.com'

    Using decorators:
        >>> @validate_arguments
        ... def my_function(url: str, name: str):
        ...     return f"{name}: {url}"

        >>> @validate_return_value
        ... def get_config() -> dict:
        ...     return {"key": "value"}
"""

from __future__ import annotations

import re
from functools import lru_cache, wraps
from typing import Any, Callable, Optional, Pattern, TypeVar, Union
from urllib.parse import urlparse

from mcp_composer.core.utils.logger import LoggerFactory

logger = LoggerFactory.get_logger()

# Type variable for generic decorator support
T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., Any])


# ============================================================================
# Exception Classes
# ============================================================================


class ValidationError(Exception):
    """Base exception for validation errors."""

    def __init__(self, message: str, field: Optional[str] = None, value: Any = None):
        self.field = field
        self.value = value
        super().__init__(message)


class URLValidationError(ValidationError):
    """Raised when URL validation fails."""


class IDValidationError(ValidationError):
    """Raised when ID format validation fails."""


class RangeValidationError(ValidationError):
    """Raised when value is out of acceptable range."""


class TypeValidationError(ValidationError):
    """Raised when type validation fails."""


class ConfigValidationError(ValidationError):
    """Raised when configuration validation fails."""


# ============================================================================
# String Validation Functions
# ============================================================================


def validate_non_empty_string(value: Any, field_name: str, strip: bool = True) -> str:
    """Validate that a value is a non-empty string.

    Args:
        value: The value to validate
        field_name: Name of the field being validated (for error messages)
        strip: Whether to strip whitespace before validation

    Returns:
        The validated (and optionally stripped) string

    Raises:
        ValidationError: If value is not a non-empty string

    Examples:
        >>> validate_non_empty_string("test", "name")
        'test'
        >>> validate_non_empty_string("  test  ", "name", strip=True)
        'test'
        >>> validate_non_empty_string("", "name")
        Traceback (most recent call last):
        ...
        ValidationError: name cannot be empty
    """
    if not isinstance(value, str):
        raise TypeValidationError(
            f"{field_name} must be a string, got {type(value).__name__}",
            field=field_name,
            value=value,
        )

    result = value.strip() if strip else value

    if not result:
        raise ValidationError(
            f"{field_name} cannot be empty", field=field_name, value=value
        )

    return result


def validate_string_length(
    value: str,
    field_name: str,
    min_length: Optional[int] = None,
    max_length: Optional[int] = None,
) -> str:
    """Validate string length is within specified bounds.

    Args:
        value: The string to validate
        field_name: Name of the field being validated
        min_length: Minimum allowed length (inclusive)
        max_length: Maximum allowed length (inclusive)

    Returns:
        The validated string

    Raises:
        RangeValidationError: If string length is out of bounds

    Examples:
        >>> validate_string_length("test", "name", min_length=2, max_length=10)
        'test'
        >>> validate_string_length("a", "name", min_length=2)
        Traceback (most recent call last):
        ...
        RangeValidationError: name must be at least 2 characters (got 1)
    """
    length = len(value)

    if min_length is not None and length < min_length:
        raise RangeValidationError(
            f"{field_name} must be at least {min_length} characters (got {length})",
            field=field_name,
            value=value,
        )

    if max_length is not None and length > max_length:
        raise RangeValidationError(
            f"{field_name} must be at most {max_length} characters (got {length})",
            field=field_name,
            value=value,
        )

    return value


@lru_cache(maxsize=128)
def _compile_pattern(pattern: str) -> Pattern[str]:
    """Compile and cache regex patterns for performance.

    Args:
        pattern: Regex pattern string to compile

    Returns:
        Compiled regex Pattern object
    """
    return re.compile(pattern)


def validate_regex_pattern(
    value: str, pattern: Union[str, Pattern[str]], field_name: str
) -> str:
    """Validate that a string matches a regex pattern.

    Args:
        value: The string to validate
        pattern: Regex pattern (string or compiled Pattern)
        field_name: Name of the field being validated

    Returns:
        The validated string

    Raises:
        ValidationError: If string doesn't match pattern

    Examples:
        >>> validate_regex_pattern("test123", r"^[a-z0-9]+$", "username")
        'test123'
        >>> validate_regex_pattern("test@", r"^[a-z0-9]+$", "username")
        Traceback (most recent call last):
        ...
        ValidationError: username format is invalid
    """
    if isinstance(pattern, str):
        pattern = _compile_pattern(pattern)

    if not pattern.match(value):
        raise ValidationError(
            f"{field_name} format is invalid", field=field_name, value=value
        )

    return value


# ============================================================================
# ID Validation Functions
# ============================================================================


def validate_server_id(server_id: str) -> str:
    """Validate server ID format.

    Server IDs must contain only alphanumeric characters, hyphens, and underscores.

    Args:
        server_id: The server ID to validate

    Returns:
        The validated server ID

    Raises:
        IDValidationError: If server ID format is invalid

    Examples:
        >>> validate_server_id("my-server_123")
        'my-server_123'
        >>> validate_server_id("my server")
        Traceback (most recent call last):
        ...
        IDValidationError: Server ID must contain only alphanumeric characters, hyphens, and underscores
    """
    server_id = validate_non_empty_string(server_id, "Server ID")

    if not re.match(r"^[a-zA-Z0-9_-]+$", server_id):
        raise IDValidationError(
            "Server ID must contain only alphanumeric characters, hyphens, and underscores",
            field="server_id",
            value=server_id,
        )

    return server_id


def validate_identifier(
    identifier: str, field_name: str = "identifier", allow_hyphen: bool = True
) -> str:
    """Validate a Python-style identifier.

    Args:
        identifier: The identifier to validate
        field_name: Name of the field being validated
        allow_hyphen: Whether to allow hyphens in addition to underscores

    Returns:
        The validated identifier

    Raises:
        ValidationError: If identifier format is invalid

    Examples:
        >>> validate_identifier("my_var")
        'my_var'
        >>> validate_identifier("my-var", allow_hyphen=True)
        'my-var'
        >>> validate_identifier("123invalid")
        Traceback (most recent call last):
        ...
        ValidationError: identifier must start with a letter or underscore
    """
    identifier = validate_non_empty_string(identifier, field_name)

    if allow_hyphen:
        pattern = r"^[a-zA-Z_][a-zA-Z0-9_-]*$"
        error_msg = f"{field_name} must start with a letter or underscore and contain only alphanumeric characters, underscores, and hyphens"
    else:
        pattern = r"^[a-zA-Z_][a-zA-Z0-9_]*$"
        error_msg = f"{field_name} must start with a letter or underscore and contain only alphanumeric characters and underscores"

    if not re.match(pattern, identifier):
        raise ValidationError(error_msg, field=field_name, value=identifier)

    return identifier


# ============================================================================
# URL Validation Functions
# ============================================================================


def validate_url(
    url: str,
    field_name: str = "URL",
    require_scheme: bool = True,
    allowed_schemes: Optional[list[str]] = None,
) -> str:
    """Validate URL format.

    Args:
        url: The URL to validate
        field_name: Name of the field being validated
        require_scheme: Whether to require a scheme (http://, https://, etc.)
        allowed_schemes: List of allowed schemes (default: ["http", "https"])

    Returns:
        The validated URL

    Raises:
        URLValidationError: If URL format is invalid

    Examples:
        >>> validate_url("https://example.com")
        'https://example.com'
        >>> validate_url("http://localhost:8080/api")
        'http://localhost:8080/api'
        >>> validate_url("ftp://example.com", allowed_schemes=["ftp"])
        'ftp://example.com'
        >>> validate_url("not-a-url")
        Traceback (most recent call last):
        ...
        URLValidationError: URL must include a scheme (http://, https://, etc.)
    """
    url = validate_non_empty_string(url, field_name)

    if allowed_schemes is None:
        allowed_schemes = ["http", "https"]

    try:
        parsed = urlparse(url)

        if require_scheme and not parsed.scheme:
            raise URLValidationError(
                f"{field_name} must include a scheme (http://, https://, etc.)",
                field=field_name,
                value=url,
            )

        if parsed.scheme and parsed.scheme not in allowed_schemes:
            raise URLValidationError(
                f"{field_name} scheme must be one of {allowed_schemes}, got '{parsed.scheme}'",
                field=field_name,
                value=url,
            )

        if require_scheme and not parsed.netloc:
            raise URLValidationError(
                f"{field_name} must include a hostname",
                field=field_name,
                value=url,
            )

    except ValueError as e:
        raise URLValidationError(
            f"Invalid {field_name} format: {e}", field=field_name, value=url
        ) from e

    return url


def validate_http_url(url: str, field_name: str = "URL") -> str:
    """Validate HTTP/HTTPS URL format.

    Args:
        url: The URL to validate
        field_name: Name of the field being validated

    Returns:
        The validated URL

    Raises:
        URLValidationError: If URL is not a valid HTTP/HTTPS URL

    Examples:
        >>> validate_http_url("https://example.com")
        'https://example.com'
        >>> validate_http_url("ftp://example.com")
        Traceback (most recent call last):
        ...
        URLValidationError: URL must be a valid HTTP(S) URL
    """
    url = validate_non_empty_string(url, field_name)

    if not (url.startswith("http://") or url.startswith("https://")):
        raise URLValidationError(
            f"{field_name} must be a valid HTTP(S) URL",
            field=field_name,
            value=url,
        )

    return validate_url(url, field_name, allowed_schemes=["http", "https"])


# ============================================================================
# Type Validation Functions
# ============================================================================


def validate_type(
    value: Any, expected_type: type, field_name: str, allow_none: bool = False
) -> Any:
    """Validate that a value is of the expected type.

    Args:
        value: The value to validate
        expected_type: The expected type
        field_name: Name of the field being validated
        allow_none: Whether to allow None values

    Returns:
        The validated value

    Raises:
        TypeValidationError: If value is not of expected type

    Examples:
        >>> validate_type(42, int, "count")
        42
        >>> validate_type("test", int, "count")
        Traceback (most recent call last):
        ...
        TypeValidationError: count must be of type int, got str
        >>> validate_type(None, int, "count", allow_none=True)
    """
    if allow_none and value is None:
        return value

    if not isinstance(value, expected_type):
        raise TypeValidationError(
            f"{field_name} must be of type {expected_type.__name__}, got {type(value).__name__}",
            field=field_name,
            value=value,
        )

    return value


def validate_dict(
    value: Any,
    field_name: str,
    required_keys: Optional[list[str]] = None,
    allow_empty: bool = True,
) -> dict[str, Any]:
    """Validate that a value is a dictionary with optional required keys.

    Args:
        value: The value to validate
        field_name: Name of the field being validated
        required_keys: List of required keys
        allow_empty: Whether to allow empty dictionaries

    Returns:
        The validated dictionary

    Raises:
        TypeValidationError: If value is not a dictionary
        ValidationError: If required keys are missing or dict is empty when not allowed

    Examples:
        >>> validate_dict({"key": "value"}, "config")
        {'key': 'value'}
        >>> validate_dict({}, "config", allow_empty=False)
        Traceback (most recent call last):
        ...
        ValidationError: config cannot be empty
        >>> validate_dict({"a": 1}, "config", required_keys=["a", "b"])
        Traceback (most recent call last):
        ...
        ValidationError: config is missing required keys: b
    """
    validate_type(value, dict, field_name)

    if not allow_empty and not value:
        raise ValidationError(
            f"{field_name} cannot be empty", field=field_name, value=value
        )

    if required_keys:
        missing = [key for key in required_keys if key not in value]
        if missing:
            raise ValidationError(
                f"{field_name} is missing required keys: {', '.join(missing)}",
                field=field_name,
                value=value,
            )

    return value


def validate_list(
    value: Any,
    field_name: str,
    item_type: Optional[type] = None,
    min_length: Optional[int] = None,
    max_length: Optional[int] = None,
    allow_empty: bool = True,
) -> list[Any]:
    """Validate that a value is a list with optional constraints.

    Args:
        value: The value to validate
        field_name: Name of the field being validated
        item_type: Expected type of list items
        min_length: Minimum list length
        max_length: Maximum list length
        allow_empty: Whether to allow empty lists

    Returns:
        The validated list

    Raises:
        TypeValidationError: If value is not a list or items are wrong type
        RangeValidationError: If list length is out of bounds
        ValidationError: If list is empty when not allowed

    Examples:
        >>> validate_list([1, 2, 3], "numbers", item_type=int)
        [1, 2, 3]
        >>> validate_list([], "items", allow_empty=False)
        Traceback (most recent call last):
        ...
        ValidationError: items cannot be empty
        >>> validate_list([1, 2], "items", min_length=3)
        Traceback (most recent call last):
        ...
        RangeValidationError: items must have at least 3 items (got 2)
    """
    validate_type(value, list, field_name)

    if not allow_empty and not value:
        raise ValidationError(
            f"{field_name} cannot be empty", field=field_name, value=value
        )

    length = len(value)

    if min_length is not None and length < min_length:
        raise RangeValidationError(
            f"{field_name} must have at least {min_length} items (got {length})",
            field=field_name,
            value=value,
        )

    if max_length is not None and length > max_length:
        raise RangeValidationError(
            f"{field_name} must have at most {max_length} items (got {length})",
            field=field_name,
            value=value,
        )

    if item_type is not None:
        for i, item in enumerate(value):
            if not isinstance(item, item_type):
                raise TypeValidationError(
                    f"{field_name}[{i}] must be of type {item_type.__name__}, got {type(item).__name__}",
                    field=f"{field_name}[{i}]",
                    value=item,
                )

    return value


# ============================================================================
# Range Validation Functions
# ============================================================================


def validate_range(
    value: Union[int, float],
    field_name: str,
    min_value: Optional[Union[int, float]] = None,
    max_value: Optional[Union[int, float]] = None,
    inclusive: bool = True,
) -> Union[int, float]:
    """Validate that a numeric value is within a specified range.

    Args:
        value: The value to validate
        field_name: Name of the field being validated
        min_value: Minimum allowed value
        max_value: Maximum allowed value
        inclusive: Whether bounds are inclusive

    Returns:
        The validated value

    Raises:
        RangeValidationError: If value is out of range

    Examples:
        >>> validate_range(5, "count", min_value=0, max_value=10)
        5
        >>> validate_range(-1, "count", min_value=0)
        Traceback (most recent call last):
        ...
        RangeValidationError: count must be >= 0 (got -1)
        >>> validate_range(10, "count", min_value=0, max_value=10, inclusive=False)
        Traceback (most recent call last):
        ...
        RangeValidationError: count must be < 10 (got 10)
    """
    if not isinstance(value, (int, float)):
        raise TypeValidationError(
            f"{field_name} must be numeric, got {type(value).__name__}",
            field=field_name,
            value=value,
        )

    if min_value is not None:
        if inclusive and value < min_value:
            raise RangeValidationError(
                f"{field_name} must be >= {min_value} (got {value})",
                field=field_name,
                value=value,
            )
        elif not inclusive and value <= min_value:
            raise RangeValidationError(
                f"{field_name} must be > {min_value} (got {value})",
                field=field_name,
                value=value,
            )

    if max_value is not None:
        if inclusive and value > max_value:
            raise RangeValidationError(
                f"{field_name} must be <= {max_value} (got {value})",
                field=field_name,
                value=value,
            )
        elif not inclusive and value >= max_value:
            raise RangeValidationError(
                f"{field_name} must be < {max_value} (got {value})",
                field=field_name,
                value=value,
            )

    return value


def validate_positive(value: Union[int, float], field_name: str) -> Union[int, float]:
    """Validate that a numeric value is positive (> 0).

    Args:
        value: The value to validate
        field_name: Name of the field being validated

    Returns:
        The validated value

    Raises:
        RangeValidationError: If value is not positive

    Examples:
        >>> validate_positive(5, "count")
        5
        >>> validate_positive(0, "count")
        Traceback (most recent call last):
        ...
        RangeValidationError: count must be > 0 (got 0)
    """
    return validate_range(value, field_name, min_value=0, inclusive=False)


def validate_non_negative(
    value: Union[int, float], field_name: str
) -> Union[int, float]:
    """Validate that a numeric value is non-negative (>= 0).

    Args:
        value: The value to validate
        field_name: Name of the field being validated

    Returns:
        The validated value

    Raises:
        RangeValidationError: If value is negative

    Examples:
        >>> validate_non_negative(0, "count")
        0
        >>> validate_non_negative(-1, "count")
        Traceback (most recent call last):
        ...
        RangeValidationError: count must be >= 0 (got -1)
    """
    return validate_range(value, field_name, min_value=0, inclusive=True)


# ============================================================================
# Configuration Validation Functions
# ============================================================================


def validate_config_completeness(
    config: dict[str, Any], required_fields: list[str], config_name: str = "config"
) -> dict[str, Any]:
    """Validate that a configuration dictionary contains all required fields.

    Args:
        config: The configuration dictionary to validate
        required_fields: List of required field names
        config_name: Name of the configuration (for error messages)

    Returns:
        The validated configuration

    Raises:
        ConfigValidationError: If required fields are missing

    Examples:
        >>> validate_config_completeness({"a": 1, "b": 2}, ["a", "b"])
        {'a': 1, 'b': 2}
        >>> validate_config_completeness({"a": 1}, ["a", "b"])
        Traceback (most recent call last):
        ...
        ConfigValidationError: config is missing required fields: b
    """
    validate_dict(config, config_name, allow_empty=False)

    missing = [field for field in required_fields if field not in config]

    if missing:
        raise ConfigValidationError(
            f"{config_name} is missing required fields: {', '.join(missing)}",
            field=config_name,
            value=config,
        )

    return config


def validate_one_of(value: Any, allowed_values: list[Any], field_name: str) -> Any:
    """Validate that a value is one of the allowed values.

    Args:
        value: The value to validate
        allowed_values: List of allowed values
        field_name: Name of the field being validated

    Returns:
        The validated value

    Raises:
        ValidationError: If value is not in allowed values

    Examples:
        >>> validate_one_of("http", ["http", "https"], "scheme")
        'http'
        >>> validate_one_of("ftp", ["http", "https"], "scheme")
        Traceback (most recent call last):
        ...
        ValidationError: scheme must be one of ['http', 'https'], got 'ftp'
    """
    if value not in allowed_values:
        raise ValidationError(
            f"{field_name} must be one of {allowed_values}, got {value!r}",
            field=field_name,
            value=value,
        )

    return value


# ============================================================================
# Validation Decorators
# ============================================================================


def validate_arguments(**validators: Callable[[Any], Any]) -> Callable[[F], F]:
    """Decorator to validate function arguments.

    Args:
        **validators: Mapping of argument names to validation functions

    Returns:
        Decorated function

    Examples:
        >>> @validate_arguments(
        ...     url=validate_http_url,
        ...     count=lambda x: validate_positive(x, "count")
        ... )
        ... def fetch_data(url: str, count: int):
        ...     return f"Fetching {count} items from {url}"

        >>> fetch_data("https://api.example.com", 5)
        'Fetching 5 items from https://api.example.com'

        >>> fetch_data("ftp://example.com", 5)
        Traceback (most recent call last):
        ...
        URLValidationError: URL must be a valid HTTP(S) URL
    """

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Get function signature
            import inspect

            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()

            # Validate specified arguments
            for arg_name, validator in validators.items():
                if arg_name in bound_args.arguments:
                    try:
                        bound_args.arguments[arg_name] = validator(
                            bound_args.arguments[arg_name]
                        )
                    except ValidationError as e:
                        logger.error(
                            "Validation failed for argument '%s' in function '%s': %s",
                            arg_name,
                            func.__name__,
                            e,
                        )
                        raise

            return func(*bound_args.args, **bound_args.kwargs)

        return wrapper  # type: ignore

    return decorator


def validate_return_value(validator: Callable[[Any], Any]) -> Callable[[F], F]:
    """Decorator to validate function return value.

    Args:
        validator: Validation function to apply to return value

    Returns:
        Decorated function

    Examples:
        >>> @validate_return_value(lambda x: validate_dict(x, "result"))
        ... def get_config():
        ...     return {"key": "value"}

        >>> get_config()
        {'key': 'value'}

        >>> @validate_return_value(lambda x: validate_dict(x, "result"))
        ... def get_invalid():
        ...     return "not a dict"

        >>> get_invalid()
        Traceback (most recent call last):
        ...
        TypeValidationError: result must be of type dict, got str
    """

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            result = func(*args, **kwargs)
            try:
                return validator(result)
            except ValidationError as e:
                logger.error(
                    "Validation failed for return value of function '%s': %s",
                    func.__name__,
                    e,
                )
                raise

        return wrapper  # type: ignore

    return decorator


def validate_not_none(func: F) -> F:
    """Decorator to ensure function doesn't return None.

    Args:
        func: Function to decorate

    Returns:
        Decorated function

    Raises:
        ValidationError: If function returns None

    Examples:
        >>> @validate_not_none
        ... def get_value():
        ...     return "value"

        >>> get_value()
        'value'

        >>> @validate_not_none
        ... def get_none():
        ...     return None

        >>> get_none()
        Traceback (most recent call last):
        ...
        ValidationError: Function get_none returned None
    """

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        result = func(*args, **kwargs)
        if result is None:
            raise ValidationError(f"Function {func.__name__} returned None")
        return result

    return wrapper  # type: ignore


# ============================================================================
# Utility Functions
# ============================================================================


def is_valid_email(email: str) -> bool:
    """Check if a string is a valid email address format.

    Args:
        email: The email address to validate

    Returns:
        True if valid, False otherwise

    Examples:
        >>> is_valid_email("user@example.com")
        True
        >>> is_valid_email("invalid-email")
        False
    """
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def is_valid_semver(version: str) -> bool:
    """Check if a string is a valid semantic version.

    Args:
        version: The version string to validate

    Returns:
        True if valid semver, False otherwise

    Examples:
        >>> is_valid_semver("1.0.0")
        True
        >>> is_valid_semver("1.0.0-beta.1")
        True
        >>> is_valid_semver("invalid")
        False
    """
    pattern = r"^\d+\.\d+\.\d+(-[a-zA-Z0-9.-]+)?(\+[a-zA-Z0-9.-]+)?$"
    return bool(re.match(pattern, version))


def sanitize_string(value: str, max_length: Optional[int] = None) -> str:
    """Sanitize a string by removing control characters and optionally truncating.

    This function removes control characters (except newlines and tabs), normalizes
    whitespace by collapsing multiple spaces into single spaces, and optionally
    truncates the string to a maximum length.

    Args:
        value: The string to sanitize. Control characters will be replaced with spaces.
        max_length: Maximum length for the sanitized string. If provided and the
            sanitized string exceeds this length, it will be truncated. If None,
            no truncation is performed.

    Returns:
        The sanitized string with control characters removed, whitespace normalized,
        and optionally truncated to max_length.

    Raises:
        None: This function does not raise exceptions. Invalid input types will
            cause standard Python type errors.

    Examples:
        >>> sanitize_string("hello\\nworld")
        'hello world'
        >>> sanitize_string("long string", max_length=4)
        'long'
        >>> sanitize_string("text\\twith\\ttabs")
        'text with tabs'
        >>> sanitize_string("multiple    spaces")
        'multiple spaces'
    """
    # Remove control characters except newlines and tabs
    sanitized = "".join(
        char if char.isprintable() or char in "\n\t" else " " for char in value
    )

    # Normalize whitespace
    sanitized = " ".join(sanitized.split())

    # Truncate if needed
    if max_length is not None and len(sanitized) > max_length:
        sanitized = sanitized[:max_length]

    return sanitized
