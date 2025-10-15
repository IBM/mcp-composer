import json
import typer
import subprocess
import os
from rich import print
from .rule_dsl import Rule
from .engine import TagEngine
from .scanner.json_file import JsonFileScanner
from .scanner.mcp_protocol import McpProtocolScanner
from .exporters.backstage import BackstageExporter
from .policy_eval import PolicyGate
from .models import TagReport, ToolDescriptor
from typing import List, Optional
from urllib.parse import urlparse

app = typer.Typer(
    add_completion=False, help="MCPTag - MCP Security Scanning and Tool Tagging Tool"
)


@app.command()
def tag(
    from_json: str = typer.Option(None, help="Path to JSON tool descriptors"),
    mcp_endpoint: str = typer.Option(None, help="Live MCP endpoint (optional)"),
    mcp_auth_token: str = typer.Option(
        None, help="Authorization token for MCP endpoint"
    ),
    mcp_transport: str = typer.Option("http", help="MCP transport type: http|sse"),
    command: str = typer.Option(None, help="Command for running in stdio mode"),
    args: str = typer.Option(None, help="Arguments for the command in stdio mode"),
    mcp_scan_output: str = typer.Option(None, help="Path to MCP-Scan output JSON"),
    rules: str = typer.Option("rules/rules_default.yaml", help="Rules YAML file"),
    policy: str = typer.Option(None, help="Policy YAML (optional)"),
    out: str = typer.Option(None, help="Write TagResult JSON to this path"),
):
    """Tag MCP tools based on rules for compliance and capability analysis"""
    # try:
    # Fix: resolve rules path relative to this file if not absolute
    rules_path = rules
    if not os.path.isabs(rules_path):
        script_dir = os.path.dirname(__file__)
        rules_path = os.path.join(script_dir, rules_path)
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
        raise typer.BadParameter(
            "Provide either --mcp-scan-output, --from-json, or --mcp-endpoint"
        )

    # Tag the tools
    result = engine.scan(tools)

    if out:
        json.dump(result.model_dump(), open(out, "w"), indent=2)
        print(f"[green]Tagging results written to[/green] {out}")
    else:
        print(json.dumps(result.model_dump(), indent=2))

    # except Exception as e:
    #     print(f"[red]Error during tagging:[/red] {e}")
    #     raise typer.Exit(1)


def _load_from_mcp_scan(mcp_scan_output: str) -> List[ToolDescriptor]:
    """Load tools from MCP-Scan output format"""
    try:
        with open(mcp_scan_output, "r") as f:
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
        )


@app.command()
def check(
    report: str = typer.Option(..., help="Path to ScanResult JSON"),
    require: list[str] = typer.Option(None, help="One or more gating expressions"),
):
    data = json.load(open(report))
    gate = PolicyGate(require or [])
    ok, failures = gate.evaluate(
        type("ScanResultObj", (), {"reports": data["reports"]})
    )
    if not ok:
        print("[red]Policy gate failed:[/red]", failures)
        raise typer.Exit(1)
    print("[green]Policy gate passed[/green]")


@app.command()
def export(
    backend: str = typer.Argument(..., help="export backend, e.g., backstage"),
    report: str = typer.Option(..., help="Path to ScanResult JSON"),
    out: str = typer.Option(..., help="Destination (dir or file)"),
):
    data = json.load(open(report))
    reports = []
    for r in data["reports"]:
        reports.append(TagReport(**r))

    if backend == "backstage":
        BackstageExporter(out).write(reports)
        print(f"[green]Exported Backstage entities to[/green] {out}")
    else:
        raise typer.BadParameter("Unsupported backend")
