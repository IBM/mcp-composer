"""postgres_adapter.py"""

from __future__ import annotations
from typing import TYPE_CHECKING, Dict, List, Any, Union, Optional
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import sql
from contextlib import contextmanager
from urllib.parse import urlparse

from mcp_composer.core.utils.exceptions import ToolDuplicateError
from mcp_composer.core.utils import LoggerFactory
from mcp_composer.core.utils.tools import check_duplicate_tool

from .database import DatabaseInterface

logger = LoggerFactory.get_logger()
if TYPE_CHECKING:
    from mcp_composer.core.composer import MCPComposer


class PostgresAdapter(DatabaseInterface):
    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        database: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        table_name: str = "mcp_servers",
        url: Optional[str] = None,
    ):
        """
        Initialize PostgreSQL adapter.
        
        Args:
            host: PostgreSQL host (ignored if url is provided)
            port: PostgreSQL port (ignored if url is provided)
            database: PostgreSQL database name (ignored if url is provided)
            user: PostgreSQL username (ignored if url is provided)
            password: PostgreSQL password (ignored if url is provided)
            table_name: Table name for storing MCP server configurations
            url: PostgreSQL connection URL (e.g., postgresql://user:password@host:port/database)
        """
        self._table_name = table_name
        
        if url:
            # Parse PostgreSQL URL
            self._connection_params = self._parse_postgres_url(url)
        else:
            # Use individual parameters
            if not all([host, database, user, password]):
                raise ValueError("Either 'url' or all of 'host', 'database', 'user', 'password' must be provided")
            
            self._connection_params = {
                "host": host,
                "port": port or 5432,
                "database": database,
                "user": user,
                "password": password,
            }
        
        self._initialize_database()

    def _parse_postgres_url(self, url: str) -> Dict[str, Any]:
        """
        Parse PostgreSQL connection URL and return connection parameters.
        
        Args:
            url: PostgreSQL connection URL (e.g., postgresql://user:pass@host:port/database)
            
        Returns:
            Dictionary with connection parameters
        """
        try:
            parsed = urlparse(url)
            
            if parsed.scheme not in ['postgresql', 'postgres']:
                raise ValueError(f"Invalid URL scheme: {parsed.scheme}. Expected 'postgresql' or 'postgres'")
            
            if not parsed.hostname:
                raise ValueError("URL must include hostname")
            
            if not parsed.path or parsed.path == '/':
                raise ValueError("URL must include database name")
            
            # Remove leading slash from path to get database name
            database = parsed.path.lstrip('/')
            
            connection_params = {
                "host": parsed.hostname,
                "port": parsed.port or 5432,
                "database": database,
                "user": parsed.username,
                "password": parsed.password,
            }
            
            # Validate required fields
            if not connection_params["user"]:
                raise ValueError("URL must include username")
            if not connection_params["password"]:
                raise ValueError("URL must include password")
            
            logger.info("Parsed PostgreSQL URL successfully")
            return connection_params
            
        except Exception as e:
            logger.error("Failed to parse PostgreSQL URL: %s", e)
            raise ValueError(f"Invalid PostgreSQL URL: {e}") from e

    def _initialize_database(self) -> None:
        """Initialize the database and create the table if it doesn't exist."""
        # Validate connection parameters
        required_keys = ["host", "database", "user", "password"]
        if not all(k in self._connection_params for k in required_keys):
            raise ValueError("Connection parameters must include host, database, user, and password")

        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    # Create table if it doesn't exist
                    create_table_query = f"""
                    CREATE TABLE IF NOT EXISTS {self._table_name} (
                        id VARCHAR(255) PRIMARY KEY,
                        config JSONB NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                    """
                    cursor.execute(create_table_query)

                    # Create index on id for faster lookups
                    cursor.execute(f"""
                        CREATE INDEX IF NOT EXISTS idx_{self._table_name}_id
                        ON {self._table_name} (id);
                    """)

                    conn.commit()
                    logger.info("PostgreSQL database and table initialized successfully")
        except Exception as e:
            logger.error("Failed to initialize PostgreSQL database: %s", e)
            raise

    @contextmanager
    def _get_connection(self):
        """Context manager for database connections."""
        conn = None
        try:
            conn = psycopg2.connect(**self._connection_params)
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error("Database connection error: %s", e)
            raise
        finally:
            if conn:
                conn.close()

    def _parse_config(self, config_data: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Parse config data from database, handling both string and dict formats."""
        if isinstance(config_data, str):
            return json.loads(config_data)
        elif isinstance(config_data, dict):
            return config_data
        else:
            logger.warning("Unexpected config data type: %s", type(config_data))
            return {}

    def _save_disabled_tools_to_db(
        self, server_id: str, tools: list[str], enable: bool
    ) -> None:
        tools = list(set(tools))  # Remove duplicates
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    # Check if server exists
                    cursor.execute(
                        f"SELECT config FROM {self._table_name} WHERE id = %s",
                        (server_id,)
                    )
                    result = cursor.fetchone()

                    if result:
                        config = self._parse_config(result["config"])
                        # Type assertion to help type checker understand this is a dict
                        assert isinstance(config, dict)
                    else:
                        # Create new config if server doesn't exist
                        config = {"id": server_id, "type": "composer"}

                    if enable:
                        # Simply overwrite disabled tools
                        config["disabled_tools"] = tools  # type: ignore
                    else:
                        if len(tools) == 1 and tools[0].lower() == "all":
                            existing_tools: List[str] = []
                        else:
                            existing_tools_raw = config.get("disabled_tools", [])
                            if not isinstance(existing_tools_raw, list):
                                existing_tools = []
                            else:
                                existing_tools = existing_tools_raw

                        if existing_tools:
                            logger.info(
                                "Remove tool list is already %s present in postgres for server_id %s. Updating list. Response: %s",
                                existing_tools,
                                server_id,
                                config,
                            )

                            duplicate_tool = check_duplicate_tool(existing_tools, tools)
                            if duplicate_tool:
                                raise ToolDuplicateError(
                                    f"Tool {duplicate_tool} is already removed"
                                )

                            config["disabled_tools"].extend(tools)  # type: ignore
                        else:
                            config["disabled_tools"] = tools  # type: ignore

                    # Update or insert the document
                    cursor.execute(
                        f"""
                        INSERT INTO {self._table_name} (id, config, updated_at)
                        VALUES (%s, %s, CURRENT_TIMESTAMP)
                        ON CONFLICT (id) DO UPDATE SET
                            config = EXCLUDED.config,
                            updated_at = CURRENT_TIMESTAMP
                        """,
                        (server_id, json.dumps(config))
                    )
                    conn.commit()

                    logger.info(
                        "Saved disabled tool list '%s' for server '%s'",
                        config["disabled_tools"],
                        server_id,
                    )

        except Exception as e:
            logger.error("Failed to save disabled tool list: %s", str(e))
            raise

    def load_all_servers(self) -> List[Dict[str, Any]]:
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(f"SELECT config FROM {self._table_name}")
                    results = cursor.fetchall()
                    servers = []
                    for row in results:
                        config = self._parse_config(row["config"])
                        servers.append(config)
                    return servers
        except Exception as exc:
            logger.error("PostgreSQL read failed: %s", exc)
            return []

    def add_server(self, config: Dict[str, Any]) -> None:
        doc_id = config["id"]
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        f"""
                        INSERT INTO {self._table_name} (id, config, updated_at)
                        VALUES (%s, %s, CURRENT_TIMESTAMP)
                        ON CONFLICT (id) DO UPDATE SET
                            config = EXCLUDED.config,
                            updated_at = CURRENT_TIMESTAMP
                        """,
                        (doc_id, json.dumps(config))
                    )
                    conn.commit()
                    logger.info("Saved server '%s' to PostgreSQL", doc_id)
        except Exception as e:
            logger.error("Failed to save server '%s': %s", doc_id, e)
            raise

    def remove_server(self, server_id: str) -> None:
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        f"DELETE FROM {self._table_name} WHERE id = %s",
                        (server_id,)
                    )
                    conn.commit()
                    logger.info("Deleted server '%s' from PostgreSQL", server_id)
        except Exception as exc:
            logger.error("PostgreSQL operation failed: %s", exc)
            raise

    def disable_tools(self, tools: list[str], server_id: str) -> None:
        """Disable tools for a member server."""
        self._save_disabled_tools_to_db(server_id, tools, enable=False)

    def enable_tools(self, tools: list[str], server_id: str) -> None:
        """Enable tools for a member server."""
        self._save_disabled_tools_to_db(server_id, tools, enable=True)

    def update_tool_description(
        self, tool: str, description: str, server_id: str
    ) -> None:
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    # Get existing config
                    cursor.execute(
                        f"SELECT config FROM {self._table_name} WHERE id = %s",
                        (server_id,)
                    )
                    result = cursor.fetchone()

                    if result:
                        config = self._parse_config(result["config"])
                        # Type assertion to help type checker understand this is a dict
                        assert isinstance(config, dict)
                    else:
                        # Create new config if server doesn't exist
                        config = {"id": server_id, "type": "composer"}

                    # Update or initialize tools_description
                    tools_description = config.get("tools_description", {})
                    if not isinstance(tools_description, dict):
                        tools_description = {}
                    tools_description[tool] = description
                    config["tools_description"] = tools_description  # type: ignore

                    # Update the document
                    cursor.execute(
                        f"""
                        INSERT INTO {self._table_name} (id, config, updated_at)
                        VALUES (%s, %s, CURRENT_TIMESTAMP)
                        ON CONFLICT (id) DO UPDATE SET
                            config = EXCLUDED.config,
                            updated_at = CURRENT_TIMESTAMP
                        """,
                        (server_id, json.dumps(config))
                    )
                    conn.commit()

                    logger.info(
                        "Updated tool description '%s' for server '%s'",
                        description,
                        server_id,
                    )

        except Exception as e:
            logger.error("Failed to save tool description: %s", str(e))
            raise

    def disable_prompts(self, prompts: list[str], server_id: str) -> None:
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    # Get existing config
                    cursor.execute(
                        f"SELECT config FROM {self._table_name} WHERE id = %s",
                        (server_id,)
                    )
                    result = cursor.fetchone()

                    if result:
                        config = self._parse_config(result["config"])
                        # Type assertion to help type checker understand this is a dict
                        assert isinstance(config, dict)
                    else:
                        # Create new config if server doesn't exist
                        config = {"id": server_id, "type": "composer"}

                    prompts = list(set(prompts))
                    existing_prompts = config.get("disabled_prompts", [])
                    if not isinstance(existing_prompts, list):
                        existing_prompts = []
                    prompts_description = config.get("prompts_description", {})
                    if not isinstance(prompts_description, dict):
                        prompts_description = {}

                    # Check for duplicates
                    if existing_prompts:
                        logger.info(
                            """Disabled prompt list is already
                                %s present in postgres for server_id %s.
                                So, update the disabled prompt list.
                                Response: %s""",
                            existing_prompts,
                            server_id,
                            config,
                        )

                        duplicate_prompt = check_duplicate_tool(existing_prompts, prompts)
                        if duplicate_prompt:
                            raise ToolDuplicateError(
                                f"Prompt {duplicate_prompt} is already disabled"
                            )
                        config["disabled_prompts"].extend(prompts)  # type: ignore
                    else:
                        config["disabled_prompts"] = prompts  # type: ignore  # type: ignore

                    # Remove prompt descriptions if they exist
                    if config["disabled_prompts"] and prompts_description:
                        for prompt in config["disabled_prompts"]:
                            prompts_description.pop(prompt, None)

                    # Update the document
                    cursor.execute(
                        f"""
                        INSERT INTO {self._table_name} (id, config, updated_at)
                        VALUES (%s, %s, CURRENT_TIMESTAMP)
                        ON CONFLICT (id) DO UPDATE SET
                            config = EXCLUDED.config,
                            updated_at = CURRENT_TIMESTAMP
                        """,
                        (server_id, json.dumps(config))
                    )
                    conn.commit()

                    logger.info(
                        """Saved disabled prompt list '%s'
                            for server '%s'""",
                        config["disabled_prompts"],
                        server_id,
                    )

        except Exception as e:
            logger.error("Failed to save disabled prompt list: %s", str(e))
            raise

    def enable_prompts(self, prompts: list[str], server_id: str) -> None:
        """Enable prompts which already disabled"""
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    # Get existing config
                    cursor.execute(
                        f"SELECT config FROM {self._table_name} WHERE id = %s",
                        (server_id,)
                    )
                    result = cursor.fetchone()

                    if result:
                        config = self._parse_config(result["config"])
                        # Type assertion to help type checker understand this is a dict
                        assert isinstance(config, dict)
                    else:
                        # Create new config if server doesn't exist
                        config = {"id": server_id, "type": "composer"}

                    config["disabled_prompts"] = prompts  # type: ignore

                    # Update the document
                    cursor.execute(
                        f"""
                        INSERT INTO {self._table_name} (id, config, updated_at)
                        VALUES (%s, %s, CURRENT_TIMESTAMP)
                        ON CONFLICT (id) DO UPDATE SET
                            config = EXCLUDED.config,
                            updated_at = CURRENT_TIMESTAMP
                        """,
                        (server_id, json.dumps(config))
                    )
                    conn.commit()

                    logger.info(
                        """Saved disabled prompt list '%s'
                            for server '%s'""",
                        config["disabled_prompts"],
                        server_id,
                    )
        except Exception as e:
            logger.error("Failed to save disabled prompt list: %s", str(e))
            raise

    def disable_resources(self, resources: list[str], server_id: str) -> None:
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    # Get existing config
                    cursor.execute(
                        f"SELECT config FROM {self._table_name} WHERE id = %s",
                        (server_id,)
                    )
                    result = cursor.fetchone()

                    if result:
                        config = self._parse_config(result["config"])
                        # Type assertion to help type checker understand this is a dict
                        assert isinstance(config, dict)
                    else:
                        # Create new config if server doesn't exist
                        config = {"id": server_id, "type": "composer"}

                    resources = list(set(resources))
                    existing_resources = config.get("disabled_resources", [])
                    if not isinstance(existing_resources, list):
                        existing_resources = []
                    resources_description = config.get("resources_description", {})
                    if not isinstance(resources_description, dict):
                        resources_description = {}

                    # Check for duplicates
                    if existing_resources:
                        logger.info(
                            """Disabled resource list is already
                                %s present in postgres for server_id %s.
                                So, update the disabled resource list.
                                Response: %s""",
                            existing_resources,
                            server_id,
                            config,
                        )

                        duplicate_resource = check_duplicate_tool(existing_resources, resources)
                        if duplicate_resource:
                            raise ToolDuplicateError(
                                f"Resource {duplicate_resource} is already disabled"
                            )
                        config["disabled_resources"].extend(resources)  # type: ignore
                    else:
                        config["disabled_resources"] = resources  # type: ignore  # type: ignore

                    # Remove resource descriptions if they exist
                    if config["disabled_resources"] and resources_description:
                        for resource in config["disabled_resources"]:
                            resources_description.pop(resource, None)

                    # Update the document
                    cursor.execute(
                        f"""
                        INSERT INTO {self._table_name} (id, config, updated_at)
                        VALUES (%s, %s, CURRENT_TIMESTAMP)
                        ON CONFLICT (id) DO UPDATE SET
                            config = EXCLUDED.config,
                            updated_at = CURRENT_TIMESTAMP
                        """,
                        (server_id, json.dumps(config))
                    )
                    conn.commit()

                    logger.info(
                        """Saved disabled resource list '%s'
                            for server '%s'""",
                        config["disabled_resources"],
                        server_id,
                    )

        except Exception as e:
            logger.error("Failed to save disabled resource list: %s", str(e))
            raise

    def enable_resources(self, resources: list[str], server_id: str) -> None:
        """Enable resources which already disabled"""
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    # Get existing config
                    cursor.execute(
                        f"SELECT config FROM {self._table_name} WHERE id = %s",
                        (server_id,)
                    )
                    result = cursor.fetchone()

                    if result:
                        config = self._parse_config(result["config"])
                        # Type assertion to help type checker understand this is a dict
                        assert isinstance(config, dict)
                    else:
                        # Create new config if server doesn't exist
                        config = {"id": server_id, "type": "composer"}

                    config["disabled_resources"] = resources  # type: ignore

                    # Update the document
                    cursor.execute(
                        f"""
                        INSERT INTO {self._table_name} (id, config, updated_at)
                        VALUES (%s, %s, CURRENT_TIMESTAMP)
                        ON CONFLICT (id) DO UPDATE SET
                            config = EXCLUDED.config,
                            updated_at = CURRENT_TIMESTAMP
                        """,
                        (server_id, json.dumps(config))
                    )
                    conn.commit()

                    logger.info(
                        """Saved disabled resource list '%s'
                            for server '%s'""",
                        config["disabled_resources"],
                        server_id,
                    )
        except Exception as e:
            logger.error("Failed to save disabled resource list: %s", str(e))
            raise

    def get_document(self, server_id: str) -> Dict[str, Any]:
        # get the server config details of a single server
        server_doc = {}
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(
                        f"SELECT config FROM {self._table_name} WHERE id = %s",
                        (server_id,)
                    )
                    result = cursor.fetchone()

                    if result:
                        server_doc = self._parse_config(result["config"])
                        logger.info(
                            "Retrieve server '%s' config details from PostgreSQL. Response: %s",
                            server_id,
                            server_doc,
                        )
                    else:
                        logger.warning("No server details found in DB for server_id: %s", server_id)

        except Exception as e:
            logger.error("No server details found in DB: %s", e)
        return server_doc

    def mark_deactivated(self, server_id: str) -> None:
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    # Get existing config
                    cursor.execute(
                        f"SELECT config FROM {self._table_name} WHERE id = %s",
                        (server_id,)
                    )
                    result = cursor.fetchone()

                    if result:
                        config = self._parse_config(result["config"])
                        config["status"] = "deactivated"

                        # Update the document
                        cursor.execute(
                            f"""
                            UPDATE {self._table_name}
                            SET config = %s, updated_at = CURRENT_TIMESTAMP
                            WHERE id = %s
                            """,
                            (json.dumps(config), server_id)
                        )
                        conn.commit()
                        logger.info("Marked server '%s' as deactivated", server_id)
                    else:
                        logger.error("Server '%s' not found. Cannot deactivate.", server_id)

        except Exception as e:
            logger.error("Error deactivating server '%s': %s", server_id, e)
            raise

    def get_server_status(self, server_id: str) -> str:
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute(
                        f"SELECT config FROM {self._table_name} WHERE id = %s",
                        (server_id,)
                    )
                    result = cursor.fetchone()

                    if result:
                        config = self._parse_config(result["config"])
                        status = config.get("status", "active")  # default to 'active' if not set
                        logger.info("Server '%s' has status: %s", server_id, status)
                        return status
                    else:
                        logger.warning("Server '%s' not found when fetching status.", server_id)
                        return "unknown"

        except Exception as e:
            logger.error("Error retrieving server status for '%s': %s", server_id, e)
            return "unknown"

    def update_server_config(self, config: Dict[str, Any]) -> None:
        """
        Update the configuration of an existing server.
        If the document does not exist, raise an error.
        """
        server_id = config.get("id")
        if not server_id:
            raise ValueError("Config must include 'id' to update.")

        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    # Check if server exists
                    cursor.execute(
                        f"SELECT id FROM {self._table_name} WHERE id = %s",
                        (server_id,)
                    )
                    if not cursor.fetchone():
                        logger.error("Server '%s' not found in PostgreSQL.", server_id)
                        raise ValueError(f"Server '{server_id}' not found in PostgreSQL.")

                    # Update the server config
                    cursor.execute(
                        f"""
                        UPDATE {self._table_name}
                        SET config = %s, updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                        """,
                        (json.dumps(config), server_id)
                    )
                    conn.commit()

                    logger.info("Updated configuration for server '%s'", server_id)

        except Exception as e:
            logger.error("Failed to update server '%s': %s", server_id, e)
            raise
