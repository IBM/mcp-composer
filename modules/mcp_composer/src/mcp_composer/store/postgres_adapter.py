"""postgres_adapter.py"""

from __future__ import annotations
import json
import asyncio
from typing import TYPE_CHECKING, Dict, List, Any, Union, Optional
from urllib.parse import urlparse
import asyncpg

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
        min_size: int = 1,
        max_size: int = 10,
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
            min_size: Minimum connections in the pool
            max_size: Maximum connections in the pool
        """
        self._table_name = table_name
        self._resources_table_name = f"{table_name}_resources"
        self._pool: Optional[asyncpg.Pool] = None
        self._min_size = min_size
        self._max_size = max_size

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

        # Initialize database synchronously
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

    async def _get_connection(self) -> asyncpg.Connection:
        """Get a database connection."""
        try:
            conn = await asyncpg.connect(**self._connection_params)
            return conn
        except Exception as e:
            logger.error("Failed to create PostgreSQL connection: %s", e)
            raise

    def _initialize_database(self) -> None:
        """Initialize the database and create the table if it doesn't exist."""
        # Validate connection parameters
        required_keys = ["host", "database", "user", "password"]
        if not all(k in self._connection_params for k in required_keys):
            raise ValueError("Connection parameters must include host, database, user, and password")

        try:
            # Use asyncio.run to execute async code synchronously, but handle existing event loop
            self._run_async(self._async_initialize_database())
        except Exception as e:
            logger.error("Failed to initialize PostgreSQL database: %s", e)
            raise

    async def _async_initialize_database(self) -> None:
        """Async part of database initialization."""
        conn = await self._get_connection()
        try:
            # Create table if it doesn't exist
            create_table_query = f"""
            CREATE TABLE IF NOT EXISTS {self._table_name} (
                id VARCHAR(255) PRIMARY KEY,
                config JSONB NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
            await conn.execute(create_table_query)

            # Create index on id for faster lookups
            await conn.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{self._table_name}_id
                ON {self._table_name} (id);
            """)

            await conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self._resources_table_name} (
                    id VARCHAR(255) PRIMARY KEY,
                    data JSONB NOT NULL,
                    kind VARCHAR(32) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            await conn.execute(
                f"""
                CREATE INDEX IF NOT EXISTS idx_{self._resources_table_name}_id
                ON {self._resources_table_name} (id);
                """
            )

            logger.info("PostgreSQL database and table initialized successfully")
        finally:
            await conn.close()

    def _run_async(self, coro):
        """Run async coroutine, handling existing event loop properly."""
        try:
            # Try to get the current event loop
            loop = asyncio.get_running_loop()
            # If we're in an async context, we need to create a task
            # But since we're in a sync method, we'll use asyncio.run_coroutine_threadsafe
            import concurrent.futures
            import threading

            # Create a new event loop in a separate thread
            def run_in_thread():
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    return new_loop.run_until_complete(coro)
                finally:
                    new_loop.close()

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(run_in_thread)
                return future.result()
        except RuntimeError:
            # No event loop running, safe to use asyncio.run
            return asyncio.run(coro)

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
        """Save disabled tools to database synchronously."""
        self._run_async(self._async_save_disabled_tools_to_db(server_id, tools, enable))

    async def _async_save_disabled_tools_to_db(
        self, server_id: str, tools: list[str], enable: bool
    ) -> None:
        """Async implementation of saving disabled tools."""
        tools = list(set(tools))  # Remove duplicates
        try:
            conn = await self._get_connection()
            try:
                # Check if server exists
                result = await conn.fetchrow(
                    f"SELECT config FROM {self._table_name} WHERE id = $1",
                    server_id
                )

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
                await conn.execute(
                    f"""
                    INSERT INTO {self._table_name} (id, config, updated_at)
                    VALUES ($1, $2, CURRENT_TIMESTAMP)
                    ON CONFLICT (id) DO UPDATE SET
                        config = EXCLUDED.config,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    server_id, json.dumps(config)
                )

                logger.info(
                    "Saved disabled tool list '%s' for server '%s'",
                    config["disabled_tools"],
                    server_id,
                )
            finally:
                await conn.close()

        except Exception as e:
            logger.error("Failed to save disabled tool list: %s", str(e))
            raise

    def load_all_servers(self) -> List[Dict[str, Any]]:
        """Load all servers synchronously."""
        return self._run_async(self._async_load_all_servers())

    async def _async_load_all_servers(self) -> List[Dict[str, Any]]:
        """Async implementation of loading all servers."""
        try:
            conn = await self._get_connection()
            try:
                results = await conn.fetch(f"SELECT config FROM {self._table_name}")
                servers = []
                for row in results:
                    config = self._parse_config(row["config"])
                    servers.append(config)
                return servers
            finally:
                await conn.close()
        except Exception as exc:
            logger.error("PostgreSQL read failed: %s", exc)
            return []

    def add_server(self, config: Dict[str, Any]) -> None:
        """Add server synchronously."""
        self._run_async(self._async_add_server(config))

    async def _async_add_server(self, config: Dict[str, Any]) -> None:
        """Async implementation of adding server."""
        doc_id = config["id"]
        try:
            conn = await self._get_connection()
            try:
                await conn.execute(
                    f"""
                    INSERT INTO {self._table_name} (id, config, updated_at)
                    VALUES ($1, $2, CURRENT_TIMESTAMP)
                    ON CONFLICT (id) DO UPDATE SET
                        config = EXCLUDED.config,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    doc_id, json.dumps(config)
                )
                logger.info("Saved server '%s' to PostgreSQL", doc_id)
            finally:
                await conn.close()
        except Exception as e:
            logger.error("Failed to save server '%s': %s", doc_id, e)
            raise

    def remove_server(self, server_id: str) -> None:
        """Remove server synchronously."""
        self._run_async(self._async_remove_server(server_id))

    async def _async_remove_server(self, server_id: str) -> None:
        """Async implementation of removing server."""
        try:
            conn = await self._get_connection()
            try:
                await conn.execute(
                    f"DELETE FROM {self._table_name} WHERE id = $1",
                    server_id
                )
                logger.info("Deleted server '%s' from PostgreSQL", server_id)
            finally:
                await conn.close()
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
        """Update tool description synchronously."""
        self._run_async(self._async_update_tool_description(tool, description, server_id))

    async def _async_update_tool_description(
        self, tool: str, description: str, server_id: str
    ) -> None:
        """Async implementation of updating tool description."""
        try:
            conn = await self._get_connection()
            try:
                # Get existing config
                result = await conn.fetchrow(
                    f"SELECT config FROM {self._table_name} WHERE id = $1",
                    server_id
                )

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
                await conn.execute(
                    f"""
                    INSERT INTO {self._table_name} (id, config, updated_at)
                    VALUES ($1, $2, CURRENT_TIMESTAMP)
                    ON CONFLICT (id) DO UPDATE SET
                        config = EXCLUDED.config,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    server_id, json.dumps(config)
                )

                logger.info(
                    "Updated tool description '%s' for server '%s'",
                    description,
                    server_id,
                )
            finally:
                await conn.close()

        except Exception as e:
            logger.error("Failed to save tool description: %s", str(e))
            raise

    def disable_prompts(self, prompts: list[str], server_id: str) -> None:
        """Disable prompts synchronously."""
        self._run_async(self._async_disable_prompts(prompts, server_id))

    async def _async_disable_prompts(self, prompts: list[str], server_id: str) -> None:
        """Async implementation of disabling prompts."""
        try:
            conn = await self._get_connection()
            try:
                # Get existing config
                result = await conn.fetchrow(
                    f"SELECT config FROM {self._table_name} WHERE id = $1",
                    server_id
                )

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
                await conn.execute(
                    f"""
                    INSERT INTO {self._table_name} (id, config, updated_at)
                    VALUES ($1, $2, CURRENT_TIMESTAMP)
                    ON CONFLICT (id) DO UPDATE SET
                        config = EXCLUDED.config,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    server_id, json.dumps(config)
                )

                logger.info(
                    """Saved disabled prompt list '%s'
                        for server '%s'""",
                    config["disabled_prompts"],
                    server_id,
                )
            finally:
                await conn.close()

        except Exception as e:
            logger.error("Failed to save disabled prompt list: %s", str(e))
            raise

    def enable_prompts(self, prompts: list[str], server_id: str) -> None:
        """Enable prompts synchronously."""
        self._run_async(self._async_enable_prompts(prompts, server_id))

    async def _async_enable_prompts(self, prompts: list[str], server_id: str) -> None:
        """Async implementation of enabling prompts."""
        try:
            conn = await self._get_connection()
            try:
                # Get existing config
                result = await conn.fetchrow(
                    f"SELECT config FROM {self._table_name} WHERE id = $1",
                    server_id
                )

                if result:
                    config = self._parse_config(result["config"])
                    # Type assertion to help type checker understand this is a dict
                    assert isinstance(config, dict)
                else:
                    # Create new config if server doesn't exist
                    config = {"id": server_id, "type": "composer"}

                config["disabled_prompts"] = prompts  # type: ignore

                # Update the document
                await conn.execute(
                    f"""
                    INSERT INTO {self._table_name} (id, config, updated_at)
                    VALUES ($1, $2, CURRENT_TIMESTAMP)
                    ON CONFLICT (id) DO UPDATE SET
                        config = EXCLUDED.config,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    server_id, json.dumps(config)
                )

                logger.info(
                    """Saved disabled prompt list '%s'
                        for server '%s'""",
                    config["disabled_prompts"],
                    server_id,
                )
            finally:
                await conn.close()
        except Exception as e:
            logger.error("Failed to save disabled prompt list: %s", str(e))
            raise

    def disable_resources(self, resources: list[str], server_id: str) -> None:
        """Disable resources synchronously."""
        self._run_async(self._async_disable_resources(resources, server_id))

    async def _async_disable_resources(self, resources: list[str], server_id: str) -> None:
        """Async implementation of disabling resources."""
        try:
            conn = await self._get_connection()
            try:
                # Get existing config
                result = await conn.fetchrow(
                    f"SELECT config FROM {self._table_name} WHERE id = $1",
                    server_id
                )

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
                await conn.execute(
                    f"""
                    INSERT INTO {self._table_name} (id, config, updated_at)
                    VALUES ($1, $2, CURRENT_TIMESTAMP)
                    ON CONFLICT (id) DO UPDATE SET
                        config = EXCLUDED.config,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    server_id, json.dumps(config)
                )

                logger.info(
                    """Saved disabled resource list '%s'
                        for server '%s'""",
                    config["disabled_resources"],
                    server_id,
                )
            finally:
                await conn.close()

        except Exception as e:
            logger.error("Failed to save disabled resource list: %s", str(e))
            raise

    def enable_resources(self, resources: list[str], server_id: str) -> None:
        """Enable resources synchronously."""
        self._run_async(self._async_enable_resources(resources, server_id))

    async def _async_enable_resources(self, resources: list[str], server_id: str) -> None:
        """Async implementation of enabling resources."""
        try:
            conn = await self._get_connection()
            try:
                # Get existing config
                result = await conn.fetchrow(
                    f"SELECT config FROM {self._table_name} WHERE id = $1",
                    server_id
                )

                if result:
                    config = self._parse_config(result["config"])
                    # Type assertion to help type checker understand this is a dict
                    assert isinstance(config, dict)
                else:
                    # Create new config if server doesn't exist
                    config = {"id": server_id, "type": "composer"}

                config["disabled_resources"] = resources  # type: ignore

                # Update the document
                await conn.execute(
                    f"""
                    INSERT INTO {self._table_name} (id, config, updated_at)
                    VALUES ($1, $2, CURRENT_TIMESTAMP)
                    ON CONFLICT (id) DO UPDATE SET
                        config = EXCLUDED.config,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    server_id, json.dumps(config)
                )

                logger.info(
                    """Saved disabled resource list '%s'
                        for server '%s'""",
                    config["disabled_resources"],
                    server_id,
                )
            finally:
                await conn.close()
        except Exception as e:
            logger.error("Failed to save disabled resource list: %s", str(e))
            raise

    def get_document(self, server_id: str) -> Dict[str, Any]:
        """Get document synchronously."""
        return self._run_async(self._async_get_document(server_id))

    async def _async_get_document(self, server_id: str) -> Dict[str, Any]:
        """Async implementation of getting document."""
        # get the server config details of a single server
        server_doc = {}
        try:
            conn = await self._get_connection()
            try:
                result = await conn.fetchrow(
                    f"SELECT config FROM {self._table_name} WHERE id = $1",
                    server_id
                )

                if result:
                    server_doc = self._parse_config(result["config"])
                    logger.info(
                        "Retrieve server '%s' config details from PostgreSQL. Response: %s",
                        server_id,
                        server_doc,
                    )
                else:
                    logger.warning("No server details found in DB for server_id: %s", server_id)
            finally:
                await conn.close()

        except Exception as e:
            logger.error("No server details found in DB: %s", e)
        return server_doc

    def mark_deactivated(self, server_id: str) -> None:
        """Mark server as deactivated synchronously."""
        self._run_async(self._async_mark_deactivated(server_id))

    async def _async_mark_deactivated(self, server_id: str) -> None:
        """Async implementation of marking server as deactivated."""
        try:
            conn = await self._get_connection()
            try:
                # Get existing config
                result = await conn.fetchrow(
                    f"SELECT config FROM {self._table_name} WHERE id = $1",
                    server_id
                )

                if result:
                    config = self._parse_config(result["config"])
                    config["status"] = "deactivated"

                    # Update the document
                    await conn.execute(
                        f"""
                        UPDATE {self._table_name}
                        SET config = $1, updated_at = CURRENT_TIMESTAMP
                        WHERE id = $2
                        """,
                        json.dumps(config), server_id
                    )
                    logger.info("Marked server '%s' as deactivated", server_id)
                else:
                    logger.error("Server '%s' not found. Cannot deactivate.", server_id)
            finally:
                await conn.close()

        except Exception as e:
            logger.error("Error deactivating server '%s': %s", server_id, e)
            raise

    def get_server_status(self, server_id: str) -> str:
        """Get server status synchronously."""
        return self._run_async(self._async_get_server_status(server_id))

    async def _async_get_server_status(self, server_id: str) -> str:
        """Async implementation of getting server status."""
        try:
            conn = await self._get_connection()
            try:
                result = await conn.fetchrow(
                    f"SELECT config FROM {self._table_name} WHERE id = $1",
                    server_id
                )

                if result:
                    config = self._parse_config(result["config"])
                    status = config.get("status", "active")  # default to 'active' if not set
                    logger.info("Server '%s' has status: %s", server_id, status)
                    return status
                else:
                    logger.warning("Server '%s' not found when fetching status.", server_id)
                    return "unknown"
            finally:
                await conn.close()

        except Exception as e:
            logger.error("Error retrieving server status for '%s': %s", server_id, e)
            return "unknown"

    def update_server_config(self, config: Dict[str, Any]) -> None:
        """Update server config synchronously."""
        self._run_async(self._async_update_server_config(config))

    async def _async_update_server_config(self, config: Dict[str, Any]) -> None:
        """Async implementation of updating server config."""
        """
        Update the configuration of an existing server.
        If the document does not exist, raise an error.
        """
        server_id = config.get("id")
        if not server_id:
            raise ValueError("Config must include 'id' to update.")

        try:
            conn = await self._get_connection()
            try:
                # Check if server exists
                result = await conn.fetchrow(
                    f"SELECT id FROM {self._table_name} WHERE id = $1",
                    server_id
                )
                if not result:
                    logger.error("Server '%s' not found in PostgreSQL.", server_id)
                    raise ValueError(f"Server '{server_id}' not found in PostgreSQL.")

                # Update the server config
                await conn.execute(
                    f"""
                    UPDATE {self._table_name}
                    SET config = $1, updated_at = CURRENT_TIMESTAMP
                    WHERE id = $2
                    """,
                    json.dumps(config), server_id
                )

                logger.info("Updated configuration for server '%s'", server_id)
            finally:
                await conn.close()

        except Exception as e:
            logger.error("Failed to update server '%s': %s", server_id, e)
            raise

    def load_all_resources(self) -> List[Dict[str, Any]]:
        return self._run_async(self._async_load_all_resources())

    async def _async_load_all_resources(self) -> List[Dict[str, Any]]:
        try:
            conn = await self._get_connection()
            try:
                result = await conn.fetch(
                    f"SELECT data FROM {self._resources_table_name}"
                )
                resources: List[Dict[str, Any]] = []
                for row in result:
                    resources.append(self._parse_config(row["data"]))
                return resources
            finally:
                await conn.close()
        except Exception as exc:
            logger.error("PostgreSQL resource load failed: %s", exc)
            return []

    def upsert_resource(self, resource: Dict[str, Any]) -> None:
        self._run_async(self._async_upsert_resource(resource))

    async def _async_upsert_resource(self, resource: Dict[str, Any]) -> None:
        storage_id = resource["storage_id"]
        try:
            conn = await self._get_connection()
            try:
                await conn.execute(
                    f"""
                    INSERT INTO {self._resources_table_name} (id, data, kind, updated_at)
                    VALUES ($1, $2, $3, CURRENT_TIMESTAMP)
                    ON CONFLICT (id) DO UPDATE SET
                        data = EXCLUDED.data,
                        kind = EXCLUDED.kind,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    storage_id,
                    json.dumps(resource),
                    resource.get("resource_type", "resource"),
                )
                logger.info("Saved resource '%s' to PostgreSQL", storage_id)
            finally:
                await conn.close()
        except Exception as exc:
            logger.error("Failed to save resource '%s': %s", storage_id, exc)
            raise

    def delete_resource(self, resource_id: str) -> None:
        self._run_async(self._async_delete_resource(resource_id))

    async def _async_delete_resource(self, resource_id: str) -> None:
        try:
            conn = await self._get_connection()
            try:
                await conn.execute(
                    f"DELETE FROM {self._resources_table_name} WHERE id = $1",
                    resource_id,
                )
                logger.info("Deleted resource '%s' from PostgreSQL", resource_id)
            finally:
                await conn.close()
        except Exception as exc:
            logger.error("Failed to delete resource '%s': %s", resource_id, exc)
            raise

    def close(self) -> None:
        """Close method for compatibility (no-op with direct connections)."""
        # With direct connections, each operation closes its own connection
        # This method is kept for compatibility with the interface
        logger.info("PostgreSQL adapter close called (direct connections used)")

    def __del__(self):
        """Destructor for compatibility (no-op with direct connections)."""
        # With direct connections, there's no persistent pool to close
        # This method is kept for compatibility
        pass
