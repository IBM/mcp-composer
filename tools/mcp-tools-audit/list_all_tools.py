#!/usr/bin/env python3
"""
Lists all tool names and descriptions for every active MCP server registered
in mcp-composer, by querying OpenAPI specs or live MCP endpoints.

Supports three MCP transport modes automatically:
  1. Plain JSON-RPC POST        — tried first for all http_mcp servers
  2. Streamable HTTP (MCP 2025) — retried with Accept: text/event-stream on 406
  3. Classic SSE (2-step)       — GET /sse to get session URL, then POST JSON-RPC

Usage:
    python3 list_all_tools.py
    python3 list_all_tools.py --apikey <IBM_CLOUD_API_KEY>
    python3 list_all_tools.py --format md
    python3 list_all_tools.py --format json
    python3 list_all_tools.py --format json -o tools.json
    python3 list_all_tools.py --use-db --db-host <HOST> --db-name <NAME> \
        --db-user <USER> --db-password <PASS>
"""

import argparse
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

# Global bearer token (set after exchanging API key)
_BEARER_TOKEN: str | None = None


def get_bearer_token(apikey: str) -> str:
    """Exchange an IBM Cloud API key for an IAM bearer token."""
    url = "https://iam.cloud.ibm.com/identity/token"
    data = urllib.parse.urlencode(
        {
            "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
            "apikey": apikey,
        }
    ).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        result = json.loads(resp.read().decode())
    token = result.get("access_token")
    if not token:
        raise RuntimeError(f"No access_token in IAM response: {result}")
    return token


def fetch_servers_from_db(host: str, port: int, dbname: str, user: str, password: str) -> list:
    """Fetch server configurations from PostgreSQL database."""
    try:
        import psycopg2
        import psycopg2.extras
    except ImportError:
        print("Error: psycopg2 not installed. Install with: pip install psycopg2-binary")
        return []

    try:
        conn = psycopg2.connect(host=host, port=port, dbname=dbname, user=user, password=password)
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Query the mcp_servers table — config column holds full JSON config
        cursor.execute("SELECT id, config FROM mcp_servers")

        rows = cursor.fetchall()
        servers = []

        for row in rows:
            cfg = row["config"]
            if isinstance(cfg, str):
                cfg = json.loads(cfg)

            kind = cfg.get("type") or cfg.get("kind")
            server = {"id": row["id"], "kind": kind}

            if kind == "openapi":
                server["spec_url"] = cfg.get("spec_url")
                if cfg.get("custom_routes"):
                    server["custom_routes"] = cfg["custom_routes"]
            elif kind == "http_mcp":
                server["endpoint"] = cfg.get("endpoint") or cfg.get("url")

            servers.append(server)

        cursor.close()
        conn.close()

        print(f"✅ Loaded {len(servers)} servers from database")
        return servers

    except Exception as e:
        print(f"❌ Database error: {e}")
        return []


# ── Server registry ─────────────────────────────────────────────────────────
# Configure your MCP servers here, or use --use-db to load from a database.
# Each entry must have:
#   - id:   a unique name for the server
#   - kind: "openapi" (reads an OpenAPI spec URL) or "http_mcp" (queries a live MCP endpoint)
#
# For "openapi" servers, also set:
#   - spec_url:      URL to the OpenAPI JSON spec
#   - custom_routes: list of route rules that map HTTP methods/paths to TOOL or EXCLUDE
#
# For "http_mcp" servers, also set:
#   - endpoint: base URL of the MCP server (e.g. https://your-server.example.com/mcp)
#
# Example:
SERVERS = [
    # OpenAPI-type example:
    # {
    #     "id": "my-openapi-server",
    #     "kind": "openapi",
    #     "spec_url": "https://example.com/openapi.json",
    #     "custom_routes": [
    #         {"methods": ["GET"], "pattern": ".*", "mcp_type": "TOOL"},
    #         {"methods": ["POST", "DELETE", "PUT", "PATCH"],
    #          "pattern": ".*", "mcp_type": "EXCLUDE"},
    #     ],
    # },
    # HTTP MCP-type example:
    # {
    #     "id": "my-mcp-server",
    #     "kind": "http_mcp",
    #     "endpoint": "https://your-server.example.com/mcp",
    # },
]

