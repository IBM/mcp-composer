"""
MCP Composer catalog commands module.

This module provides commands for generating Backstage-compatible catalog files
from MCP servers using fastmcp client to discover tools, resources, and prompts.
"""

import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Any, Dict, List, Optional
from urllib.parse import urlparse

import typer
import yaml
from fastmcp.client import Client
from fastmcp.client.transports import SSETransport, StreamableHttpTransport
from typer import Option

from mcp_composer.core.utils.logger import LoggerFactory

# Initialize logger
logger = LoggerFactory.get_logger()

# Create Typer app for catalog commands
app = typer.Typer(
    name="catalog",
    help="MCP Composer catalog generation commands",
    add_completion=False,
    rich_markup_mode="rich",
)


@app.command("generate-catalog")
def generate_catalog(
    mcp_url: Annotated[
        str,
        Option(
            "--mcp-url", "-u", help="URL of the MCP server to generate catalog from"
        ),
    ],
    mcp_scan_output: str = typer.Option(None, help="Path to MCP-Scan output JSON"),
    output_dir: Annotated[
        str,
        Option(
            "--outputdir", "-o", help="Output directory for generated catalog files"
        ),
    ] = "./catalog",
    dry_run: Annotated[
        bool,
        Option("--dry-run", help="Show what would be generated without creating files"),
    ] = False,
) -> None:
    """
    Generate Backstage-compatible catalog files from MCP server.

    This command connects to an MCP server using fastmcp client and generates
    Backstage-compatible YAML files for tools, resources, and prompts.

    Examples:

    \b
    # Generate catalog from HTTP MCP server
    mcp-composer catalog generate-catalog --mcp-url http://localhost:8000/mcp --outputdir ./catalog

    \b
    # Dry run to see what would be generated
    mcp-composer catalog generate-catalog --mcp-url http://localhost:8000/mcp --dry-run
    """

    # Create output directory
    output_path = Path(output_dir)
    if not dry_run:
        output_path.mkdir(parents=True, exist_ok=True)
        logger.info("Created output directory: %s", output_path)

    # Run the catalog generation
    try:
        asyncio.run(
            _generate_catalog_async(
                mcp_url=mcp_url,
                output_dir=output_path,
                dry_run=dry_run,
                mcp_scan_output=mcp_scan_output,
            )
        )

        if not dry_run:
            typer.echo(f"✅ Catalog generated successfully in {output_path}")
        else:
            typer.echo("✅ Dry run completed successfully")

    except Exception as error:  # pylint: disable=broad-exception-caught
        logger.error("Failed to generate catalog: %s", error)
        typer.echo(f"❌ Error generating catalog: {error}")
        raise typer.Exit(1)


