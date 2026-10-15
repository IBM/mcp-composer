"""Strip developer .env service settings before each unit test.

``LoggerFactory`` loads a local ``.env`` at import. These keys must not leak
into the suite, especially ``MCP_COMPOSER_ENV=local`` and database URLs.
"""

from __future__ import annotations

import os

import pytest

EXTERNAL_ENV_KEYS = (
    "MCP_COMPOSER_ENV",
    "MCP_COMPOSER_LOG_LEVEL",
    "MCP_DATABASE_TYPE",
    "MCP_DATABASE_URL",
    "MCP_DATABASE_HOST",
    "MCP_DATABASE_NAME",
    "MCP_DATABASE_USER",
    "MCP_DATABASE_PASSWORD",
    "MCP_DATABASE_PORT",
    "MCP_DATABASE_TABLE_NAME",
    "MCP_DATABASE_API_KEY",
    "MCP_DATABASE_SERVICE_URL",
    "MCP_DATABASE_DB_NAME",
    "MCP_DATABASE_FILE_PATH",
    "MCP_USE_LOCAL_FILE_STORAGE",
    "SERVER_CONFIG_FILE_PATH",
    "POSTGRES_URL",
    "DATABASE_URL",
)


@pytest.fixture(autouse=True)
def isolate_external_env():
    """Remove service credentials and local-mode flags for the duration of a test."""
    saved = {key: os.environ.pop(key, None) for key in EXTERNAL_ENV_KEYS}
    try:
        yield
    finally:
        for key, value in saved.items():
            if value is not None:
                os.environ[key] = value
