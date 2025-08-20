import asyncio
from fastmcp.client import Client
import json


async def main():
    client = Client("http://localhost:8000")

    print("Testing XML to JSON Middleware")
    print("=" * 50)

    # Test user data (XML response)
    print("\n1. Testing get_user_data (XML response):")
    try:
        resp = await client.call_tool("get_user_data", {"user_id": "12345"})
        print("✅ Success!")
        print("Response structure:")
        print(f"  Is Error: {getattr(resp, 'isError', False)}")
        print(
            f"  Has Structured Content: {hasattr(resp, 'structuredContent') and getattr(resp, 'structuredContent', None) is not None}"
        )

        # Check if data is now JSON instead of XML
        # Access content from the CallToolResult
        data = ""
        if hasattr(resp, "content") and resp.content:
            # Extract text from content blocks
            for block in resp.content:
                if (
                    hasattr(block, "text")
                    and hasattr(block, "type")
                    and block.type == "text"
                ):
                    data += block.text
        if data.startswith("{") or data.startswith("["):
            print("✅ Data is now in JSON format!")
            try:
                json_data = json.loads(data) if isinstance(data, str) else data
                print("  Parsed JSON structure:")
                print(f"    User ID: {json_data.get('user', {}).get('id')}")
                print(f"    Name: {json_data.get('user', {}).get('name')}")
                print(f"    Email: {json_data.get('user', {}).get('email')}")
            except json.JSONDecodeError:
                print("❌ Failed to parse as JSON")
        else:
            print("❌ Data is still in XML format")

    except Exception as e:
        print(f"❌ Error: {e}")

    # Test product catalog (XML response)
    print("\n2. Testing get_product_catalog (XML response):")
    try:
        resp = await client.call_tool(
            "get_product_catalog", {"category": "electronics"}
        )
        print("✅ Success!")

        # Check if data is now JSON
        # Access content from the CallToolResult
        data = ""
        if hasattr(resp, "content") and resp.content:
            # Extract text from content blocks
            for block in resp.content:
                if (
                    hasattr(block, "text")
                    and hasattr(block, "type")
                    and block.type == "text"
                ):
                    data += block.text
        if data.startswith("{") or data.startswith("["):
            print("✅ Data is now in JSON format!")
            try:
                json_data = json.loads(data) if isinstance(data, str) else data
                print("  Parsed JSON structure:")
                catalog = json_data.get("catalog", {})
                print(f"    Category: {catalog.get('@attributes', {}).get('category')}")
                products = catalog.get("product", [])
                if not isinstance(products, list):
                    products = [products]
                print(f"    Number of products: {len(products)}")
                for i, product in enumerate(products):
                    print(
                        f"      Product {i+1}: {product.get('name')} - ${product.get('price')}"
                    )
            except json.JSONDecodeError:
                print("❌ Failed to parse as JSON")
        else:
            print("❌ Data is still in XML format")

    except Exception as e:
        print(f"❌ Error: {e}")

    print("\n" + "=" * 50)
    print("Expected behavior:")
    print("- XML responses should be automatically converted to JSON format")
    print("- The middleware should preserve the XML structure as JSON objects")
    print("- Attributes should be preserved with @attributes key")


if __name__ == "__main__":
    asyncio.run(main())
