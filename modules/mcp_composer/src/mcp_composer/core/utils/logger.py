# utils/logger.py

import logging
import os
import sys
from collections.abc import Mapping

from dotenv import load_dotenv

from mcp_composer.core.utils.log_redaction import redact_for_log, redact_message

load_dotenv()


def _redact_record(record: logging.LogRecord) -> None:
    """Scrub credential material before a handler or parent logger sees the record."""
    try:
        if record.args:
            if isinstance(record.args, Mapping):
                record.args = redact_for_log(record.args)
            elif isinstance(record.args, tuple):
                record.args = tuple(redact_for_log(arg) for arg in record.args)
            else:
                record.args = redact_for_log(record.args)
        if "message" in record.__dict__:
            del record.message
        rendered = record.getMessage()
        scrubbed = redact_message(rendered)
        if scrubbed != rendered:
            record.msg = scrubbed
            record.args = ()
            record.message = scrubbed
    except Exception:  # noqa: BLE001 — never break logging
        return


class _ComposerLogger(logging.Logger):
    """Logger whose records are redacted before any handler formats them."""

    def handle(self, record: logging.LogRecord) -> None:
        _redact_record(record)
        super().handle(record)


class LoggerFactory:
    """
    Produces consistent structured loggers across the system.

    Every logger it returns redacts passwords, tokens, API keys, and bearer
    values before the stream handler, the file handler, or a parent logger
    receives the record.
    """

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

        if type(logger) is logging.Logger:
            logger.__class__ = _ComposerLogger
        return logger
