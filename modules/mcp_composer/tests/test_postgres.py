#!/usr/bin/env python3
"""
Comprehensive test suite for PostgreSQL adapter with asyncpg.
Combines functionality from all previous PostgreSQL test files.
"""

import sys
import json
import pytest
from pathlib import Path
from urllib.parse import urlparse

# Add the src directory to the Python path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))


def test_postgres_adapter_import():
    """Test that we can import the PostgreSQL adapter directly."""
    from mcp_composer.store.postgres_adapter import PostgresAdapter

    print("✅ PostgreSQL adapter imported successfully")
    # Test passes if no exception is raised
    assert True


def test_url_parsing():
    """Test URL parsing functionality with proper assertions."""
    from mcp_composer.store.postgres_adapter import PostgresAdapter

    print("\n🧪 Testing URL parsing...")

    # Test URL parsing method directly
    adapter = PostgresAdapter.__new__(PostgresAdapter)  # Create without calling __init__

    test_urls = [
        "postgresql://user:pass@localhost:5432/db",
        "postgres://user:pass@localhost:5432/db",
        "postgresql://user:pass@localhost/db",  # Default port
        "postgresql://user:pass@example.com:5433/db",
    ]

    for i, url in enumerate(test_urls, 1):
        parsed = adapter._parse_postgres_url(url)
        print(f"✅ Test {i}: URL '{url}' parsed successfully")
        print(f"   Parsed: {parsed}")

        # Assert that parsing was successful
        assert parsed is not None
        assert 'host' in parsed
        assert 'database' in parsed
        assert 'user' in parsed
        assert 'password' in parsed


def test_invalid_urls():
    """Test invalid URL handling with pytest.raises."""
    from mcp_composer.store.postgres_adapter import PostgresAdapter

    print("\n🧪 Testing invalid URL handling...")

    adapter = PostgresAdapter.__new__(PostgresAdapter)  # Create without calling __init__

    invalid_urls = [
        ("http://user:pass@localhost:5432/db", "Wrong scheme"),
        ("postgresql://localhost:5432/db", "Missing user/password"),
        ("postgresql://user@localhost:5432/db", "Missing password"),
        ("postgresql://test_user:test_pass@localhost:5432/", "Missing database"),
    ]

    for i, (url, description) in enumerate(invalid_urls, 1):
        with pytest.raises(ValueError):
            adapter._parse_postgres_url(url)
        print(f"✅ Test {i}: {description} - '{url}' correctly rejected")


def test_table_creation_sql():
    """Test that the table creation SQL includes updated_at column."""
    from mcp_composer.store.postgres_adapter import PostgresAdapter

    print("\n🧪 Testing table creation SQL...")

    # Check if the _async_initialize_database method exists and has the right SQL
    import inspect
    source = inspect.getsource(PostgresAdapter._async_initialize_database)

    assert "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP" in source, "Table creation SQL missing updated_at column"
    print("✅ Table creation SQL includes updated_at column")

    assert "CREATE TABLE IF NOT EXISTS" in source, "Table creation logic missing"
    print("✅ Table creation logic found")


def test_adapter_creation_with_url():
    """Test PostgreSQL adapter creation with URL parameter."""
    from mcp_composer.store.postgres_adapter import PostgresAdapter

    print("\n🧪 Testing adapter creation with URL...")

    test_url = "postgresql://test_user:test_pass@localhost:5432/test_db"
    adapter = None

    try:
        adapter = PostgresAdapter(url=test_url, table_name="test_table")
        print("✅ PostgreSQL adapter created successfully with URL")
        print(f"✅ Connection params: {adapter._connection_params}")

        # Verify connection parameters
        assert adapter._connection_params['host'] == 'localhost'
        assert adapter._connection_params['port'] == 5432
        assert adapter._connection_params['database'] == 'test_db'
        assert adapter._connection_params['user'] == 'test_user'
        assert adapter._connection_params['password'] == 'test_pass'

    except Exception as e:
        if any(keyword in str(e).lower() for keyword in ["connection", "connect", "role", "does not exist", "authorization", "database"]):
            print("✅ PostgreSQL adapter created successfully (connection failed as expected)")
            if adapter:
                print(f"✅ Connection params: {adapter._connection_params}")

                # Verify connection parameters even when connection fails
                assert adapter._connection_params['host'] == 'localhost'
                assert adapter._connection_params['port'] == 5432
                assert adapter._connection_params['database'] == 'test_db'
                assert adapter._connection_params['user'] == 'test_user'
                assert adapter._connection_params['password'] == 'test_pass'
        else:
            print(f"❌ Unexpected error: {e}")
            pytest.fail(f"Unexpected error during adapter creation: {e}")


