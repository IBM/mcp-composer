"""Comprehensive tests for validation utilities."""

import pytest
from mcp_composer.core.utils.validation import (
    ConfigValidationError,
    IDValidationError,
    RangeValidationError,
    TypeValidationError,
    URLValidationError,
    ValidationError,
    is_valid_email,
    is_valid_semver,
    sanitize_string,
    validate_arguments,
    validate_config_completeness,
    validate_dict,
    validate_http_url,
    validate_identifier,
    validate_list,
    validate_non_empty_string,
    validate_non_negative,
    validate_not_none,
    validate_one_of,
    validate_positive,
    validate_range,
    validate_regex_pattern,
    validate_return_value,
    validate_server_id,
    validate_string_length,
    validate_type,
    validate_url,
)

# ============================================================================
# String Validation Tests
# ============================================================================


class TestValidateNonEmptyString:
    """Tests for validate_non_empty_string function."""

    def test_valid_string(self):
        """Test validation of valid non-empty string."""
        assert validate_non_empty_string("test", "field") == "test"

    def test_string_with_whitespace_stripped(self):
        """Test that whitespace is stripped by default."""
        assert validate_non_empty_string("  test  ", "field") == "test"

    def test_string_with_whitespace_not_stripped(self):
        """Test that whitespace is preserved when strip=False."""
        assert validate_non_empty_string("  test  ", "field", strip=False) == "  test  "

    def test_empty_string_raises_error(self):
        """Test that empty string raises ValidationError."""
        with pytest.raises(ValidationError, match="field cannot be empty"):
            validate_non_empty_string("", "field")

    def test_whitespace_only_string_raises_error(self):
        """Test that whitespace-only string raises ValidationError."""
        with pytest.raises(ValidationError, match="field cannot be empty"):
            validate_non_empty_string("   ", "field")

    def test_non_string_raises_type_error(self):
        """Test that non-string value raises TypeValidationError."""
        with pytest.raises(TypeValidationError, match="field must be a string"):
            validate_non_empty_string(123, "field")

    def test_none_raises_type_error(self):
        """Test that None raises TypeValidationError."""
        with pytest.raises(TypeValidationError, match="field must be a string"):
            validate_non_empty_string(None, "field")


class TestValidateStringLength:
    """Tests for validate_string_length function."""

    def test_valid_length(self):
        """Test validation of string within bounds."""
        assert (
            validate_string_length("test", "field", min_length=2, max_length=10)
            == "test"
        )

    def test_exact_min_length(self):
        """Test string at exact minimum length."""
        assert validate_string_length("ab", "field", min_length=2) == "ab"

    def test_exact_max_length(self):
        """Test string at exact maximum length."""
        assert validate_string_length("test", "field", max_length=4) == "test"

    def test_below_min_length_raises_error(self):
        """Test that string below minimum length raises RangeValidationError."""
        with pytest.raises(
            RangeValidationError, match="field must be at least 5 characters"
        ):
            validate_string_length("test", "field", min_length=5)

    def test_above_max_length_raises_error(self):
        """Test that string above maximum length raises RangeValidationError."""
        with pytest.raises(
            RangeValidationError, match="field must be at most 3 characters"
        ):
            validate_string_length("test", "field", max_length=3)

    def test_no_constraints(self):
        """Test validation with no length constraints."""
        assert validate_string_length("any length", "field") == "any length"


class TestValidateRegexPattern:
    """Tests for validate_regex_pattern function."""

    def test_valid_pattern_match(self):
        """Test validation of string matching pattern."""
        assert validate_regex_pattern("test123", r"^[a-z0-9]+$", "field") == "test123"

    def test_compiled_pattern(self):
        """Test validation with compiled regex pattern."""
        import re

        pattern = re.compile(r"^[a-z0-9]+$")
        assert validate_regex_pattern("test123", pattern, "field") == "test123"

    def test_pattern_mismatch_raises_error(self):
        """Test that non-matching string raises ValidationError."""
        with pytest.raises(ValidationError, match="field format is invalid"):
            validate_regex_pattern("test@", r"^[a-z0-9]+$", "field")


# ============================================================================
# ID Validation Tests
# ============================================================================