# Deactivated — included for reference only
DEACTIVATED: list = []


def fetch_json(url: str) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": "mcp-tool-lister/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def is_included(method: str, path: str, custom_routes: list[dict]) -> bool:
    """Apply mcp-composer's custom_routes filtering logic."""
    result = None
    for route in custom_routes:
        if method.upper() in [m.upper() for m in route["methods"]]:
            if re.search(route["pattern"], path):
                result = route["mcp_type"]
    return result == "TOOL"


def tools_from_openapi(server: dict) -> list[dict]:
    """Extract tool names + descriptions from an OpenAPI spec."""
    tools = []
    try:
        spec = fetch_json(server["spec_url"])
    except Exception as e:
        return [{"name": "ERROR", "description": str(e)}]

    for path, path_item in spec.get("paths", {}).items():
        for method, op in path_item.items():
            if method not in ("get", "post", "put", "delete", "patch"):
                continue
            if not isinstance(op, dict):
                continue
            routes = server.get("custom_routes", [])
            if routes and not is_included(method, path, routes):
                continue
            op_id = op.get("operationId", f"{method}_{path.replace('/', '_')}")
            summary = op.get("summary") or op.get("description") or ""
            summary = summary.strip().replace("\n", " ")
            tools.append({"name": op_id, "description": summary})
    return tools


def _auth_headers() -> dict:
    """Base headers, with Authorization if a token is available."""
    h = {"Content-Type": "application/json", "User-Agent": "mcp-tool-lister/1.0"}
    if _BEARER_TOKEN:
        h["Authorization"] = f"Bearer {_BEARER_TOKEN}"
    return h


def _parse_tools(data: dict) -> list[dict]:
    raw = data.get("result", {}).get("tools", [])
    return [{"name": t.get("name", ""), "description": t.get("description", "")} for t in raw]


def _parse_sse_body(body: str) -> dict | None:
    """Extract the first JSON object from an SSE response body (data: ... lines)."""
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            payload = line[5:].strip()
            if payload and payload != "[DONE]":
                try:
                    return json.loads(payload)
                except json.JSONDecodeError:
                    continue
    return None


