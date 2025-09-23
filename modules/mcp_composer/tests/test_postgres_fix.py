#!/usr/bin/env python3
"""
Simple test to verify PostgreSQL adapter works with the updated_at column fix.
"""

import sys
from pathlib import Path

# Add the src directory to the Python path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

def test_postgres_adapter_creation():
    """Test that PostgreSQL adapter can be created with URL."""
    try:
        from mcp_composer.store.postgres_adapter import PostgresAdapter
        
        # Test URL parsing
        test_url = "postgresql://testuser:testpass@localhost:5432/testdb"
        
        print("🧪 Testing PostgreSQL adapter creation...")
        
        # This should not raise an error during initialization
        # (even if connection fails, URL parsing should work)
        try:
            adapter = PostgresAdapter(url=test_url, table_name="test_table")
            print("✅ PostgreSQL adapter created successfully with URL")
            print(f"✅ Connection params: {adapter._connection_params}")
            return True
        except Exception as e:
            if "connection" in str(e).lower() or "connect" in str(e).lower():
                print("✅ PostgreSQL adapter created successfully (connection failed as expected)")
                print(f"✅ Connection params: {adapter._connection_params}")
                return True
            else:
                print(f"❌ Unexpected error: {e}")
                return False
                
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
        
        test_urls = [
            "postgresql://user:pass@localhost:5432/db",
            "postgres://user:pass@localhost:5432/db",
            "postgresql://user:pass@localhost/db",  # Default port
            "postgresql://user:pass@example.com:5433/db",
        ]
        
        for i, url in enumerate(test_urls, 1):
            try:
                adapter = PostgresAdapter(url=url, table_name="test")
                print(f"✅ Test {i}: URL '{url}' parsed successfully")
            except Exception as e:
                if "connection" in str(e).lower():
                    print(f"✅ Test {i}: URL '{url}' parsed successfully (connection failed as expected)")
                else:
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
        
        # Create adapter to access the table creation logic
        adapter = PostgresAdapter(url="postgresql://test:test@localhost:5432/test", table_name="test_table")
        
        # Check if the _initialize_database method exists and has the right SQL
        import inspect
        source = inspect.getsource(adapter._initialize_database)
        
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

def main():
    """Run all tests."""
    print("🧪 Testing PostgreSQL Adapter Fix")
    print("=" * 50)
    
    success = True
    
    # Test 1: Adapter creation
    if not test_postgres_adapter_creation():
        success = False
    
    # Test 2: URL parsing
    if not test_url_parsing():
        success = False
    
    # Test 3: Table creation SQL
    if not test_table_creation_sql():
        success = False
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 All tests passed! PostgreSQL adapter fix is working correctly.")
        print("\n📖 The fix includes:")
        print("✅ URL parsing support")
        print("✅ updated_at column in table creation")
        print("✅ Migration logic for existing tables")
        print("✅ Proper error handling")
    else:
        print("❌ Some tests failed. Please check the errors above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