class TestValidateServerId:
    """Tests for validate_server_id function."""

    def test_valid_server_id(self):
        """Test validation of valid server ID."""
        assert validate_server_id("my-server_123") == "my-server_123"

    def test_alphanumeric_only(self):
        """Test server ID with only alphanumeric characters."""
        assert validate_server_id("server123") == "server123"

    def test_with_hyphens(self):
        """Test server ID with hyphens."""
        assert validate_server_id("my-server") == "my-server"

    def test_with_underscores(self):
        """Test server ID with underscores."""
        assert validate_server_id("my_server") == "my_server"

    def test_invalid_characters_raises_error(self):
        """Test that server ID with invalid characters raises IDValidationError."""
        with pytest.raises(IDValidationError, match="Server ID must contain only"):
            validate_server_id("my server")

    def test_special_characters_raises_error(self):
        """Test that server ID with special characters raises IDValidationError."""
        with pytest.raises(IDValidationError):
            validate_server_id("my@server")

    def test_empty_string_raises_error(self):
        """Test that empty server ID raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_server_id("")


class TestValidateIdentifier:
    """Tests for validate_identifier function."""

    def test_valid_identifier(self):
        """Test validation of valid identifier."""
        assert validate_identifier("my_var") == "my_var"

    def test_identifier_with_hyphen(self):
        """Test identifier with hyphen when allowed."""
        assert validate_identifier("my-var", allow_hyphen=True) == "my-var"

    def test_identifier_with_hyphen_not_allowed(self):
        """Test that hyphen raises error when not allowed."""
        with pytest.raises(ValidationError):
            validate_identifier("my-var", allow_hyphen=False)

    def test_starts_with_number_raises_error(self):
        """Test that identifier starting with number raises ValidationError."""
        with pytest.raises(
            ValidationError, match="must start with a letter or underscore"
        ):
            validate_identifier("123invalid")

    def test_starts_with_underscore(self):
        """Test identifier starting with underscore."""
        assert validate_identifier("_private") == "_private"


# ============================================================================
# URL Validation Tests
# ============================================================================


class TestValidateUrl:
    """Tests for validate_url function."""

    def test_valid_http_url(self):
        """Test validation of valid HTTP URL."""
        assert validate_url("http://example.com") == "http://example.com"

    def test_valid_https_url(self):
        """Test validation of valid HTTPS URL."""
        assert validate_url("https://example.com") == "https://example.com"

    def test_url_with_port(self):
        """Test URL with port number."""
        assert validate_url("http://localhost:8080") == "http://localhost:8080"

    def test_url_with_path(self):
        """Test URL with path."""
        assert (
            validate_url("https://example.com/api/v1") == "https://example.com/api/v1"
        )

    def test_missing_scheme_raises_error(self):
        """Test that URL without scheme raises URLValidationError."""
        with pytest.raises(URLValidationError, match="must include a scheme"):
            validate_url("example.com")

    def test_invalid_scheme_raises_error(self):
        """Test that URL with invalid scheme raises URLValidationError."""
        with pytest.raises(URLValidationError, match="scheme must be one of"):
            validate_url("ftp://example.com")

    def test_custom_allowed_schemes(self):
        """Test URL validation with custom allowed schemes."""
        assert (
            validate_url("ftp://example.com", allowed_schemes=["ftp"])
            == "ftp://example.com"
        )

    def test_missing_hostname_raises_error(self):
        """Test that URL without hostname raises URLValidationError."""
        with pytest.raises(URLValidationError, match="must include a hostname"):
            validate_url("http://")


class TestValidateHttpUrl:
    """Tests for validate_http_url function."""

    def test_valid_http_url(self):
        """Test validation of valid HTTP URL."""
        assert validate_http_url("http://example.com") == "http://example.com"

    def test_valid_https_url(self):
        """Test validation of valid HTTPS URL."""
        assert validate_http_url("https://example.com") == "https://example.com"

    def test_ftp_url_raises_error(self):
        """Test that FTP URL raises URLValidationError."""
        with pytest.raises(URLValidationError, match="must be a valid HTTP\\(S\\) URL"):
            validate_http_url("ftp://example.com")

    def test_no_scheme_raises_error(self):
        """Test that URL without scheme raises URLValidationError."""
        with pytest.raises(URLValidationError, match="must be a valid HTTP\\(S\\) URL"):
            validate_http_url("example.com")


# ============================================================================
# Type Validation Tests
# ============================================================================


class TestValidateType:
    """Tests for validate_type function."""

    def test_valid_type(self):
        """Test validation of correct type."""
        assert validate_type(42, int, "field") == 42

    def test_string_type(self):
        """Test validation of string type."""
        assert validate_type("test", str, "field") == "test"

    def test_dict_type(self):
        """Test validation of dict type."""
        assert validate_type({"key": "value"}, dict, "field") == {"key": "value"}

    def test_wrong_type_raises_error(self):
        """Test that wrong type raises TypeValidationError."""
        with pytest.raises(
            TypeValidationError, match="field must be of type int, got str"
        ):
            validate_type("test", int, "field")

    def test_none_not_allowed_raises_error(self):
        """Test that None raises error when not allowed."""
        with pytest.raises(TypeValidationError):
            validate_type(None, int, "field")

    def test_none_allowed(self):
        """Test that None is allowed when allow_none=True."""
        assert validate_type(None, int, "field", allow_none=True) is None


class TestValidateDict:
    """Tests for validate_dict function."""

    def test_valid_dict(self):
        """Test validation of valid dictionary."""
        assert validate_dict({"key": "value"}, "field") == {"key": "value"}

    def test_empty_dict_allowed(self):
        """Test that empty dict is allowed by default."""
        assert validate_dict({}, "field") == {}

    def test_empty_dict_not_allowed_raises_error(self):
        """Test that empty dict raises error when not allowed."""
        with pytest.raises(ValidationError, match="field cannot be empty"):
            validate_dict({}, "field", allow_empty=False)

    def test_required_keys_present(self):
        """Test validation with all required keys present."""
        assert validate_dict({"a": 1, "b": 2}, "field", required_keys=["a", "b"]) == {
            "a": 1,
            "b": 2,
        }

    def test_missing_required_keys_raises_error(self):
        """Test that missing required keys raises ValidationError."""
        with pytest.raises(ValidationError, match="field is missing required keys: b"):
            validate_dict({"a": 1}, "field", required_keys=["a", "b"])

    def test_non_dict_raises_error(self):
        """Test that non-dict value raises TypeValidationError."""
        with pytest.raises(TypeValidationError):
            validate_dict("not a dict", "field")


class TestValidateList:
    """Tests for validate_list function."""

    def test_valid_list(self):
        """Test validation of valid list."""
        assert validate_list([1, 2, 3], "field") == [1, 2, 3]

    def test_empty_list_allowed(self):
        """Test that empty list is allowed by default."""
        assert validate_list([], "field") == []

    def test_empty_list_not_allowed_raises_error(self):
        """Test that empty list raises error when not allowed."""
        with pytest.raises(ValidationError, match="field cannot be empty"):
            validate_list([], "field", allow_empty=False)

    def test_item_type_validation(self):
        """Test validation of list item types."""
        assert validate_list([1, 2, 3], "field", item_type=int) == [1, 2, 3]

    def test_wrong_item_type_raises_error(self):
        """Test that wrong item type raises TypeValidationError."""
        with pytest.raises(
            TypeValidationError, match="field\\[1\\] must be of type int"
        ):
            validate_list([1, "two", 3], "field", item_type=int)

    def test_min_length_validation(self):
        """Test validation of minimum list length."""
        assert validate_list([1, 2, 3], "field", min_length=2) == [1, 2, 3]

    def test_below_min_length_raises_error(self):
        """Test that list below minimum length raises RangeValidationError."""
        with pytest.raises(
            RangeValidationError, match="field must have at least 3 items"
        ):
            validate_list([1, 2], "field", min_length=3)

    def test_max_length_validation(self):
        """Test validation of maximum list length."""
        assert validate_list([1, 2], "field", max_length=3) == [1, 2]

    def test_above_max_length_raises_error(self):
        """Test that list above maximum length raises RangeValidationError."""
        with pytest.raises(
            RangeValidationError, match="field must have at most 2 items"
        ):
            validate_list([1, 2, 3], "field", max_length=2)


# ============================================================================
# Range Validation Tests
# ============================================================================


class TestValidateRange:
    """Tests for validate_range function."""

    def test_value_within_range(self):
        """Test validation of value within range."""
        assert validate_range(5, "field", min_value=0, max_value=10) == 5

    def test_value_at_min_inclusive(self):
        """Test value at minimum (inclusive)."""
        assert validate_range(0, "field", min_value=0) == 0

    def test_value_at_max_inclusive(self):
        """Test value at maximum (inclusive)."""
        assert validate_range(10, "field", max_value=10) == 10

    def test_value_below_min_raises_error(self):
        """Test that value below minimum raises RangeValidationError."""
        with pytest.raises(RangeValidationError, match="field must be >= 0"):
            validate_range(-1, "field", min_value=0)

    def test_value_above_max_raises_error(self):
        """Test that value above maximum raises RangeValidationError."""
        with pytest.raises(RangeValidationError, match="field must be <= 10"):
            validate_range(11, "field", max_value=10)

    def test_exclusive_bounds(self):
        """Test validation with exclusive bounds."""
        assert (
            validate_range(5, "field", min_value=0, max_value=10, inclusive=False) == 5
        )

    def test_value_at_min_exclusive_raises_error(self):
        """Test that value at minimum raises error with exclusive bounds."""
        with pytest.raises(RangeValidationError, match="field must be > 0"):
            validate_range(0, "field", min_value=0, inclusive=False)

    def test_float_values(self):
        """Test validation with float values."""
        assert validate_range(5.5, "field", min_value=0.0, max_value=10.0) == 5.5

    def test_non_numeric_raises_error(self):
        """Test that non-numeric value raises TypeValidationError."""
        with pytest.raises(TypeValidationError, match="field must be numeric"):
            validate_range("5", "field", min_value=0)


class TestValidatePositive:
    """Tests for validate_positive function."""

    def test_positive_value(self):
        """Test validation of positive value."""
        assert validate_positive(5, "field") == 5

    def test_zero_raises_error(self):
        """Test that zero raises RangeValidationError."""
        with pytest.raises(RangeValidationError, match="field must be > 0"):
            validate_positive(0, "field")

    def test_negative_raises_error(self):
        """Test that negative value raises RangeValidationError."""
        with pytest.raises(RangeValidationError):
            validate_positive(-1, "field")


class TestValidateNonNegative:
    """Tests for validate_non_negative function."""

    def test_positive_value(self):
        """Test validation of positive value."""
        assert validate_non_negative(5, "field") == 5

    def test_zero_allowed(self):
        """Test that zero is allowed."""
        assert validate_non_negative(0, "field") == 0

    def test_negative_raises_error(self):
        """Test that negative value raises RangeValidationError."""
        with pytest.raises(RangeValidationError, match="field must be >= 0"):
            validate_non_negative(-1, "field")


# ============================================================================
# Configuration Validation Tests
# ============================================================================


class TestValidateConfigCompleteness:
    """Tests for validate_config_completeness function."""

    def test_all_required_fields_present(self):
        """Test validation with all required fields present."""
        config = {"a": 1, "b": 2, "c": 3}
        assert validate_config_completeness(config, ["a", "b"]) == config

    def test_missing_required_fields_raises_error(self):
        """Test that missing required fields raises ConfigValidationError."""
        with pytest.raises(
            ConfigValidationError, match="config is missing required fields: b, c"
        ):
            validate_config_completeness({"a": 1}, ["a", "b", "c"])

    def test_empty_config_raises_error(self):
        """Test that empty config raises ValidationError."""
        with pytest.raises(ValidationError):
            validate_config_completeness({}, ["a"])


class TestValidateOneOf:
    """Tests for validate_one_of function."""

    def test_value_in_allowed_list(self):
        """Test validation of value in allowed list."""
        assert validate_one_of("http", ["http", "https"], "scheme") == "http"

    def test_value_not_in_allowed_list_raises_error(self):
        """Test that value not in allowed list raises ValidationError."""
        with pytest.raises(ValidationError, match="scheme must be one of"):
            validate_one_of("ftp", ["http", "https"], "scheme")

    def test_numeric_values(self):
        """Test validation with numeric values."""
        assert validate_one_of(1, [1, 2, 3], "option") == 1


# ============================================================================
# Decorator Tests
# ============================================================================


class TestValidateArguments:
    """Tests for validate_arguments decorator."""

    def test_valid_arguments(self):
        """Test decorator with valid arguments."""

        @validate_arguments(
            name=lambda x: validate_non_empty_string(x, "name"),
            count=lambda x: validate_positive(x, "count"),
        )
        def test_func(name: str, count: int):
            return f"{name}: {count}"

        assert test_func("test", 5) == "test: 5"

    def test_invalid_argument_raises_error(self):
        """Test that invalid argument raises ValidationError."""

        @validate_arguments(count=lambda x: validate_positive(x, "count"))
        def test_func(count: int):
            return count

        with pytest.raises(RangeValidationError):
            test_func(0)


class TestValidateReturnValue:
    """Tests for validate_return_value decorator."""

    def test_valid_return_value(self):
        """Test decorator with valid return value."""

        @validate_return_value(lambda x: validate_dict(x, "result"))
        def test_func():
            return {"key": "value"}

        assert test_func() == {"key": "value"}

    def test_invalid_return_value_raises_error(self):
        """Test that invalid return value raises ValidationError."""

        @validate_return_value(lambda x: validate_dict(x, "result"))
        def test_func():
            return "not a dict"

        with pytest.raises(TypeValidationError):
            test_func()


class TestValidateNotNone:
    """Tests for validate_not_none decorator."""

    def test_non_none_return_value(self):
        """Test decorator with non-None return value."""

        @validate_not_none
        def test_func():
            return "value"

        assert test_func() == "value"

    def test_none_return_value_raises_error(self):
        """Test that None return value raises ValidationError."""

        @validate_not_none
        def test_func():
            return None

        with pytest.raises(ValidationError, match="Function test_func returned None"):
            test_func()


# ============================================================================
# Utility Function Tests
# ============================================================================


class TestIsValidEmail:
    """Tests for is_valid_email function."""

    def test_valid_email(self):
        """Test validation of valid email."""
        assert is_valid_email("user@example.com") is True

    def test_email_with_subdomain(self):
        """Test email with subdomain."""
        assert is_valid_email("user@mail.example.com") is True

    def test_email_with_plus(self):
        """Test email with plus sign."""
        assert is_valid_email("user+tag@example.com") is True

    def test_invalid_email_no_at(self):
        """Test invalid email without @ symbol."""
        assert is_valid_email("userexample.com") is False

    def test_invalid_email_no_domain(self):
        """Test invalid email without domain."""
        assert is_valid_email("user@") is False

    def test_invalid_email_no_tld(self):
        """Test invalid email without TLD."""
        assert is_valid_email("user@example") is False


class TestIsValidSemver:
    """Tests for is_valid_semver function."""

    def test_valid_semver(self):
        """Test validation of valid semantic version."""
        assert is_valid_semver("1.0.0") is True

    def test_semver_with_prerelease(self):
        """Test semantic version with prerelease."""
        assert is_valid_semver("1.0.0-beta.1") is True

    def test_semver_with_build(self):
        """Test semantic version with build metadata."""
        assert is_valid_semver("1.0.0+build.123") is True

    def test_semver_with_both(self):
        """Test semantic version with prerelease and build."""
        assert is_valid_semver("1.0.0-beta.1+build.123") is True

    def test_invalid_semver_two_parts(self):
        """Test invalid semantic version with only two parts."""
        assert is_valid_semver("1.0") is False

    def test_invalid_semver_text(self):
        """Test invalid semantic version with text."""
        assert is_valid_semver("invalid") is False


class TestSanitizeString:
    """Tests for sanitize_string function."""

    def test_normal_string(self):
        """Test sanitization of normal string."""
        assert sanitize_string("hello world") == "hello world"

    def test_string_with_newlines(self):
        """Test sanitization of string with newlines."""
        assert sanitize_string("hello\nworld") == "hello world"

    def test_string_with_tabs(self):
        """Test sanitization of string with tabs."""
        assert sanitize_string("hello\tworld") == "hello world"

    def test_string_with_multiple_spaces(self):
        """Test sanitization normalizes multiple spaces."""
        assert sanitize_string("hello    world") == "hello world"

    def test_truncation(self):
        """Test string truncation."""
        assert sanitize_string("long string", max_length=4) == "long"

    def test_no_truncation_when_shorter(self):
        """Test that shorter strings are not truncated."""
        assert sanitize_string("short", max_length=10) == "short"


# ============================================================================
# Exception Tests
# ============================================================================


class TestValidationExceptions:
    """Tests for validation exception classes."""

    def test_validation_error_with_field(self):
        """Test ValidationError with field information."""
        error = ValidationError("Test error", field="test_field", value="test_value")
        assert error.field == "test_field"
        assert error.value == "test_value"
        assert str(error) == "Test error"

    def test_url_validation_error(self):
        """Test URLValidationError is subclass of ValidationError."""
        error = URLValidationError("Invalid URL")
        assert isinstance(error, ValidationError)

    def test_id_validation_error(self):
        """Test IDValidationError is subclass of ValidationError."""
        error = IDValidationError("Invalid ID")
        assert isinstance(error, ValidationError)

    def test_range_validation_error(self):
        """Test RangeValidationError is subclass of ValidationError."""
        error = RangeValidationError("Out of range")
        assert isinstance(error, ValidationError)

    def test_type_validation_error(self):
        """Test TypeValidationError is subclass of ValidationError."""
        error = TypeValidationError("Wrong type")
        assert isinstance(error, ValidationError)

    def test_config_validation_error(self):
        """Test ConfigValidationError is subclass of ValidationError."""
        error = ConfigValidationError("Invalid config")
        assert isinstance(error, ValidationError)
