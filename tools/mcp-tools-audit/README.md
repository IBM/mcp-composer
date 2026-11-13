# MCP Tools Audit

A comprehensive toolkit for auditing and analyzing MCP (Model Context Protocol) tool definitions to improve tool selection reliability and agent decision-making.

> **📖 Quick Start:** See [INSTALL.md](INSTALL.md) for detailed installation instructions, including how to install Bob skills.

## Overview

This repository contains:
1. **`list_all_tools.py`** - A Python script that fetches and lists all MCP tools from registered servers
2. **`bob-skills/`** - Bob AI skill artifacts for performing detailed tool audits and generating reports

**⚠️ Important:** To use the audit functionality, you must install the Bob skills to your local `~/.bob/skills/` directory. See [Installation](#installation) below.

## Features

### Tool Listing Script (`list_all_tools.py`)

- Fetches tool definitions from multiple MCP server types:
  - OpenAPI-based servers (reads tools from an OpenAPI JSON spec)
  - HTTP MCP servers (queries live endpoints)
- Supports three MCP transport modes:
  - Plain JSON-RPC POST
  - Streamable HTTP (MCP 2025)
  - Classic SSE (2-step)
- Handles authentication via IBM Cloud API keys
- Outputs in multiple formats: text, markdown, JSON

### Bob Skills for Tool Audit

The `bob-skills/` folder contains comprehensive documentation and templates for:
- Identifying naming collisions and duplicates
- Analyzing description quality and overlaps
- Detecting ambiguous or vague tool definitions
- Generating actionable recommendations
- Creating prevention guidelines

## Prerequisites

- Python 3.7 or higher
- (Optional) IBM Cloud API key — only needed when your MCP servers require authentication
- (Optional) `psycopg2-binary` Python package — only needed for the `--use-db` mode

## Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd mcp-tools-audit
```

### 2. Install Bob Skills (Required for Auditing)

To use the tool audit capabilities with Bob AI, copy the skills to your Bob skills directory:

```bash
# Copy the tool-audit skill to your Bob skills directory
cp -r bob-skills ~/.bob/skills/tool-audit
```

**Verify installation:**
```bash
ls ~/.bob/skills/tool-audit
# Should show: SKILL.md, README.md, QUICK-START.md, etc.
```

**Note:** Bob skills work in **Agent mode**. Make sure you are in Agent mode before using the audit skill.

### 3. (Optional) Set Up Environment Variables

For the `list_all_tools.py` script:
```bash
cp .env.example .env
# Edit .env and add your IBM_CLOUD_API_KEY
```

### 4. Dependencies

Basic usage requires only the Python standard library. The `--use-db` flag additionally
requires `psycopg2-binary`:

```bash
pip install psycopg2-binary
```

## Usage

### Basic Usage

List all tools in text format:
```bash
python3 list_all_tools.py
```

### With Authentication

Provide IBM Cloud API key for authenticated servers:
```bash
python3 list_all_tools.py --apikey YOUR_IBM_CLOUD_API_KEY
```

Or use environment variable:
```bash
export IBM_CLOUD_API_KEY=your_api_key_here
python3 list_all_tools.py
```

### Output Formats

**Markdown format:**
```bash
python3 list_all_tools.py --format md
```

**JSON format:**
```bash
python3 list_all_tools.py --format json
```

**Save to file:**
```bash
python3 list_all_tools.py --format json -o tools.json
```

## Output Structure

The script generates output with the following structure:

```json
{
  "active": {
    "server-name": [
      {
        "name": "tool_name",
        "description": "Tool description"
      }
    ]
  },
  "deactivated": ["server-list"]
}
```

## Registered Servers

The `SERVERS` list in [`list_all_tools.py`](list_all_tools.py) is empty by default. Add your own servers before running the script. Two kinds are supported:

### OpenAPI-based Servers

Point to any publicly accessible OpenAPI JSON spec and define `custom_routes` to control which HTTP methods become tools:

```python
{
    "id": "my-openapi-server",
    "kind": "openapi",
    "spec_url": "https://example.com/openapi.json",
    "custom_routes": [
        {"methods": ["GET"], "pattern": ".*", "mcp_type": "TOOL"},
        {"methods": ["POST", "DELETE", "PUT", "PATCH"], "pattern": ".*", "mcp_type": "EXCLUDE"},
    ],
}
```

### HTTP MCP Servers

Point to any live MCP endpoint that speaks JSON-RPC:

```python
{
    "id": "my-mcp-server",
    "kind": "http_mcp",
    "endpoint": "https://your-server.example.com/mcp",
}
```

Alternatively, use `--use-db` to load server configurations dynamically from a PostgreSQL database.

## Bob Skills for Tool Audit

The `bob-skills/` folder contains comprehensive resources for performing detailed tool audits.

### Installation

**Important:** You must install the Bob skills to your local Bob skills directory before using them.

```bash
# Copy the tool-audit skill to your Bob skills directory
cp -r bob-skills ~/.bob/skills/tool-audit
```

**Verify the installation:**
```bash
ls ~/.bob/skills/tool-audit
# Should show: SKILL.md, README.md, QUICK-START.md, and other files
```

### Quick Start

1. **Install the skills** (see above)
2. Ensure you're in Bob's **Agent mode** (skills only work in Agent mode)
3. Generate tool definitions:
   ```bash
   python3 list_all_tools.py --format json -o tools.json
   ```
4. Ask Bob to audit your tools:
   ```
   "Audit the tool definitions in tools.json"
   ```
5. Review the generated report

### Available Documentation

- **[`SKILL.md`](bob-skills/SKILL.md)** - Main skill instructions and audit process
- **[`README.md`](bob-skills/README.md)** - Comprehensive skill documentation
- **[`QUICK-START.md`](bob-skills/QUICK-START.md)** - Quick start guide
- **[`analysis-techniques.md`](bob-skills/analysis-techniques.md)** - Detailed analysis methods
- **[`report-template.md`](bob-skills/report-template.md)** - Report structure template
- **[`quality-checklist.md`](bob-skills/quality-checklist.md)** - Quality assurance checklist
- **[`example-analysis.md`](bob-skills/example-analysis.md)** - Concrete example using the sample catalog

### What the Audit Detects

- 🔴 **Critical Issues**
  - Exact duplicate tool names within same server
  - Typos in descriptions
  - ERROR tools (authentication failures)
  
- 🟠 **High Priority Issues**
  - Cross-server duplicate names
  - Descriptions under 20 characters
  - Truncated names with "xxx" placeholders
  - Unexplained acronyms

- 🟡 **Medium Priority Issues**
  - Inconsistent naming patterns
  - Missing context in descriptions
  - Style inconsistencies

## Example Workflow

### Complete Setup and Audit Process

1. **Install Bob Skills (one-time setup):**
   ```bash
   cp -r bob-skills ~/.bob/skills/tool-audit
   ```

2. **Fetch tool definitions:**
   ```bash
   python3 list_all_tools.py --format json -o tools.json
   ```

3. **Audit with Bob:**
   - Open Bob in **Agent mode** (required for skills)
   - Say: "Audit the tool definitions in tools.json"
   - Review the generated report

4. **Implement recommendations:**
   - Fix critical issues (duplicates, typos)
   - Improve vague descriptions
   - Standardize naming conventions

5. **Re-audit:**
   - Run the audit again to verify improvements
   - Track progress over time

## Try It Without a Server

[`examples/`](examples/) contains a small, made-up catalog and an illustrative report, so you can see the input and output without access to any MCP server:

- [`examples/sample_tools.json`](examples/sample_tools.json) - ten tools on two fictional servers, in the same format `list_all_tools.py` produces. It includes a deliberate name collision, a pair of overlapping descriptions, and two vague descriptions.
- [`examples/sample_report.md`](examples/sample_report.md) - the kind of report the audit skill produces for that catalog.

To try it, install the Bob skills (see [Installation](#installation)), open Bob in Agent mode, and ask: "Audit the tool definitions in examples/sample_tools.json".

## Authentication

### Getting an IBM Cloud API Key

1. Log in to [IBM Cloud](https://cloud.ibm.com)
2. Navigate to **Manage** → **Access (IAM)** → **API keys**
3. Click **Create an IBM Cloud API key**
4. Copy the API key and store it securely
5. Add it to your `.env` file or pass via `--apikey` flag

### Why Authentication is Needed

Some MCP servers require authentication to access their tool definitions. Without authentication, these servers will return:
- `401 Unauthorized` errors
- `503 Service Unavailable` errors

The script will still work and list tools from public servers, but authenticated servers will show ERROR placeholders.

## Troubleshooting

### Issue: 401/503 Errors for Some Servers

**Solution:** Provide an IBM Cloud API key via `--apikey` flag or environment variable.

### Issue: JSON Parsing Error

**Solution:** Validate the output JSON using `jq` or an online validator:
```bash
python3 list_all_tools.py --format json | jq .
```

### Issue: Connection Timeout

**Solution:** Some servers may be slow to respond. The script has built-in timeouts (15-20 seconds). If issues persist, check your network connection.

### Issue: Empty Tool List

**Solution:** Verify that:
- The server endpoints are accessible
- Authentication is provided if required
- The server is not in the deactivated list

## Utilities

### `convert_to_csv.py`

Converts a `tools.json` output file into a CSV with columns `Server`, `Tool Name`, and `Description` — useful for sharing or reviewing tool inventories in a spreadsheet.

```bash
python3 list_all_tools.py --format json -o tools.json
python3 convert_to_csv.py   # produces tools.csv
```

## Contributing

To improve this toolkit:

1. **Add new servers** - Edit the `SERVERS` list in `list_all_tools.py`
2. **Enhance analysis** - Add techniques to `bob-skills/analysis-techniques.md`
3. **Improve templates** - Update `bob-skills/report-template.md`
4. **Share examples** - Add to `bob-skills/example-analysis.md`

## Best Practices

### For Tool Creators

1. **Use descriptive names**: `get_user_profile` not `get_user`
2. **Write detailed descriptions**: Minimum 40 characters
3. **Explain context**: What, why, and for whom
4. **Expand acronyms**: First use should spell out
5. **Follow conventions**: Consistent verb-noun-context pattern

### For Auditors

1. **Count accurately**: Always use programmatic counting
2. **Identify ERROR tools**: Exclude authentication placeholders
3. **Be thorough**: Analyze all tools
4. **Provide examples**: Show concrete before/after
5. **Prioritize issues**: Focus on critical problems first

## License

This toolkit is part of the MCP Composer project.

## Support

For questions or issues:
1. Check the `bob-skills/` documentation
2. Review example analyses
3. Consult the quality checklist
4. Open an issue on this repository

---

**Version**: 1.0.0
**Last Updated**: 2025-07-23
**Maintainer**: community contributor (open an issue on this repository)