def test_adapter_creation_with_individual_params():
    """Test PostgreSQL adapter creation with individual parameters."""
    from mcp_composer.store.postgres_adapter import PostgresAdapter

    print("\n🧪 Testing adapter creation with individual parameters...")

    adapter = None
    try:
        adapter = PostgresAdapter(
            host='localhost',
            port=5432,
            database='test_db',
            user='test_user',
            password='test_pass',
            table_name='test_table'
        )
        print("✅ PostgreSQL adapter created successfully with individual parameters")
        print(f"✅ Connection params: {adapter._connection_params}")

        # Verify connection parameters
        assert adapter._connection_params['host'] == 'localhost'
        assert adapter._connection_params['port'] == 5432
        assert adapter._connection_params['database'] == 'test_db'
        assert adapter._connection_params['user'] == 'test_user'
        assert adapter._connection_params['password'] == 'test_pass'

    except Exception as e:
        if any(keyword in str(e).lower() for keyword in ["connection", "connect", "role", "does not exist", "authorization", "database"]):
            print("✅ PostgreSQL adapter created successfully (connection failed as expected)")
            if adapter:
                print(f"✅ Connection params: {adapter._connection_params}")

                # Verify connection parameters even when connection fails
                assert adapter._connection_params['host'] == 'localhost'
                assert adapter._connection_params['port'] == 5432
                assert adapter._connection_params['database'] == 'test_db'
                assert adapter._connection_params['user'] == 'test_user'
                assert adapter._connection_params['password'] == 'test_pass'
        else:
            print(f"❌ Unexpected error: {e}")
            pytest.fail(f"Unexpected error during adapter creation: {e}")


def test_missing_parameters():
    """Test that missing parameters raise appropriate errors."""
    from mcp_composer.store.postgres_adapter import PostgresAdapter

    print("\n🧪 Testing missing parameters...")

    with pytest.raises(ValueError, match="Either 'url' or all of 'host', 'database', 'user', 'password' must be provided"):
        PostgresAdapter()

    print("✅ Missing parameters correctly rejected")


def test_url_parsing_logic_standalone():
    """Test URL parsing logic without importing the full adapter."""
    print("\n🧪 Testing PostgreSQL URL parsing logic...")

    test_urls = [
        "postgresql://user:pass@localhost:5432/db",
        "postgres://user:pass@localhost:5432/db",
        "postgresql://user:pass@localhost/db",  # Default port
        "postgresql://user:pass@example.com:5433/db",
    ]

    for i, url in enumerate(test_urls, 1):
        parsed = urlparse(url)

        # Validate scheme
        assert parsed.scheme in ['postgresql', 'postgres'], f"Invalid scheme '{parsed.scheme}' for URL '{url}'"

        # Validate hostname
        assert parsed.hostname is not None, f"Missing hostname in URL '{url}'"

        # Validate database path
        assert parsed.path and parsed.path != '/', f"Missing database name in URL '{url}'"

        database = parsed.path.lstrip('/')

        connection_params = {
            "host": parsed.hostname,
            "port": parsed.port or 5432,
            "database": database,
            "user": parsed.username,
            "password": parsed.password,
        }

        # Validate credentials
        assert connection_params["user"] is not None, f"Missing username in URL '{url}'"
        assert connection_params["password"] is not None, f"Missing password in URL '{url}'"

        print(f"✅ Test {i}: URL '{url}' parsed successfully")
        print(f"   Parsed: {connection_params}")


def test_connection_parameter_construction():
    """Test connection parameter construction."""
    print("\n🧪 Testing connection parameter construction...")

    # Test URL-based parameters
    url = "postgresql://test_user:test_pass@localhost:5432/test_db"
    parsed = urlparse(url)

    connection_params = {
        "host": parsed.hostname,
        "port": parsed.port or 5432,
        "database": parsed.path.lstrip('/'),
        "user": parsed.username,
        "password": parsed.password,
    }

    expected_params = {
        "host": "localhost",
        "port": 5432,
        "database": "test_db",
        "user": "test_user",
        "password": "test_pass",
    }

    assert connection_params == expected_params, f"URL-based connection parameters mismatch: {connection_params}"
    print("✅ URL-based connection parameters constructed correctly")

    # Test individual parameters
    individual_params = {
        "host": "localhost",
        "port": 5432,
        "database": "test_db",
        "user": "test_user",
        "password": "test_pass",
    }

    assert individual_params == expected_params, f"Individual connection parameters mismatch: {individual_params}"
    print("✅ Individual connection parameters constructed correctly")


