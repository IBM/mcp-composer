# MCPTag - MCP Security Scanning and Tool Tagging Tool

MCPTag provides comprehensive security scanning and compliance analysis for Model Context Protocol (MCP) servers and tools.

## Features

- **MCP Server Connection**: Connect to live MCP servers and extract tool information
- **Tool Discovery**: Automatically discover and catalog available tools from MCP servers
- **Compliance Analysis**: Apply rules to tag tools for compliance (GDPR, HIPAA, etc.)
- **Policy Gating**: Enforce security policies and compliance requirements
- **Export Support**: Export results to various backends (Backstage, etc.)

## Quick Start

### 1. Connect to an MCP Server and Extract Tools

```bash
# install mcp-composer
pip install mcp-composer

# MCP tools tag list of options
mcp-composer tag --help


# Basic connection to MCP server
mcp-composer tag --mcp-endpoint http://localhost:8000

# With authentication
mcp-composer tag --mcp-endpoint http://localhost:8000 --mcp-auth-token "your-token"

# Specify transport type (http or sse)
mcp-composer tag --mcp-endpoint http://localhost:8000 --mcp-transport sse
```

### 2. Apply Custom Rules

```bash
# Use custom rules file
mcp-composer tag --mcp-endpoint http://localhost:8000 --rules my-rules.yaml

# Save results to file
mcp-composer tag --mcp-endpoint http://localhost:8000 --rules my-rules.yaml --out results.json
```

## Tool Discovery

MCPTag automatically discovers tools from MCP servers by:

1. **Protocol Endpoints**: Trying standard MCP protocol endpoints
2. **Server Info**: Extracting tool information from server metadata
3. **Fallback Discovery**: Using basic discovery when protocol methods fail

### Supported Tool Formats

- Standard MCP tool descriptors
- Custom tool schemas
- Server capabilities converted to tools
- Fallback tool information

## Rules and Tagging

Create YAML rule files to automatically tag tools:

```yaml
rules:
  # Capability detection
  - name: data_access_tools
    when:
      desc_regex: "\b(api|data|file|database)\b"
    then:
      add_capabilities: ["cap:data_access"]

  # Compliance tagging
  - name: gdpr_tools
    when:
      desc_regex: "\b(gdpr|export|erasure|data subject)\b"
    then:
      policy:
        gdpr: data-subject

  # PII detection
  - name: pii_tools
    when:
      input_jsonpath:
        expr: "$..[?(@.format=='email')]"
    then:
      policy:
        pii_risk: medium
```

### Common Issues

1. **Connection Failed**
   - Verify the MCP server is running
   - Check the endpoint URL is correct
   - Ensure the server supports the MCP protocol

2. **Authentication Errors**
   - Verify your auth token is valid
   - Check if the token has expired
   - Ensure the token has the required permissions

3. **No Tools Found**
   - The server might not expose tools via standard endpoints
   - Check server logs for any errors
   - Try different transport types (http vs sse)