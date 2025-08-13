import asyncio
from fastmcp.client import Client
from fastmcp.exceptions import ToolError


client = Client("http://localhost:8000/mcp")


async def main():
    async with client:
        # Basic server interaction
        await client.ping()

        print("Testing Circuit Breaker Middleware")
        print("=" * 50)

        # Test multiple calls to trigger circuit breaker
        for i in range(10):
            try:
                print(f"\nCall {i + 1}:")
                resp = await client.call_tool("unreliable_service", {"data": f"test_data_{i}"})
                print(f"✅ Success: {resp}")
            except ToolError as e:
                print(f"❌ Failed: {e}")

            # Small delay between calls
            await asyncio.sleep(0.5)

        print("\n" + "=" * 50)
        print("Circuit breaker should have opened after 3 failures")
        print("Wait 10 seconds for it to close again...")

        # Wait for circuit to close
        await asyncio.sleep(10)

        print("\nTesting after circuit should be closed:")
        try:
            resp = await client.call_tool("unreliable_service", {"data": "test_after_timeout"})
            print(f"✅ Success after timeout: {resp}")
        except ToolError as e:
            print(f"❌ Still failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
