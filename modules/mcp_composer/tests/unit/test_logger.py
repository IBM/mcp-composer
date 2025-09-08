"""Test module for logger.py"""

import pytest
import logging
import sys
from unittest.mock import Mock, patch, MagicMock
from mcp_composer.core.utils.logger import LoggerFactory


class TestLoggerFactory:
    """Test cases for LoggerFactory"""

    def test_get_logger_default_parameters(self):
        """Test get_logger with default parameters"""
        logger = LoggerFactory.get_logger()

        assert isinstance(logger, logging.Logger)
        assert logger.name == "mcp-composer"
        assert logger.level == logging.INFO

    def test_get_logger_custom_name(self):
        """Test get_logger with custom name"""
        logger = LoggerFactory.get_logger("custom-logger")

        assert isinstance(logger, logging.Logger)
        assert logger.name == "custom-logger"

    def test_get_logger_custom_level(self):
        """Test get_logger with custom level"""
        logger = LoggerFactory.get_logger(level="DEBUG")

        assert isinstance(logger, logging.Logger)
        assert logger.level == logging.DEBUG

    def test_get_logger_invalid_level(self):
        """Test get_logger with invalid level falls back to INFO"""
        logger = LoggerFactory.get_logger(level="INVALID_LEVEL")

        assert isinstance(logger, logging.Logger)
        assert logger.level == logging.INFO

    def test_get_logger_has_handlers(self):
        """Test get_logger when logger already has handlers"""
        # Get logger first time
        logger1 = LoggerFactory.get_logger("test-logger")

        # Get logger second time (should return existing logger)
        logger2 = LoggerFactory.get_logger("test-logger")

        assert logger1 is logger2
        assert len(logger1.handlers) > 0

    def test_get_logger_handlers_count(self):
        """Test that logger has correct number of handlers"""
        logger = LoggerFactory.get_logger()

        # Should have at least 1 handler (StreamHandler), and possibly 2 (StreamHandler + FileHandler)
        assert len(logger.handlers) >= 1
        assert len(logger.handlers) <= 2

    def test_get_logger_stream_handler(self):
        """Test that StreamHandler is configured correctly"""
        logger = LoggerFactory.get_logger()

        # Find StreamHandler
        stream_handler = None
        for handler in logger.handlers:
            if isinstance(handler, logging.StreamHandler):
                stream_handler = handler
                break

        assert stream_handler is not None
        assert stream_handler.stream == sys.stderr
        assert stream_handler.formatter is not None

    def test_get_logger_file_handler(self):
        """Test that FileHandler is configured correctly (if it exists)"""
        logger = LoggerFactory.get_logger()

        # Find FileHandler
        file_handler = None
        for handler in logger.handlers:
            if isinstance(handler, logging.FileHandler):
                file_handler = handler
                break

        # File handler might not exist due to permissions, so only test if it exists
        if file_handler is not None:
            assert file_handler.baseFilename.endswith("mcp_composer.log")
            assert file_handler.formatter is not None

    def test_get_logger_formatter(self):
        """Test that formatter is configured correctly"""
        logger = LoggerFactory.get_logger()

        # Check that all handlers have the same formatter
        formatter = None
        for handler in logger.handlers:
            if formatter is None:
                formatter = handler.formatter
            else:
                assert handler.formatter == formatter

        assert formatter is not None
        assert isinstance(formatter, logging.Formatter)

    def test_get_logger_formatter_format(self):
        """Test that formatter has correct format"""
        logger = LoggerFactory.get_logger()

        # Get formatter from any handler (ensure we have at least one handler)
        assert len(logger.handlers) > 0
        formatter = logger.handlers[0].formatter

        # Test format string
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        formatted = formatter.format(record)
        assert "Test message" in formatted
        assert "INFO" in formatted

    @patch("logging.getLogger")
    def test_get_logger_existing_logger_with_handlers(self, mock_get_logger):
        """Test get_logger when existing logger has handlers"""
        # Mock existing logger with handlers
        mock_logger = Mock()
        mock_logger.handlers = [Mock()]  # Non-empty handlers list
        mock_get_logger.return_value = mock_logger

        logger = LoggerFactory.get_logger()

        # Should return existing logger without adding handlers
        assert logger == mock_logger
        mock_logger.addHandler.assert_not_called()

    @patch("logging.getLogger")
    def test_get_logger_new_logger_without_handlers(self, mock_get_logger):
        """Test get_logger when creating new logger without handlers"""
        # Mock new logger without handlers
        mock_logger = Mock()
        mock_logger.handlers = []  # Empty handlers list
        mock_get_logger.return_value = mock_logger

        logger = LoggerFactory.get_logger()

        # Should add handlers to new logger
        assert logger == mock_logger
        assert mock_logger.addHandler.call_count == 2  # StreamHandler and FileHandler

    def test_get_logger_different_levels(self):
        """Test get_logger with different log levels"""
        levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

        for level in levels:
            logger = LoggerFactory.get_logger(level=level)
            expected_level = getattr(logging, level)
            assert logger.level == expected_level

    def test_get_logger_case_insensitive_level(self):
        """Test get_logger with case insensitive level"""
        logger = LoggerFactory.get_logger(level="debug")

        assert logger.level == logging.DEBUG

    def test_get_logger_multiple_calls_same_name(self):
        """Test multiple calls to get_logger with same name"""
        logger1 = LoggerFactory.get_logger("test-multiple")
        logger2 = LoggerFactory.get_logger("test-multiple")
        logger3 = LoggerFactory.get_logger("test-multiple")

        # All should be the same logger instance
        assert logger1 is logger2
        assert logger2 is logger3

    def test_get_logger_different_names(self):
        """Test get_logger with different names creates different loggers"""
        logger1 = LoggerFactory.get_logger("logger1")
        logger2 = LoggerFactory.get_logger("logger2")

        # Should be different logger instances
        assert logger1 is not logger2
        assert logger1.name == "logger1"
        assert logger2.name == "logger2"

    def test_logger_factory_static_method(self):
        """Test that get_logger is a static method"""
        # Should be able to call without instantiating the class
        logger = LoggerFactory.get_logger()
        assert isinstance(logger, logging.Logger)

    def test_logger_actual_logging(self):
        """Test that logger actually logs messages"""
        logger = LoggerFactory.get_logger("test-actual-logging")

        # Test that we can log without errors
        logger.info("Test info message")
        logger.warning("Test warning message")
        logger.error("Test error message")

        # If we get here without exceptions, the test passes
        assert True
