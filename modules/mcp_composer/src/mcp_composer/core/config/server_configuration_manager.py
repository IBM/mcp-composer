"""
Server Configuration Manager for MCP Composer.

Handles database configuration, unified configuration processing, and config state management.
"""

import os
import sys
from typing import Any, Dict, Optional, Union

from mcp_composer.core.config.config_loader import ConfigLoader
from mcp_composer.core.settings.version_control_manager import ConfigManager
from mcp_composer.core.utils import (
    AllServersValidator,
    ValidationError,
    get_version_adapter,
)
from mcp_composer.core.utils.logger import LoggerFactory
from mcp_composer.store.database import DatabaseInterface
from mcp_composer.store.cloudant_adapter import CloudantAdapter
from mcp_composer.store.local_file_adapter import LocalFileAdapter
from mcp_composer.store.postgres_adapter import PostgresAdapter

logger = LoggerFactory.get_logger()


class ServerConfigurationManager:
    """Manages server configuration including database and unified config."""

    def __init__(
        self,
        version_adapter_config: Optional[Dict[str, Any]] = None,
    ):
        """Initialize the configuration manager."""
        self._config_manager = ConfigManager(
            get_version_adapter(version_adapter_config)
        )
        self._config: list[dict] = []
        self._unified_config_applied = False
        self._unified_config = None
        self._unified_config_type = None

    @property
    def config_manager(self) -> ConfigManager:
        """Get the config manager instance."""
        return self._config_manager

    @property
    def config(self) -> list[dict]:
        """Get the current server configuration list."""
        return self._config

    @property
    def unified_config(self):
        """Get the unified configuration object."""
        return self._unified_config

    @property
    def unified_config_applied(self) -> bool:
        """Check if unified config has been applied."""
        return self._unified_config_applied

    @property
    def unified_config_type(self):
        """Get the unified config type."""
        return self._unified_config_type

    def get_database_from_config(
        self,
        database_config: Optional[Union[Dict[str, Any], DatabaseInterface]] = None,
    ) -> Optional[DatabaseInterface]:
        """
        Create and return a database instance from configuration.

        Args:
            database_config: Database configuration dict or DatabaseInterface instance

        Returns:
            DatabaseInterface instance or None if no database configured
        """
        env_db_config = self.get_database_config_from_env()
        effective_db_config = env_db_config or database_config

        if effective_db_config:
            logger.info("Database configuration found")
            try:
                if isinstance(effective_db_config, DatabaseInterface):
                    database = effective_db_config
                    logger.info(
                        "Database configuration loaded successfully (Custom Database Interface)"
                    )
                elif effective_db_config.get("type") == "cloudant":
                    required_keys = ["api_key", "service_url"]
                    if not all(k in effective_db_config for k in required_keys):
                        error_msg = "Missing required Cloudant config keys: api_key, service_url"
                        logger.error("Database configuration error: %s", error_msg)
                        raise ValueError(error_msg)

                    database = CloudantAdapter(
                        api_key=effective_db_config["api_key"],
                        service_url=effective_db_config["service_url"],
                        db_name=effective_db_config.get("db_name", "mcp_server"),
                    )
                    logger.info("Database configuration loaded successfully (Cloudant)")
                elif effective_db_config.get("type") == "local_file":
                    database = LocalFileAdapter(
                        file_path=effective_db_config.get("file_path")
                    )
                    logger.info(
                        "Database configuration loaded successfully (Local File)"
                    )
                elif effective_db_config.get("type") == "postgres":
                    # Check if URL is provided (preferred method)
                    if "url" in effective_db_config:
                        database = PostgresAdapter(
                            url=effective_db_config["url"],
                            table_name=effective_db_config.get(
                                "table_name", "mcp_servers"
                            ),
                        )
                        logger.info(
                            "Database configuration loaded successfully (PostgreSQL via URL)"
                        )
                    else:
                        # Use individual parameters
                        required_keys = ["host", "database", "user", "password"]
                        if not all(k in effective_db_config for k in required_keys):
                            error_msg = (
                                "Missing required PostgreSQL config keys: host, "
                                "database, user, password (or provide 'url')"
                            )
                            logger.error("Database configuration error: %s", error_msg)
                            raise ValueError(error_msg)

                        database = PostgresAdapter(
                            host=effective_db_config["host"],
                            port=effective_db_config.get("port", 5432),
                            database=effective_db_config["database"],
                            user=effective_db_config["user"],
                            password=effective_db_config["password"],
                            table_name=effective_db_config.get(
                                "table_name", "mcp_servers"
                            ),
                        )
                        logger.info(
                            "Database configuration loaded successfully (PostgreSQL)"
                        )
                else:
                    error_msg = (
                        f"Unsupported database type: {effective_db_config.get('type')}"
                    )
                    logger.error("Database configuration error: %s", error_msg)
                    raise ValueError(error_msg)
                return database
            except Exception as e:
                logger.error("Failed to initialize database: %s", e)
                raise
        else:
            # No database config provided - check if local file storage is enabled via env
            logger.info("No database configuration provided")
            use_local_file = (
                os.getenv("MCP_USE_LOCAL_FILE_STORAGE", "false").strip().lower()
            )
            if use_local_file in ("true", "1", "yes", "on"):
                database = LocalFileAdapter()
                logger.info("Local file storage enabled via environment variable")
                return database
            else:
                logger.info(
                    "No database configured - running without persistent storage"
                )
                return None

    def get_database_config_from_env(self) -> Optional[Dict[str, Any]]:
        """
        Get database configuration from environment variables.

        Environment variables:
        - MCP_DATABASE_TYPE: Type of database ("cloudant", "local_file", or "postgres")
        - MCP_DATABASE_API_KEY: API key for Cloudant (required for cloudant type)
        - MCP_DATABASE_SERVICE_URL: Service URL for Cloudant (required for cloudant type)
        - MCP_DATABASE_NAME: Database name (optional, defaults to "mcp_servers")
        - MCP_DATABASE_FILE_PATH: File path for local file storage (optional for local_file type)
        - MCP_DATABASE_URL: PostgreSQL connection URL (preferred for postgres type)
        - MCP_DATABASE_HOST: PostgreSQL host (required for postgres type if URL not provided)
        - MCP_DATABASE_PORT: PostgreSQL port (optional for postgres type, defaults to 5432)
        - MCP_DATABASE_USER: PostgreSQL user (required for postgres type if URL not provided)
        - MCP_DATABASE_PASSWORD: PostgreSQL password (required for postgres type if URL not provided)
        - MCP_DATABASE_TABLE_NAME: PostgreSQL table name (optional for postgres type, defaults to "mcp_servers")

        Returns:
            Dict containing database configuration or None if no env config found
        """
        db_type = os.getenv("MCP_DATABASE_TYPE")
        if not db_type:
            logger.info("No database type specified in environment variables")
            return None

        # Validate database type
        db_type = db_type.strip().lower()
        if db_type not in ["cloudant", "local_file", "postgres"]:
            logger.warning(
                "Unsupported database type in environment: %s. Supported types: cloudant, local_file, postgres",
                db_type,
            )
            return None

        config = {"type": db_type}

        if db_type == "cloudant":
            api_key = os.getenv("MCP_DATABASE_API_KEY")
            service_url = os.getenv("MCP_DATABASE_SERVICE_URL")

            # Validate required fields - fail fast on missing required fields
            if not api_key or not api_key.strip():
                error_msg = "Cloudant database type specified but MCP_DATABASE_API_KEY is missing or empty"
                logger.error("Database configuration error: %s", error_msg)
                raise ValueError(error_msg)
            if not service_url or not service_url.strip():
                error_msg = "Cloudant database type specified but MCP_DATABASE_SERVICE_URL is missing or empty"
                logger.error("Database configuration error: %s", error_msg)
                raise ValueError(error_msg)

            # Validate service URL format - fail fast on invalid format
            if not service_url.startswith(("http://", "https://")):
                error_msg = f"Invalid service URL format: {service_url}. Must start with http:// or https://"
                logger.error("Database configuration error: %s", error_msg)
                raise ValueError(error_msg)

            config.update(
                {
                    "api_key": api_key.strip(),
                    "service_url": service_url.strip(),
                    "db_name": os.getenv("MCP_DATABASE_DB_NAME", "mcp_servers").strip(),
                }
            )
            logger.info(
                "Database configuration loaded from environment variables (Cloudant)"
            )

        elif db_type == "local_file":
            file_path = os.getenv("MCP_DATABASE_FILE_PATH")
            if file_path and file_path.strip():
                # Validate file path format - warn but don't fail for file extensions
                if not file_path.strip().endswith((".json", ".db", ".sqlite")):
                    logger.warning(
                        "File path should end with .json, .db, or .sqlite: %s",
                        file_path,
                    )
                config["file_path"] = file_path.strip()
            logger.info(
                "Database configuration loaded from environment variables (Local File)"
            )

        elif db_type == "postgres":
            # Check if URL is provided (preferred method)
            url = os.getenv("MCP_DATABASE_URL")
            if url and url.strip():
                config["url"] = url.strip()
                config["table_name"] = os.getenv(
                    "MCP_DATABASE_TABLE_NAME", "mcp_servers"
                ).strip()
                logger.info(
                    "Database configuration loaded from environment variables (PostgreSQL via URL)"
                )
            else:
                # Use individual parameters
                host = os.getenv("MCP_DATABASE_HOST")
                database = os.getenv("MCP_DATABASE_NAME")
                user = os.getenv("MCP_DATABASE_USER")
                password = os.getenv("MCP_DATABASE_PASSWORD")

                # Validate required fields - fail fast on missing required fields
                if not host or not host.strip():
                    error_msg = (
                        "PostgreSQL database type specified but MCP_DATABASE_HOST is "
                        "missing or empty (or provide MCP_DATABASE_URL)"
                    )
                    logger.error("Database configuration error: %s", error_msg)
                    raise ValueError(error_msg)
                if not database or not database.strip():
                    error_msg = (
                        "PostgreSQL database type specified but MCP_DATABASE_NAME "
                        "is missing or empty (or provide MCP_DATABASE_URL)"
                    )
                    logger.error("Database configuration error: %s", error_msg)
                    raise ValueError(error_msg)
                if not user or not user.strip():
                    error_msg = (
                        "PostgreSQL database type specified but MCP_DATABASE_USER is "
                        "missing or empty (or provide MCP_DATABASE_URL)"
                    )
                    logger.error("Database configuration error: %s", error_msg)
                    raise ValueError(error_msg)
                if not password or not password.strip():
                    error_msg = (
                        "PostgreSQL database type specified but "
                        "MCP_DATABASE_PASSWORD is missing or empty "
                        "(or provide MCP_DATABASE_URL)"
                    )
                    logger.error("Database configuration error: %s", error_msg)
                    raise ValueError(error_msg)

                config["host"] = host.strip()
                config["port"] = int(os.getenv("MCP_DATABASE_PORT", "5432"))  # type: ignore
                config["database"] = database.strip()
                config["user"] = user.strip()
                config["password"] = password.strip()
                config["table_name"] = os.getenv(
                    "MCP_DATABASE_TABLE_NAME", "mcp_servers"
                ).strip()
                logger.info(
                    "Database configuration loaded from environment variables (PostgreSQL)"
                )

        return config

    def process_config(
        self,
        config: Optional[Union[list[dict], str]],
        composer: Any,  # MCPComposer instance
    ) -> None:
        """
        Process server configuration (unified config file or list of configs).

        Args:
            config: Either a file path (str) or list of server config dicts
            composer: MCPComposer instance for unified config processing
        """
        if config:
            if isinstance(config, str):
                # Handle unified configuration file path
                self._process_unified_config(config, composer)
            elif isinstance(config, list):
                # Handle traditional list of server configurations
                try:
                    AllServersValidator(config).validate_all()
                    self._config = config
                    logger.info("Merged %d configs supplied at launch", len(config))
                except ValidationError as e:
                    logger.error("Validation error: %s", e)
                    sys.exit(1)
            else:
                raise TypeError(
                    "Config must be a list of server configurations or a file path string"
                )

    def _process_unified_config(self, config_path: str, composer: Any) -> None:
        """Process unified configuration file with auto-detection."""
        try:
            # Create config loader and detect type
            config_loader = ConfigLoader(composer)
            config_type = config_loader.detect_config_type(config_path)

            # Load configuration using the same loader instance
            unified_config = config_loader.load_from_file(config_path, config_type)

            # Store configuration for later application
            self._unified_config = unified_config
            self._unified_config_type = config_type

            # Extract server configs for backward compatibility
            if unified_config.servers:
                self._config = [
                    server.model_dump() for server in unified_config.servers
                ]
                logger.info("Loaded %d servers from unified config", len(self._config))

            self._unified_config_applied = True
            logger.info(
                "Successfully loaded unified configuration from %s", config_path
            )

        except Exception as e:
            logger.error(
                "Failed to process unified configuration from %s: %s", config_path, e
            )
            sys.exit(1)

    async def apply_unified_config(self, composer: Any) -> None:
        """Apply the loaded unified configuration."""
        try:
            if self._unified_config is None:
                logger.warning("No unified config to apply")
                return
            config_loader = ConfigLoader(composer)
            results = await config_loader.apply_config(self._unified_config)

            # Log results
            for section, result in results.items():
                if result.get("total", 0) > 0:
                    registered = len(result.get("registered", []))
                    failed = len(result.get("failed", []))
                    logger.info(
                        "Applied %s: %s registered, %s failed",
                        section,
                        registered,
                        failed,
                    )

                    # Log failures
                    for failure in result.get("failed", []):
                        logger.error("Failed to apply %s: %s", section, failure)

            logger.info("Successfully applied unified configuration")

        except Exception as e:
            logger.error("Failed to apply unified configuration: %s", e)
            raise