async def _generate_catalog_async(
    mcp_url: str,
    output_dir: Path,
    dry_run: bool,
    mcp_scan_output: Optional[str] = None,
) -> None:
    """Async implementation of catalog generation."""

    # Parse URL to extract server name
    parsed_url = urlparse(mcp_url)
    server_name = parsed_url.hostname or "mcp-server"
    if parsed_url.port:
        server_name = f"{server_name}-{parsed_url.port}"

    # Set defaults
    owner = "mcp"
    system = "mcp"
    product_name = server_name
    format = "yaml"
    mcp_scan_tools = {}

    if mcp_scan_output:
        # Use MCP-Scan output
        mcp_scan_tools = _load_from_mcp_scan(mcp_scan_output)

    # Detect transport type from URL
    if "/sse" in mcp_url:
        transport = "sse"
    else:
        transport = "http"

    # Create fastmcp client
    client = _create_mcp_client(mcp_url, transport, None)

    try:
        async with client:
            logger.info("Connected to MCP server: %s", mcp_url)

            # Collect data from MCP server
            components = []

            logger.info("Discovering tools...")
            tools = await _discover_tools(client)
            logger.info("Found %s tools", len(tools))

            # Generate tool components
            for tool in tools:
                mcp_scan_tool = mcp_scan_tools.get(tool["name"], {})

                component = _create_backstage_component(
                    name=tool["name"],
                    title=tool.get("title", tool["name"]),
                    description=tool.get("description", f"MCP Tool: {tool['name']}"),
                    component_type="tool",
                    owner=owner,
                    system=system,
                    product_name=server_name,
                    tags=["mcp", "tool"],
                    metadata={
                        "mcp_server": server_name,
                        "mcp_url": mcp_url,
                        "tool_name": tool["name"],
                        "tool_description": tool.get("description", ""),
                        "input_schema": mcp_scan_tool.get("input_schema", {}),
                        "output_schema": mcp_scan_tool.get("output_schema", {}),
                        "annotations": mcp_scan_tool.get("annotations", {}),
                        "scan_report": mcp_scan_tool.get("scan_report", {}),
                        "capabilities": mcp_scan_tool.get("capabilities"),
                        "policy": mcp_scan_tool.get("policy"),
                    },
                )
                components.append(component)

            # Discover resources
            logger.info("Discovering resources...")
            resources = await _discover_resources(client)
            logger.info("Found %s resources", len(resources))

            # Generate resource components
            for resource in resources:
                component = _create_backstage_component(
                    name=resource["name"],
                    title=resource.get("title", resource["name"]),
                    description=resource.get(
                        "description", f"MCP Resource: {resource['name']}"
                    ),
                    component_type="resource",
                    owner=owner,
                    system=system,
                    product_name=product_name,
                    tags=["mcp", "resource"],
                    metadata={
                        "mcp_server": server_name,
                        "mcp_url": mcp_url,
                        "resource_name": resource["name"],
                        "resource_description": resource.get("description", ""),
                        "resource_type": resource.get("type", "unknown"),
                    },
                )
                components.append(component)

            # Discover prompts
            logger.info("Discovering prompts...")
            prompts = await _discover_prompts(client)
            logger.info("Found %s prompts", len(prompts))

            # Generate prompt components
            for prompt in prompts:
                component = _create_backstage_component(
                    name=prompt["name"],
                    title=prompt.get("title", prompt["name"]),
                    description=prompt.get(
                        "description", f"MCP Prompt: {prompt['name']}"
                    ),
                    component_type="prompt",
                    owner=owner,
                    system=system,
                    product_name=product_name,
                    tags=["mcp", "prompt"],
                    metadata={
                        "mcp_server": server_name,
                        "mcp_url": mcp_url,
                        "prompt_name": prompt["name"],
                        "prompt_description": prompt.get("description", ""),
                        "prompt_template": prompt.get("template", ""),
                    },
                )
                components.append(component)

            # Write components to files
            if not dry_run:
                await _write_components_to_files(components, output_dir, format)
            else:
                _display_dry_run_results(components, format)

            logger.info("Generated %s catalog components", len(components))

    except Exception as e:
        logger.error("Error during catalog generation: %s", e)
        raise


def _create_mcp_client(
    mcp_url: str, transport: str, auth_token: Optional[str]
) -> Client:
    """Create a fastmcp client for the given URL and transport."""

    headers = {}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    if transport == "http":
        # Ensure URL ends with /mcp for HTTP transport
        if not mcp_url.endswith("/mcp"):
            mcp_url = f"{mcp_url.rstrip('/')}/mcp"
        transport_obj = StreamableHttpTransport(mcp_url, headers=headers)
    elif transport == "sse":
        # Ensure URL ends with /sse for SSE transport
        if not mcp_url.endswith("/sse"):
            mcp_url = f"{mcp_url.rstrip('/')}/sse"
        transport_obj = SSETransport(mcp_url, headers=headers)
    else:
        raise ValueError("Unsupported transport: %s", transport)

    return Client(transport_obj)


async def _discover_tools(client: Client) -> List[Dict[str, Any]]:
    """Discover tools from MCP server - MVP version."""
    try:
        tools_result = await client.list_tools()
        tools = []

        # Handle different return types - simplified for MVP
        if isinstance(tools_result, list):
            tools_list = tools_result
        else:
            # If it's not a list, try to get tools attribute
            tools_list = getattr(tools_result, "tools", [])

        for tool in tools_list:
            tool_data = {
                "name": getattr(tool, "name", "unknown-tool"),
                "description": getattr(tool, "description", ""),
                "title": getattr(tool, "title", getattr(tool, "name", "unknown-tool")),
            }
            tools.append(tool_data)

        return tools
    except Exception as error:  # pylint: disable=broad-exception-caught
        logger.warning("Failed to discover tools: %s", error)
        # Return a sample tool for MVP
        return [
            {
                "name": "sample-tool",
                "description": "Sample MCP tool",
                "title": "Sample Tool",
            }
        ]


