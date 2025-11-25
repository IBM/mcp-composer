import json
import os
from typing import List

import typer
from rich import print as rprint

from mcp_composer.tag.rule_dsl import Rule
from mcp_composer.tag.engine import TagEngine
from mcp_composer.tag.scanner.json_file import JsonFileScanner
from mcp_composer.tag.scanner.mcp_protocol import McpProtocolScanner
from mcp_composer.tag.exporters.backstage import BackstageExporter
from mcp_composer.tag.policy_eval import PolicyGate
from mcp_composer.tag.models import TagReport, ToolDescriptor
from mcp_composer.core.utils.logger import LoggerFactory

# Initialize logger
logger = LoggerFactory.get_logger()

app = typer.Typer(
    name="tag",
    help="MCPTag - MCP Security Scanning and Tool Tagging Tool",
    add_completion=False,
    rich_markup_mode="rich",
)


@app.command("generate-tag")
def generate_tag(
    from_json: str = typer.Option(None, help="Path to JSON tool descriptors"),
    mcp_endpoint: str = typer.Option(None, help="Live MCP endpoint (optional)"),
    mcp_auth_token: str = typer.Option(
        None, help="Authorization token for MCP endpoint"
    ),
    mcp_transport: str = typer.Option("http", help="MCP transport type: http|sse"),
    command: str = typer.Option(None, help="Command for running in stdio mode"),
    mcp_scan_output: str = typer.Option(None, help="Path to MCP-Scan output JSON"),
    args: str = typer.Option(None, help="Arguments for the command in stdio mode"),
    rules: str = typer.Option("rules/rules_default.yaml", help="Rules YAML file"),
    policy: str = typer.Option(None, help="Policy YAML (optional)"),  # pylint: disable=unused-argument
    output: str = typer.Option(
        None, help="Write MCP Tag/Scan/Catalog results to this path"
    ),
):
    """Tag MCP tools based on rules for compliance and capability analysis"""
    try:
        # Fix: resolve rules path relative to this file if not absolute
        rules_path = rules
        if not os.path.isabs(rules_path):
            script_dir = os.path.dirname(__file__)
            # Go up two levels (from cli → core → mcp), then into tag/rules/
            rules_path = os.path.abspath(
                os.path.join(script_dir, "../../..", "tag", rules_path)
            )

        rule_objs = Rule.load_all(rules_path)
        engine = TagEngine(rule_objs)

        # Determine source of tools
        if mcp_scan_output:
            # Use MCP-Scan output
            tools = _load_from_mcp_scan(mcp_scan_output)
        elif from_json:
            # Use JSON file
            scanner = JsonFileScanner(from_json)
            tools = scanner.collect()
        elif mcp_transport:
            if mcp_transport in ["http", "sse"] and not mcp_endpoint:
                raise typer.BadParameter("Provide --mcp-endpoint")

            if mcp_transport == "stdio" and not command:
                raise typer.BadParameter("Provide --command for stdio transport")

            # Use live MCP endpoint with protocol scanner
            scanner = McpProtocolScanner(
                mcp_endpoint,
                auth_token=mcp_auth_token,
                transport=mcp_transport,
                command=command,
                args=args,
            )
            tools = scanner.collect()
        else:
            raise typer.BadParameter("Provide either --from-json, or --mcp-endpoint")

        # Tag the tools
        result = engine.scan(tools)
        rprint(f"[green]Tagged {len(result.reports)} tools successfully[/green]")

        if output:
            with open(output, "w", encoding="utf-8") as f:
                json.dump(result.model_dump(), f, indent=2, ensure_ascii=False)
            rprint(f"[green]Tagging results written to[/green] {output}")
        else:
            rprint(json.dumps(result.model_dump(), indent=2, ensure_ascii=False))

    except Exception as e:
        rprint(f"[red]Error during tagging:[/red] {e}")
        raise typer.Exit(1)


def _load_from_mcp_scan(mcp_scan_output: str) -> List[ToolDescriptor]:
    """Load tools from MCP-Scan output format"""
    try:
        with open(mcp_scan_output, "r", encoding="utf-8") as f:
            data = json.load(f)

        tools = []
        # MCP-Scan output structure may vary, adjust based on actual format
        if "servers" in data:
            for server in data["servers"]:
                if "tools" in server:
                    for tool in server["tools"]:
                        descriptor = ToolDescriptor(
                            id=tool.get("name", ""),
                            name=tool.get("name", ""),
                            description=tool.get("description", ""),
                            input_schema=tool.get("inputSchema", {}),
                            output_schema=tool.get("outputSchema", {}),
                            annotations=tool.get("annotations", {}),
                            vendor=tool.get("vendor"),
                            endpoint=server.get("endpoint"),
                        )
                        tools.append(descriptor)
        else:
            # Fallback: assume direct tools array
            for tool in data.get("tools", []):
                descriptor = ToolDescriptor(
                    id=tool.get("name", ""),
                    name=tool.get("name", ""),
                    description=tool.get("description", ""),
                    input_schema=tool.get("inputSchema", {}),
                    output_schema=tool.get("outputSchema", {}),
                    annotations=tool.get("annotations", {}),
                    vendor=tool.get("vendor"),
                )
                tools.append(descriptor)

        return tools
    except Exception as e:
        raise RuntimeError(
            f"Failed to load tools from MCP-Scan output {mcp_scan_output}: {e}"
        ) from e


@app.command()
def check(
    report: str = typer.Option(..., help="Path to ScanResult JSON"),
    require: list[str] = typer.Option(None, help="One or more gating expressions"),
):
    with open(report, "r", encoding="utf-8") as f:
        data = json.load(f)
    gate = PolicyGate(require or [])
    ok, failures = gate.evaluate(
        type("ScanResultObj", (), {"reports": data["reports"]})
    )
    if not ok:
        rprint("[red]Policy gate failed:[/red]", failures)
        raise typer.Exit(1)
    rprint("[green]Policy gate passed[/green]")


@app.command()
def export(
    backend: str = typer.Argument(..., help="export backend, e.g., backstage"),
    report: str = typer.Option(..., help="Path to ScanResult JSON"),
    out: str = typer.Option(..., help="Destination (dir or file)"),
):
    with open(report, "r", encoding="utf-8") as f:
        data = json.load(f)
    reports = []
    for r in data["reports"]:
        reports.append(TagReport(**r))

    if backend == "backstage":
        BackstageExporter(out).write(reports)
        rprint(f"[green]Exported Backstage entities to[/green] {out}")
    else:
        raise typer.BadParameter("Unsupported backend")
