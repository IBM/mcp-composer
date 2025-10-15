#!/usr/bin/env python3
"""
Example script demonstrating how to connect to an MCP server and extract tools
using the MCPTag library.
"""

import sys
import json
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent / "modules/mcp_composer/src"))
from mcp_composer.tag.scanner.mcp_protocol import McpProtocolScanner
from mcp_composer.tag.engine import TagEngine
from mcp_composer.tag.rule_dsl import Rule


def main():
    """Main function demonstrating MCP connection and tool extraction"""

    # Example MCP server endpoint (replace with your actual endpoint)
    mcp_endpoint = "http://localhost:8000"

    print(f"Connecting to MCP server at: {mcp_endpoint}")

    try:
        # Create MCP protocol scanner
        scanner = McpProtocolScanner(
            endpoint=mcp_endpoint, transport="http"  # or "sse" for Server-Sent Events
        )

        # Extract tools from the MCP server
        print("Extracting tools from MCP server...")
        tools = scanner.collect()

        print(f"Found {len(tools)} tools:")
        for i, tool in enumerate(tools, 1):
            print(f"  {i}. {tool.name}")
            print(f"     ID: {tool.id}")
            print(f"     Description: {tool.description}")
            print(f"     Vendor: {tool.vendor}")
            print(f"     Endpoint: {tool.endpoint}")
            if tool.annotations:
                print(f"     Annotations: {tool.annotations}")
            print()

        # Example: Apply some basic rules to the tools
        print("Applying basic rules to tools...")

        # Create a simple rule
        rule = Rule(
            name="example_rule",
            when={"desc_regex": r"\b(api|data|file)\b"},
            then={"add_capabilities": ["cap:data_access"]},
        )

        # Create tag engine and scan tools
        engine = TagEngine([rule])
        result = engine.scan(tools)

        print(f"Scan completed. Generated {len(result.reports)} reports.")

        # Save results to file
        output_file = "mcp_tools_scan_result.json"
        with open(output_file, "w") as f:
            json.dump(result.model_dump(), f, indent=2)

        print(f"Results saved to: {output_file}")

    except Exception as e:
        print(f"Error connecting to MCP server: {e}")
        print("\nTroubleshooting tips:")
        print("1. Make sure the MCP server is running")
        print("2. Check the endpoint URL is correct")
        print("3. Verify the server supports the MCP protocol")
        print("4. Check if authentication is required")


if __name__ == "__main__":
    main()