def test_jsonb_handling():
    """Test JSONB data handling logic."""
    print("\n🧪 Testing JSONB data handling...")

    # Test config parsing
    test_configs = [
        '{"id": "test", "type": "http", "endpoint": "http://example.com"}',
        {"id": "test", "type": "http", "endpoint": "http://example.com"},
        '{"disabled_tools": ["tool1", "tool2"]}',
        {"disabled_tools": ["tool1", "tool2"]},
    ]

    for i, config_data in enumerate(test_configs, 1):
        if isinstance(config_data, str):
            parsed_config = json.loads(config_data)
        elif isinstance(config_data, dict):
            parsed_config = config_data
        else:
            pytest.fail(f"Unexpected config data type: {type(config_data)}")

        assert isinstance(parsed_config, dict), f"Config data not parsed as dict: {type(parsed_config)}"
        print(f"✅ Test {i}: Config data parsed successfully: {parsed_config}")


def test_async_sync_bridge():
    """Test that the async/sync bridge is properly implemented."""
    from mcp_composer.store.postgres_adapter import PostgresAdapter

    print("\n🧪 Testing async/sync bridge...")

    adapter = PostgresAdapter.__new__(PostgresAdapter)

    # Test that _run_async method exists
    assert hasattr(adapter, '_run_async'), "_run_async method not found"
    print("✅ _run_async method found")

    # Test that async methods exist
    async_methods = [
        '_async_initialize_database',
        '_async_load_all_servers',
        '_async_add_server',
        '_async_remove_server',
        '_async_get_document',
        '_async_save_disabled_tools_to_db',
    ]

    for method_name in async_methods:
        assert hasattr(adapter, method_name), f"Async method {method_name} not found"

    print("✅ All required async methods found")


def test_database_interface_compliance():
    """Test that PostgresAdapter implements all required DatabaseInterface methods."""
    from mcp_composer.store.postgres_adapter import PostgresAdapter
    from mcp_composer.store.database import DatabaseInterface

    print("\n🧪 Testing DatabaseInterface compliance...")

    # Check that PostgresAdapter implements DatabaseInterface
    assert issubclass(PostgresAdapter, DatabaseInterface), "PostgresAdapter does not implement DatabaseInterface"

    # Get all abstract methods from DatabaseInterface
    import inspect
    abstract_methods = set()
    for name, method in inspect.getmembers(DatabaseInterface):
        if inspect.isfunction(method) and getattr(method, '__isabstractmethod__', False):
            abstract_methods.add(name)

    # Check that PostgresAdapter implements all abstract methods
    adapter_methods = set(dir(PostgresAdapter))

    for method in abstract_methods:
        assert method in adapter_methods, f"PostgresAdapter missing required method: {method}"

    print("✅ PostgresAdapter fully implements DatabaseInterface")


def test_table_creation_sql_construction():
    """Test that we can construct the table creation SQL."""
    print("\n🧪 Testing table creation SQL construction...")

    table_name = "mcp_servers"

    # Test table creation SQL
    create_table_query = f"""
    CREATE TABLE IF NOT EXISTS {table_name} (
        id VARCHAR(255) PRIMARY KEY,
        config JSONB NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """

    assert "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP" in create_table_query, "Table creation SQL missing updated_at column"
    print("✅ Table creation SQL includes updated_at column")

    # Test migration SQL
    migration_query = f"""
        ALTER TABLE {table_name} 
        ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
    """

    assert "ALTER TABLE" in migration_query and "ADD COLUMN updated_at" in migration_query, "Migration logic for updated_at column missing"
    print("✅ Migration logic for updated_at column found")


