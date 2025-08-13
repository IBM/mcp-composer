import asyncio
from fastmcp.client import Client
from fastmcp.exceptions import ToolError


async def test_rate_limits(client):
    """Test rate limiting behavior"""
    print("Testing Rate Limiter Middleware")
    print("=" * 50)

    # Test search_docs (lower limits)
    print("\nTesting search_docs (burst limit: 5, rate: 0.5/s):")
    for i in range(8):
        try:
            resp = await client.call_tool("search_docs", {"query": f"search query {i}"})
            print(f"✅ Call {i + 1}: Success")
        except ToolError as e:
            print(f"❌ Call {i + 1}: Rate limited - {e}")

        await asyncio.sleep(0.1)  # Small delay

    # Wait for tokens to refill
    print("\nWaiting 2 seconds for tokens to refill...")
    await asyncio.sleep(2)

    # Test ask_llm (higher limits but higher cost)
    print("\nTesting ask_llm (burst limit: 10, rate: 1/s, cost: ~5 per call):")
    for i in range(12):
        try:
            resp = await client.call_tool("ask_llm", {"query": f"AI question {i}"})
            print(f"✅ Call {i + 1}: Success")
        except ToolError as e:
            print(f"❌ Call {i + 1}: Rate limited - {e}")

        await asyncio.sleep(0.1)  # Small delay

    # Test rapid calls to trigger rate limiting
    print("\nTesting rapid calls to trigger rate limiting:")
    tasks = []
    for i in range(15):
        task = client.call_tool("search_docs", {"query": f"rapid query {i}"})
        tasks.append(task)

    results = await asyncio.gather(*tasks, return_exceptions=True)

    success_count = 0
    rate_limited_count = 0
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            if "Rate limited" in str(result):
                rate_limited_count += 1
                print(f"❌ Call {i + 1}: Rate limited")
            else:
                print(f"❌ Call {i + 1}: Error - {result}")
        else:
            success_count += 1
            print(f"✅ Call {i + 1}: Success")

    print(f"\nSummary: {success_count} succeeded, {rate_limited_count} rate limited")


client = Client("http://localhost:8000/mcp")


async def main():
    async with client:
        await test_rate_limits(client)


if __name__ == "__main__":
    asyncio.run(main())
