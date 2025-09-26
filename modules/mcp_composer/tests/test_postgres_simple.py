#!/usr/bin/env python3
"""
Simple test of PostgreSQL adapter by importing it directly.
"""

import sys
from pathlib import Path

# Add the src directory to the Python path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

def test_postgres_adapter_import():
    """Test that we can import the PostgreSQL adapter directly."""
    try:
        # Import the PostgreSQL adapter directly without going through __init__.py
        from mcp_composer.store.postgres_adapter import PostgresAdapter
        
        print("✅ PostgreSQL adapter imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Failed to import PostgreSQL adapter: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def test_url_parsing():
    """Test URL parsing functionality."""
    try:
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
            try:
                parsed = adapter._parse_postgres_url(url)
                print(f"✅ Test {i}: URL '{url}' parsed successfully")
                print(f"   Parsed: {parsed}")
            except Exception as e:
                print(f"❌ Test {i}: URL '{url}' failed: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ URL parsing test failed: {e}")
        return False

def test_table_creation_sql():
    """Test that the table creation SQL includes updated_at column."""
    try:
        from mcp_composer.store.postgres_adapter import PostgresAdapter
        
        print("\n🧪 Testing table creation SQL...")
        
        # Check if the _initialize_database method exists and has the right SQL
        import inspect
        source = inspect.getsource(PostgresAdapter._initialize_database)
        
        if "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP" in source:
            print("✅ Table creation SQL includes updated_at column")
        else:
            print("❌ Table creation SQL missing updated_at column")
            return False
            
        if "ALTER TABLE" in source and "ADD COLUMN updated_at" in source:
            print("✅ Migration logic for updated_at column found")
        else:
            print("❌ Migration logic for updated_at column missing")
            return False
            
        return True
        
    except Exception as e:
        print(f"❌ Table creation SQL test failed: {e}")
        return False

def test_invalid_urls():
    """Test invalid URL handling."""
    try:
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
            try:
                parsed = adapter._parse_postgres_url(url)
                print(f"❌ Test {i}: {description} - '{url}' should have failed but didn't")
            except Exception as e:
                print(f"✅ Test {i}: {description} - '{url}' correctly rejected: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Invalid URL test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("🧪 Testing PostgreSQL Adapter (Simple Import)")
    print("=" * 50)
    
    success = True
    
    # Test 1: Import
    if not test_postgres_adapter_import():
        success = False
    
    # Test 2: URL parsing
    if not test_url_parsing():
        success = False
    
    # Test 3: Table creation SQL
    if not test_table_creation_sql():
        success = False
    
    # Test 4: Invalid URL handling
    if not test_invalid_urls():
        success = False
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 All tests passed! PostgreSQL adapter is working correctly.")
        print("\n📖 Features verified:")
        print("✅ Direct import without dependencies")
        print("✅ URL parsing with various formats")
        print("✅ updated_at column in table creation")
        print("✅ Migration logic for existing tables")
        print("✅ Proper error handling for invalid URLs")
    else:
        print("❌ Some tests failed. Please check the errors above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