def _try_plain_post(endpoint: str) -> list[dict] | None:
    """Attempt 1: plain JSON-RPC POST (original approach)."""
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}).encode()
    req = urllib.request.Request(endpoint, data=payload, headers=_auth_headers(), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        return _parse_tools(data)
    except urllib.error.HTTPError as e:
        if e.code in (406, 415):
            return None  # signal: try SSE approaches
        raise
    except Exception:
        raise


def _try_streamable_http(endpoint: str) -> list[dict] | None:
    """Attempt 2: MCP Streamable HTTP transport (POST + Accept: text/event-stream).
    Servers that speak the 2024-11-05 / 2025-03-26 spec respond with an SSE body."""
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}).encode()
    headers = _auth_headers()
    headers["Accept"] = "application/json, text/event-stream"
    req = urllib.request.Request(endpoint, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            content_type = resp.headers.get("Content-Type", "")
            body = resp.read().decode()
        if "text/event-stream" in content_type:
            data = _parse_sse_body(body)
            if data:
                return _parse_tools(data)
            return []
        else:
            return _parse_tools(json.loads(body))
    except urllib.error.HTTPError as e:
        if e.code in (406, 415):
            return None  # signal: try classic SSE
        raise
    except Exception:
        raise


def _try_classic_sse(endpoint: str) -> list[dict]:
    """Attempt 3: Classic 2-step SSE transport.
    Step 1 — GET /sse, read the 'endpoint' event to get the session POST URL.
    Step 2 — POST JSON-RPC to that URL; read the JSON-RPC response from the SSE stream.
    """
    # Build the SSE URL: replace trailing /mcp with /sse, or append /sse
    if endpoint.endswith("/mcp"):
        sse_url = endpoint[:-4] + "/sse"
    else:
        sse_url = endpoint.rstrip("/") + "/sse"

    headers = {
        "Accept": "text/event-stream",
        "User-Agent": "mcp-tool-lister/1.0",
        "Cache-Control": "no-cache",
    }
    if _BEARER_TOKEN:
        headers["Authorization"] = f"Bearer {_BEARER_TOKEN}"

    session_url: list[str] = []  # mutable container for thread communication
    result_data: list[dict] = []

    def read_sse(resp):
        """Read SSE stream: capture 'endpoint' event, then capture tool result."""
        event_type = ""
        for raw in resp:
            line = raw.decode("utf-8", errors="replace").rstrip("\n").rstrip("\r")
            if line.startswith("event:"):
                event_type = line[6:].strip()
            elif line.startswith("data:"):
                data_val = line[5:].strip()
                if event_type == "endpoint":
                    # session URL may be relative or absolute
                    base = endpoint.rsplit("/", 1)[0]
                    url = data_val if data_val.startswith("http") else base + data_val
                    session_url.append(url)
                elif data_val and data_val != "[DONE]":
                    try:
                        parsed = json.loads(data_val)
                        if "result" in parsed:
                            result_data.extend(_parse_tools(parsed))
                            return  # got what we need
                    except json.JSONDecodeError:
                        pass
            elif line == "":
                event_type = ""  # blank line = end of event

    req = urllib.request.Request(sse_url, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as resp:
        # Run SSE reader in a thread so we can POST once we have the session URL
        reader = threading.Thread(target=read_sse, args=(resp,), daemon=True)
        reader.start()

        # Wait for session URL (up to 5 s)
        deadline = time.time() + 5
        while not session_url and time.time() < deadline:
            time.sleep(0.05)

        if not session_url:
            reader.join(timeout=1)
            raise RuntimeError("Classic SSE: no 'endpoint' event received within 5s")

        # POST the JSON-RPC request to the session URL
        payload = json.dumps(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
        ).encode()
        post_headers = _auth_headers()
        post_req = urllib.request.Request(
            session_url[0], data=payload, headers=post_headers, method="POST"
        )
        with urllib.request.urlopen(post_req, timeout=10):
            pass  # response comes back on the SSE stream

        # Wait for the tool list to arrive on the SSE stream (up to 10 s)
        reader.join(timeout=10)

    return result_data


def tools_from_http_mcp(server: dict) -> list[dict]:
    """Try to list tools from a live MCP HTTP endpoint.
    Attempts three transports in order: plain POST → streamable HTTP → classic SSE.
    """
    endpoint = server["endpoint"].rstrip("/")

    # Attempt 1: plain JSON-RPC POST
    try:
        result = _try_plain_post(endpoint)
        if result is not None:
            return result
        print("    ↳ plain POST returned 406 — trying streamable HTTP...", flush=True)
    except Exception as e:
        return [{"name": "ERROR", "description": str(e)}]

    # Attempt 2: streamable HTTP (POST + Accept: text/event-stream)
    try:
        result = _try_streamable_http(endpoint)
        if result is not None:
            return result
        print("    ↳ streamable HTTP returned 406 — trying classic SSE...", flush=True)
    except Exception as e:
        return [{"name": "ERROR", "description": str(e)}]

    # Attempt 3: classic 2-step SSE
    try:
        return _try_classic_sse(endpoint)
    except Exception as e:
        return [{"name": "ERROR", "description": str(e)}]


def collect_all() -> dict[str, list[dict]]:
    results = {}
    for server in SERVERS:
        print(f"  Fetching {server['id']}...", flush=True)
        if server["kind"] == "openapi":
            tools = tools_from_openapi(server)
        else:
            tools = tools_from_http_mcp(server)
        errors = sum(1 for t in tools if t["name"].startswith("ERROR"))
        ok = len(tools) - errors
        status = (
            f"✅ {ok} tools"
            if errors == 0
            else ("❌ failed" if ok == 0 else f"⚠️  {ok} tools, {errors} errors")
        )
        print(f"    {status}", flush=True)
        results[server["id"]] = tools
    return results


def print_text(results: dict[str, list[dict]]):
    for server_id, tools in results.items():
        print(f"\n{'='*60}")
        print(f"  {server_id}  ({len(tools)} tools)")
        print(f"{'='*60}")
        for t in tools:
            desc = (
                t["description"][:100] + "..." if len(t["description"]) > 100 else t["description"]
            )
            print(f"  {t['name']}")
            if desc:
                print(f"    → {desc}")
    if DEACTIVATED:
        print(f"\n{'='*60}")
        print("  DEACTIVATED (not mounted):")
        for s in DEACTIVATED:
            print(f"  - {s}")


def print_markdown(results: dict[str, list[dict]]):
    for server_id, tools in results.items():
        print(f"\n## {server_id}\n")
        print("| Tool | Description |")
        print("|------|-------------|")
        for t in tools:
            desc = t["description"].replace("|", "\\|")[:120]
            print(f"| `{t['name']}` | {desc} |")
    if DEACTIVATED:
        print("\n## Deactivated servers\n")
        for s in DEACTIVATED:
            print(f"- `{s}`")


def print_json_out(results: dict[str, list[dict]], output_file: str = None):
    output = {
        "active": results,
        "deactivated": DEACTIVATED,
    }
    json_str = json.dumps(output, indent=2)

    if output_file:
        with open(output_file, "w") as f:
            f.write(json_str)
        print(f"✅ JSON output saved to: {output_file}")
    else:
        print(json_str)


def main():
    global _BEARER_TOKEN, SERVERS
    parser = argparse.ArgumentParser(
        description="List all mcp-composer tool names and descriptions"
    )
    parser.add_argument("--format", choices=["text", "md", "json"], default="text")
    parser.add_argument("--output", "-o", help="Output file path (for JSON format)")
    parser.add_argument(
        "--apikey", help="IBM Cloud API key — exchanges for bearer token to auth http_mcp servers"
    )

    # Database options
    parser.add_argument(
        "--use-db",
        action="store_true",
        help="Fetch server list from database instead of hardcoded list",
    )
    parser.add_argument("--db-host", help="Database host (default: from env MCP_DATABASE_HOST)")
    parser.add_argument("--db-port", type=int, default=5432, help="Database port (default: 5432)")
    parser.add_argument("--db-name", help="Database name (default: from env MCP_DATABASE_NAME)")
    parser.add_argument("--db-user", help="Database user (default: from env MCP_DATABASE_USER)")
    parser.add_argument(
        "--db-password", help="Database password (default: from env MCP_DATABASE_PASSWORD)"
    )

    args = parser.parse_args()

    # Handle database mode
    if args.use_db:
        print("📊 Fetching server list from database...", flush=True)
        db_host = args.db_host or os.getenv("MCP_DATABASE_HOST")
        db_name = args.db_name or os.getenv("MCP_DATABASE_NAME", "postgres")
        db_user = args.db_user or os.getenv("MCP_DATABASE_USER", "postgres")
        db_password = args.db_password or os.getenv("MCP_DATABASE_PASSWORD")

        if not all([db_host, db_name, db_user, db_password]):
            print("❌ Error: Database credentials required. Provide via --db-* flags or env vars.")
            print(
                "   Required: MCP_DATABASE_HOST, MCP_DATABASE_NAME, "
                "MCP_DATABASE_USER, MCP_DATABASE_PASSWORD"
            )
            return

        db_servers = fetch_servers_from_db(db_host, args.db_port, db_name, db_user, db_password)
        if db_servers:
            SERVERS = db_servers
            print(f"✅ Using {len(SERVERS)} servers from database\n", flush=True)
        else:
            print(
                "⚠️  No servers loaded from database, falling back to hardcoded list\n", flush=True
            )

    if args.apikey:
        print("Exchanging IBM Cloud API key for bearer token...", flush=True)
        try:
            _BEARER_TOKEN = get_bearer_token(args.apikey)
            print("  ✅ Token obtained.\n", flush=True)
        except Exception as e:
            print(f"  ❌ Failed to get token: {e}\n", flush=True)

    print("Fetching tool specs...\n")
    results = collect_all()

    if args.format == "md":
        print_markdown(results)
    elif args.format == "json":
        print_json_out(results, args.output)
    else:
        print_text(results)


if __name__ == "__main__":
    main()