async def _discover_resources(client: Client) -> List[Dict[str, Any]]:
    """Discover resources from MCP server - MVP version."""
    try:
        resources_result = await client.list_resources()
        resources = []

        # Handle different return types - simplified for MVP
        if isinstance(resources_result, list):
            resources_list = resources_result
        else:
            # If it's not a list, try to get resources attribute
            resources_list = getattr(resources_result, "resources", [])

        for resource in resources_list:
            resource_data = {
                "name": getattr(resource, "uri", "unknown-resource"),
                "description": getattr(resource, "description", ""),
                "title": getattr(
                    resource, "title", getattr(resource, "uri", "unknown-resource")
                ),
                "type": getattr(resource, "type", "unknown"),
            }
            resources.append(resource_data)

        return resources
    except Exception as error:  # pylint: disable=broad-exception-caught
        logger.warning("Failed to discover resources: %s", error)
        # Return a sample resource for MVP
        return [
            {
                "name": "sample-resource",
                "description": "Sample MCP resource",
                "title": "Sample Resource",
                "type": "file",
            }
        ]


async def _discover_prompts(client: Client) -> List[Dict[str, Any]]:
    """Discover prompts from MCP server - MVP version."""
    try:
        prompts_result = await client.list_prompts()
        prompts = []

        # Handle different return types - simplified for MVP
        if isinstance(prompts_result, list):
            prompts_list = prompts_result
        else:
            # If it's not a list, try to get prompts attribute
            prompts_list = getattr(prompts_result, "prompts", [])

        for prompt in prompts_list:
            prompt_data = {
                "name": getattr(prompt, "name", "unknown-prompt"),
                "description": getattr(prompt, "description", ""),
                "title": getattr(
                    prompt, "title", getattr(prompt, "name", "unknown-prompt")
                ),
                "template": getattr(prompt, "template", ""),
            }
            prompts.append(prompt_data)

        return prompts
    except Exception as error:  # pylint: disable=broad-exception-caught
        logger.warning("Failed to discover prompts: %s", error)
        # Return a sample prompt for MVP
        return [
            {
                "name": "sample-prompt",
                "description": "Sample MCP prompt",
                "title": "Sample Prompt",
                "template": "This is a sample prompt template",
            }
        ]


def _create_backstage_component(
    name: str,
    title: str,
    description: str,
    component_type: str,
    owner: str,
    system: str,
    product_name: str,
    tags: List[str],
    metadata: Dict[str, Any],
) -> Dict[str, Any]:
    """Create a Backstage-compatible component definition."""

    try:

        # Sanitize name for Backstage (lowercase, hyphens instead of underscores)
        sanitized_name = name.lower().replace("_", "-").replace(" ", "-")

        component = {
            "apiVersion": "backstage.io/v1alpha1",
            "kind": "Component",
            "metadata": {
                "name": sanitized_name,
                "title": title,
                "description": description,
                "tags": tags,
                "annotations": {
                    "backstage.io/managed-by-location": "mcp-composer",
                    "mcp-composer/component-type": component_type,
                },
                "labels": {
                    "mcp-server": metadata.get("mcp_server", "unknown"),
                    "component-type": component_type,
                },
            },
            "spec": {
                "type": component_type,
                "owner": owner,
                "system": system,
                "productName": product_name,
            },
        }

        # Add MCP-specific metadata
        for key, value in metadata.items():
            if isinstance(value, str):  # Only add non-empty string values
                component["metadata"]["annotations"][f"mcp-composer/{key}"] = str(value)
            elif isinstance(value, dict) and key in [
                "annotations",
                "scan_report",
                "capabilities",
                "policy",
            ]:
                for k, v in value.items():
                    if isinstance(v, dict) or isinstance(v, list):
                        v_str = json.dumps(v, ensure_ascii=False)
                        component["metadata"]["annotations"][
                            f"mcp-composer/{key}/{k}"
                        ] = v_str
                    else:
                        component["metadata"]["annotations"][
                            f"mcp-composer/{key}/{k}"
                        ] = str(v)

        return component
    except Exception as error:  # pylint: disable=broad-exception-caught
        logger.error(
            "Error creating Backstage component for %s: %s", name, error
        )
        raise


