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

        handler = logging.StreamHandler(sys.stderr)  # ✅ log to stderr only
        """ formatter = logging.Formatter(
            '{"timestamp": "%(asctime)s", "level": "%(levelname)s", '
            '"name": "%(name)s", "message": "%(message)s"}'
        ) """

        formatter=logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)

        logger.setLevel(getattr(logging, level.upper(), logging.INFO))
        logger.addHandler(handler)

        return logger
