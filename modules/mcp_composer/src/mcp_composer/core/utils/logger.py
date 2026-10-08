# utils/logger.py

import logging
import os
import sys
from dotenv import load_dotenv

from mcp_composer.core.utils.log_redaction import SecretRedactionFilter

load_dotenv()


class LoggerFactory:
    """
    Produces consistent structured loggers across the system.
    """

    @staticmethod
    def _iter_filters(obj) -> list:
        """Return filter list; tolerate mocks/non-iterables used in unit tests."""
        filters = getattr(obj, "filters", None)
        if filters is None:
            return []
        try:
            return list(filters)
        except TypeError:
            return []

    @staticmethod
    def _ensure_secret_filter(logger: logging.Logger) -> None:
        """Attach secret redaction once so credentials never reach handlers."""
        if not any(
            isinstance(f, SecretRedactionFilter)
            for f in LoggerFactory._iter_filters(logger)
        ):
            logger.addFilter(SecretRedactionFilter())
        for handler in logger.handlers:
            if not any(
                isinstance(f, SecretRedactionFilter)
                for f in LoggerFactory._iter_filters(handler)
            ):
                handler.addFilter(SecretRedactionFilter())

    @staticmethod
    def get_logger(name: str = "mcp-composer", level: str = "INFO") -> logging.Logger:
        logger = logging.getLogger(name)

        # Check MCP_COMPOSER_LOG_LEVEL environment variable first, then use provided level, default to INFO
        env_log_level = os.getenv("MCP_COMPOSER_LOG_LEVEL", "").strip().upper()
        if env_log_level:
            log_level = getattr(logging, env_log_level, logging.INFO)
        else:
            # Convert level string to logging level constant
            log_level = getattr(logging, level.upper(), logging.INFO)

        # Set the logger level
        logger.setLevel(log_level)
        logger.propagate = False

        # Only add handlers if the logger doesn't have any handlers
        if not logger.handlers:
            # Create and configure StreamHandler
            stream_handler = logging.StreamHandler(sys.stderr)
            formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
            stream_handler.setFormatter(formatter)
            logger.addHandler(stream_handler)

            # Try to create and configure FileHandler, but don't fail if it's not possible
            try:
                # Use a more robust path for the log file
                log_file_path = os.path.join(os.getcwd(), "mcp_composer.log")
                file_handler = logging.FileHandler(log_file_path, mode="a")
                file_handler.setFormatter(formatter)
                logger.addHandler(file_handler)
            except (OSError, IOError, PermissionError):
                # If we can't create the file handler, just continue with stream handler only
                # This prevents the logger from failing completely
                pass

        LoggerFactory._ensure_secret_filter(logger)
        return logger