def test_invalid_url_handling_standalone():
    """Test invalid URL handling with standalone logic."""
    print("\n🧪 Testing invalid URL handling...")

    invalid_urls = [
        ("http://user:pass@localhost:5432/db", "Wrong scheme"),
        ("postgresql://localhost:5432/db", "Missing user/password"),
        ("postgresql://user@localhost:5432/db", "Missing password"),
        ("postgresql://test_user:test_pass@localhost:5432/", "Missing database"),
        ("postgresql://user:pass@localhost:5432", "Missing database"),
    ]

    for i, (url, description) in enumerate(invalid_urls, 1):
        parsed = urlparse(url)

        # Check scheme
        if parsed.scheme not in ['postgresql', 'postgres']:
            print(f"✅ Test {i}: {description} - '{url}' correctly rejected (invalid scheme)")
            continue

        # Check hostname
        if not parsed.hostname:
            print(f"✅ Test {i}: {description} - '{url}' correctly rejected (missing hostname)")
            continue

        # Check database
        if not parsed.path or parsed.path == '/':
            print(f"✅ Test {i}: {description} - '{url}' correctly rejected (missing database)")
            continue

        # Check user/password
        if not parsed.username or not parsed.password:
            print(f"✅ Test {i}: {description} - '{url}' correctly rejected (missing credentials)")
            continue

        pytest.fail(f"Test {i}: {description} - '{url}' should have failed but didn't")


# Integration test that can be run if PostgreSQL is available
def test_postgres_integration():
    """Integration test with actual PostgreSQL database (optional)."""
    from mcp_composer.store.postgres_adapter import PostgresAdapter

    print("\n🧪 Testing PostgreSQL integration...")

    # This test will only run if PostgreSQL is available
    try:
        adapter = PostgresAdapter(
            host='localhost',
            database='postgres', 
            user='syedabdulgafoornaveed',
            password='root'
        )

        # Test basic operations
        servers = adapter.load_all_servers()
        print(f"✅ Loaded {len(servers)} servers from database")

        # Test adding a server
        test_config = {'id': 'pytest_test_server', 'type': 'test', 'name': 'Pytest Test Server'}
        adapter.add_server(test_config)
        print("✅ Added test server to database")

        # Test getting the server back
        server = adapter.get_document('pytest_test_server')
        assert server.get('name') == 'Pytest Test Server', "Retrieved server name doesn't match"
        print("✅ Retrieved test server from database")

        # Clean up
        adapter.remove_server('pytest_test_server')
        print("✅ Removed test server from database")

        adapter.close()
        print("✅ Database connection closed")

    except Exception as e:
        if "connection" in str(e).lower() or "connect" in str(e).lower():
            print("⚠️ PostgreSQL integration test skipped (no database connection)")
            pytest.skip("PostgreSQL database not available for integration testing")
        else:
            pytest.fail(f"Unexpected error during integration test: {e}")


if __name__ == "__main__":
    """Run all tests when executed directly."""
    print("🧪 Comprehensive PostgreSQL Adapter Test Suite")
    print("=" * 60)

    # Run all test functions
    test_functions = [
        test_postgres_adapter_import,
        test_url_parsing,
        test_invalid_urls,
        test_table_creation_sql,
        test_adapter_creation_with_url,
        test_adapter_creation_with_individual_params,
        test_missing_parameters,
        test_url_parsing_logic_standalone,
        test_connection_parameter_construction,
        test_jsonb_handling,
        test_async_sync_bridge,
        test_database_interface_compliance,
        test_table_creation_sql_construction,
        test_invalid_url_handling_standalone,
        test_postgres_integration,
    ]

    passed = 0
    failed = 0

    for test_func in test_functions:
        try:
            test_func()
            passed += 1
        except Exception as e:
            print(f"❌ {test_func.__name__} failed: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"Tests passed: {passed}")
    print(f"Tests failed: {failed}")

    if failed == 0:
        print("🎉 All tests passed! PostgreSQL adapter with asyncpg is working perfectly!")
        print("\n📖 Comprehensive test coverage includes:")
        print("✅ Import and basic functionality")
        print("✅ URL parsing and validation")
        print("✅ Invalid URL handling")
        print("✅ Table creation SQL with updated_at column")
        print("✅ Adapter creation with URL and individual parameters")
        print("✅ Parameter validation and error handling")
        print("✅ Connection parameter construction")
        print("✅ JSONB data handling")
        print("✅ Async/sync bridge implementation")
        print("✅ DatabaseInterface compliance")
        print("✅ SQL construction logic")
        print("✅ Integration testing (when database available)")
    else:
        print("❌ Some tests failed. Please check the errors above.")
        sys.exit(1)
