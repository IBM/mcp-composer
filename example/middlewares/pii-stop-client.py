import asyncio
from fastmcp.client import Client


client = Client("http://localhost:8000/mcp")


async def main():
    async with client:
        # Simulate sending sensitive data
        form_data = {
            "name": "Alice Example",
            "email": "alice@example.com",
            "password": "SuperSecret123!",
            "credit_card": "4111 1111 1111 1111",
            "note": "Please call me at +1-202-555-0123",
            "public_info": "This is fine to show",
        }

        resp = await client.call_tool("process_form", {"data": form_data})
        print("Server Response:\n", resp)


asyncio.run(main())
