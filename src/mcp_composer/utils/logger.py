# utils/logger.py

import logging
import sys


class LoggerFactory:
    """
    Produces consistent structured loggers across the system.
    """

    @staticmethod
    def get_logger(name: str = "mcp-composer", level: str = "INFO") -> logging.Logger:
        logger = logging.getLogger(name)
        if logger.hasHandlers():
            return logger  # Prevent duplicate handlers

        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            '{"timestamp": "%(asctime)s", "level": "%(levelname)s", '
            '"name": "%(name)s", "message": "%(message)s"}'
        )
        handler.setFormatter(formatter)

        logger.setLevel(logging.DEBUG)
        logger.addHandler(handler)
        return logger
