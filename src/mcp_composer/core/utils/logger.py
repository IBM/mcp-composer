# utils/logger.py

import logging
import os
import sys


class LoggerFactory:
    """
    Produces consistent structured loggers across the system.
    """

    @staticmethod
    def get_logger(name: str = "mcp-composer", level: str = "INFO") -> logging.Logger:
        logger = logging.getLogger(name)

        # Convert level string to logging level constant
        log_level = getattr(logging, level.upper(), logging.INFO)

        # Set the logger level
        logger.setLevel(log_level)

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

        return logger
