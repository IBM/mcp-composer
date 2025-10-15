#!/usr/bin/env python3
"""
Demo script showing how to connect to an MCP server and extract tools.
This script demonstrates the core MCP connection functionality.
"""
import json
import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "modules/mcp_composer/src"))

from mcp_composer.tag.scanner.mcp_protocol import McpProtocolScanner
from mcp_composer.tag.engine import TagEngine
from mcp_composer.tag.rule_dsl import Rule


def demo_tool_tagging():
    """Demonstrate MCP server connection and tool extraction"""

    print("🚀 MCPTag - MCP Server Connection Demo")
    print("=" * 50)

    # Example MCP server endpoints to try
    test_endpoints = [
        "http://0.0.0.0:9000",
    ]

    for endpoint in test_endpoints:
        print(f"\n🔍 Trying to connect to: {endpoint}")

        try:
            # Create MCP protocol scanner
            scanner = McpProtocolScanner(endpoint=endpoint, transport="sse")

            # Extract tools from the MCP server
            print("   📡 Connecting and extracting tools...")
            tools = scanner.collect()

            if tools:
                print(f"   ✅ Success! Found {len(tools)} tools:")

                for i, tool in enumerate(tools, 1):
                    print(f"      {i}. {tool.name}")
                    print(f"         ID: {tool.id}")
                    print(
                        f"         Description: {tool.description[:60]}{'...' if len(tool.description) > 60 else ''}"
                    )
                    print(f"         Vendor: {tool.vendor}")

                    if tool.annotations:
                        print(f"         Annotations: {len(tool.annotations)} items")

                # Demo: Apply some basic rules
                print(f"\n   🏷️  Applying basic rules to {len(tools)} tools...")

                # Create a simple rule for demonstration
                demo_rule = Rule(
                    name="demo_data_access",
                    when={"desc_regex": r"\b(api|data|file|database|read|write)\b"},
                    then={"add_capabilities": ["cap:data_access"]},
                )

                # Create tag engine and scan tools
                engine = TagEngine([demo_rule])
                result = engine.scan(tools)

                print(f"   ✅ Rules applied! Generated {len(result.reports)} reports.")

                # Save results
                output_file = f"demo_results_{endpoint.replace('://', '_').replace(':', '_')}.json"
                with open(output_file, "w") as f:
                    json.dump(result.model_dump(), f, indent=2)

                print(f"   💾 Results saved to: {output_file}")

                return True  # Success, exit early

            else:
                print("   ⚠️  No tools found")

        except Exception as e:
            print(f"   ❌ Connection failed: {e}")
            continue

    print("\n❌ Could not connect to any MCP servers")
    print("\n💡 To test this demo:")
    print("   1. Start an MCP server on localhost:8000")
    print("   2. Or modify the test_endpoints list with your server URLs")
    print("   3. Run this script again")

    return False


def demo_with_custom_rules():
    """Demonstrate using custom rules for tool tagging"""

    print("\n🔧 Custom Rules Demo")
    print("=" * 30)

    # Example custom rules
    custom_rules = [
        Rule(
            name="api_tools",
            when={"desc_regex": r"\b(api|endpoint|rest|graphql)\b"},
            then={"add_capabilities": ["cap:api_access"]},
        ),
        Rule(
            name="file_tools",
            when={"desc_regex": r"\b(file|document|upload|download)\b"},
            then={"add_capabilities": ["cap:file_operations"]},
        ),
        Rule(
            name="data_tools",
            when={"desc_regex": r"\b(data|database|query|analytics)\b"},
            then={"add_capabilities": ["cap:data_processing"]},
        ),
    ]

    print("📋 Custom rules created:")
    for rule in custom_rules:
        print(f"   • {rule.name}: {rule.when}")

    # Try to apply these rules to a mock tool
    from mcp_composer.tag.models import ToolDescriptor

    mock_tools = [
        ToolDescriptor(
            id="file_uploader",
            name="File Upload Tool",
            description="Upload files to the system via API endpoints",
            input_schema={},
            output_schema={},
            annotations={},
            vendor="demo",
            endpoint="http://localhost:8000",
        )
    ]

    print(f"\n🔍 Applying rules to {len(mock_tools)} mock tools...")

    engine = TagEngine(custom_rules)
    result = engine.scan(mock_tools)

    print(f"✅ Rules applied! Generated {len(result.reports)} reports.")

    for report in result.reports:
        print(f"   Tool: {report.tool.name}")
        print(f"   Capabilities: {report.capabilities}")
        print(f"   Policy: {report.policy}")


def main():
    """Main demo function"""

    print("🎯 MCPTag Demo - MCP Server Connection and Tool Extraction")
    print("=" * 70)

    # Demo 1: Connect to MCP servers
    success = demo_tool_tagging()

    # Demo 2: Custom rules (always show this)
    demo_with_custom_rules()

    print("\n" + "=" * 70)
    if success:
        print("🎉 Demo completed successfully!")
        print("💡 You can now use MCP Tag to connect to your MCP servers")
    else:
        print("⚠️  Demo completed with warnings")
        print("💡 Check the troubleshooting tips above")


if __name__ == "__main__":
    main()