async def _write_components_to_files(
    components: List[Dict[str, Any]], output_dir: Path, catalog_format: str
) -> None:
    """Write components to individual files."""
    try:
        for component in components:
            component_name = component["metadata"]["name"]
            filepath = None

            if catalog_format == "yaml":
                filename = f"{component_name}.yaml"
                filepath = output_dir / filename

                with open(filepath, "w", encoding="utf-8") as f:
                    yaml.dump(component, f, default_flow_style=False, sort_keys=False)

            elif catalog_format == "json":
                filename = f"{component_name}.json"
                filepath = output_dir / filename

                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(component, f, indent=2, ensure_ascii=False)

            if filepath:
                logger.info("Written component: %s", filepath)

        # Also write a combined catalog file
        combined_filename = f"catalog.{catalog_format}"
        combined_filepath = output_dir / combined_filename

        if catalog_format == "yaml":
            with open(combined_filepath, "w", encoding="utf-8") as f:
                yaml.dump_all(components, f, default_flow_style=False, sort_keys=False)
        elif catalog_format == "json":
            with open(combined_filepath, "w", encoding="utf-8") as f:
                json.dump(components, f, indent=2, ensure_ascii=False)

        logger.info("Written combined catalog: %s", combined_filepath)

    except Exception as error:  # pylint: disable=broad-exception-caught
        logger.error("Error writing components to files: %s", error)
        raise


def _display_dry_run_results(
    components: List[Dict[str, Any]], catalog_format: str
) -> None:
    """Display dry run results."""

    typer.echo(f"\n🔍 Dry run results - would generate {len(components)} components:")
    typer.echo("=" * 60)

    for component in components:
        name = component["metadata"]["name"]
        title = component["metadata"]["title"]
        component_type = component["spec"]["type"]

        typer.echo(f"📄 {name}.{catalog_format}")
        typer.echo(f"   Title: {title}")
        typer.echo(f"   Type: {component_type}")
        typer.echo(f"   Owner: {component['spec']['owner']}")
        typer.echo(f"   System: {component['spec']['system']}")
        typer.echo()

    typer.echo("=" * 60)
    typer.echo(f"📊 Summary: {len(components)} components would be generated")

    # Show sample component
    if components:
        typer.echo(f"\n📋 Sample component ({components[0]['metadata']['name']}):")
        if catalog_format == "yaml":
            typer.echo(
                yaml.dump(components[0], default_flow_style=False, sort_keys=False)
            )
        else:
            typer.echo(json.dumps(components[0], indent=2, ensure_ascii=False))


def _load_from_mcp_scan(mcp_scan_output: str) -> Dict[str, Any]:
    """Load tools from MCP-Scan output format"""
    try:
        with open(mcp_scan_output, "r") as f:
            data = json.load(f)

        tools = {}
        # MCP-Scan output structure may vary, adjust based on actual format
        if "reports" in data:
            for server in data["reports"]:
                if "tool" in server:
                    tool = server["tool"]
                    tool_name = tool.get("name", "unknown_tool")
                    capabilities = server.get("capabilities", {})
                    policy = server.get("policy", {})
                    descriptor = {
                        "id": tool_name,
                        "name": tool_name,
                        "description": tool.get("description", ""),
                        "annotations": tool.get("annotations", {}),
                        "vendor": tool.get("vendor"),
                        "endpoint": tool.get("endpoint"),
                        "scan_report": tool.get("scan_report"),
                        "capabilities": capabilities,
                        "policy": policy,
                    }

                    tools.update({tool_name: descriptor})
        else:
            # Fallback: assume direct tools array
            for tool in data.get("tools", []):
                tool_name = tool.get("name", "unknown_tool")
                descriptor = {
                    "id": tool_name,
                    "name": tool_name,
                    "description": tool.get("description", ""),
                    "annotations": tool.get("annotations", {}),
                    "vendor": tool.get("vendor"),
                    "endpoint": tool.get("endpoint"),
                    "scan_report": tool.get("scan_report", {}),
                }
                tools.update({tool_name: descriptor})

        return tools
    except Exception as error:  # pylint: disable=broad-exception-caught
        raise RuntimeError(
            f"Failed to load tools from MCP-Scan output {mcp_scan_output}: {error}"
        ) from error


if __name__ == "__main__":
    app()
