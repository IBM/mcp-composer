# Catalog and Tool Tagging

The MCP Composer provides comprehensive tools for catalog generation and
security-focused tool tagging. The catalog serves as a single source of truth by
generating Backstage-compatible YAML descriptor files, while tool tagging
performs security scanning and compliance analysis of MCP tools.

## 📄 Catalog Generation

The Catalog generation feature connects to MCP servers and automatically generates
Backstage-compatible catalog files for tools, resources, and prompts. This enables
discoverability and accountability within the Backstage Internal Developer Portal.

### CLI Usage

#### Basic Catalog Generation

```bash
# Generate catalog from HTTP MCP server
mcp-composer catalog generate-catalog --mcp-url http://localhost:9000/mcp --outputdir ./catalog

# Generate catalog from HTTP (Streamable) MCP server
mcp-composer catalog generate-catalog --mcp-url http://localhost:8000/mcp --outputdir ./catalog

# Dry run to preview what would be generated
mcp-composer catalog generate-catalog --mcp-url http://localhost:9000/mcp --dry-run
```

#### Catalog Generation with MCP Scan Output

```bash
# Generate catalog with enhanced metadata from MCP scan results
mcp-composer catalog generate-catalog \
  --mcp-url http://localhost:9000/mcp \
  --mcp-scan-output ./scan-results.json \
  --outputdir ./catalog
```

### Command Options

- `--mcp-url, -u`: URL of the MCP server to generate catalog from
- `--mcp-scan-output`: Path to MCP-Scan output JSON file for enhanced metadata
- `--outputdir, -o`: Output directory for generated catalog files (default: ./catalog)
- `--dry-run`: Show what would be generated without creating files

### Input Examples

#### MCP Scan Output JSON Format

```json
{
  "reports": [
    {
      "tool": {
        "name": "activate-mcp-server",
        "description": "Reactivates a previously deactivated member server.",
        "input_schema": {
          "type": "object",
          "properties": {
            "server_id": {
              "type": "string",
              "description": "The ID of the server to activate"
            }
          },
          "required": ["server_id"]
        },
        "output_schema": {
          "type": "object",
          "properties": {
            "status": {
              "type": "string",
              "enum": ["success", "error"]
            },
            "message": {
              "type": "string"
            }
          }
        },
        "annotations": {
          "mcp_protocol": true,
          "server_name": "mcp-server",
          "server_version": "1.0.0",
          "transport": "http"
        },
        "vendor": "mcp-server",
        "endpoint": "http://localhost:9000/mcp",
        "scan_report": {
          "Level": "🟢 LOW",
          "Destructive": "❌ NO",
          "Private Data": "❌ NO",
          "Public Sink": "❌ NO"
        }
      },
      "capabilities": ["server-management"],
      "policy": {
        "pii_risk": "none",
        "hipaa": "none",
        "gdpr": "none",
        "residency": {
          "required_region": "global",
          "source_regions": [],
          "cross_border": false
        }
      }
    }
  ]
}
```

### Output Examples

#### Generated Backstage Component YAML

```yaml
apiVersion: backstage.io/v1alpha1
kind: Component
metadata:
  name: activate-mcp-server
  title: Activate MCP Server
  description: Reactivates a previously deactivated member server.
  tags:
    - mcp
    - tool
  annotations:
    backstage.io/managed-by-location: mcp-composer
    mcp-composer/component-type: tool
    mcp-composer/mcp_server: localhost-9000
    mcp-composer/mcp_url: http://localhost:9000/mcp
    mcp-composer/tool_name: activate-mcp-server
    mcp-composer/tool_description: Reactivates a previously deactivated member server.
    mcp-composer/input_schema: '{"type": "object", "properties": {"server_id": {"type": "string", "description": "The ID of the server to activate"}}, "required": ["server_id"]}'
    mcp-composer/output_schema: '{"type": "object", "properties": {"status": {"type": "string", "enum": ["success", "error"]}, "message": {"type": "string"}}}'
    mcp-composer/annotations/mcp_protocol: "true"
    mcp-composer/annotations/server_name: mcp-server
    mcp-composer/annotations/server_version: "1.0.0"
    mcp-composer/annotations/transport: http
    mcp-composer/scan_report/Level: "🟢 LOW"
    mcp-composer/scan_report/Destructive: "❌ NO"
    mcp-composer/scan_report/Private Data: "❌ NO"
    mcp-composer/scan_report/Public Sink: "❌ NO"
    mcp-composer/capabilities: '["server-management"]'
    mcp-composer/policy/pii_risk: none
    mcp-composer/policy/hipaa: none
    mcp-composer/policy/gdpr: none
    mcp-composer/policy/residency: '{"required_region": "global", "source_regions": [], "cross_border": false}'
  labels:
    mcp-server: localhost-9000
    component-type: tool
spec:
  type: tool
  owner: mcp
  system: mcp
  productName: localhost-9000
```

#### Combined Catalog File

The tool also generates a combined `catalog.yaml` file containing all components:

```yaml
apiVersion: backstage.io/v1alpha1
kind: Component
metadata:
  name: activate-mcp-server
  # ... component details ...
---
apiVersion: backstage.io/v1alpha1
kind: Component
metadata:
  name: deactivate-mcp-server
  # ... component details ...
---
# Additional components for resources and prompts...
```

#### Dry Run Output

When using `--dry-run`, the command shows a preview:

```text
🔍 Dry run results - would generate 15 components:
============================================================
📄 activate-mcp-server.yaml
   Title: Activate MCP Server
   Type: tool
   Owner: mcp
   System: mcp

📄 list-tools.yaml
   Title: List Tools
   Type: tool
   Owner: mcp
   System: mcp

📄 sample-resource.yaml
   Title: Sample Resource
   Type: resource
   Owner: mcp
   System: mcp
============================================================
📊 Summary: 15 components would be generated

📋 Sample component (activate-mcp-server):
apiVersion: backstage.io/v1alpha1
kind: Component
metadata:
  name: activate-mcp-server
  # ... full component YAML ...
```

## 🏷️ Tool Tagging

The MCP Tool Tagging process performs security-focused scanning of all tools
registered in an MCP environment. It automatically assigns compliance and risk
metadata tags based on tool functionality, code analysis, and data handling
patterns. The system includes Tool Poisoning Attack detection to identify hidden
malicious instructions in tool descriptions or schemas.

### Tool Tagging CLI Usage

#### Generate Tool Tags from Different Sources

```bash
# Tag tools from JSON file
mcp-composer tag generate-tag --from-json ./tool-descriptors.json --output results.json

# Tag tools from live MCP endpoint (HTTP transport)
mcp-composer tag generate-tag \
  --mcp-endpoint http://localhost:9000 \
  --mcp-transport http \
  --output results.json

# Tag tools from live MCP endpoint (HTTP transport)
mcp-composer tag generate-tag \
  --mcp-endpoint http://localhost:8000/mcp \
  --mcp-transport http \
  --output results.json

# Tag tools using stdio transport
mcp-composer tag generate-tag \
  --mcp-transport stdio \
  --command python \
  --args "-m my_mcp_server" \
  --output results.json

# Tag tools from MCP-Scan output
mcp-composer tag generate-tag \
  --mcp-scan-output ./scan-results.json \
  --output results.json

# Tag tools with custom rules file
mcp-composer tag generate-tag \
  --mcp-endpoint http://localhost:9000 \
  --mcp-transport http \
  --rules ./custom-rules.yaml \
  --output results.json

# Tag tools with authentication
mcp-composer tag generate-tag \
  --mcp-endpoint http://localhost:9000 \
  --mcp-transport http \
  --mcp-auth-token "your-token-here" \
  --output results.json
```

### Tool Tagging Command Options

- `--from-json`: Path to JSON file containing tool descriptors
- `--mcp-endpoint`: Live MCP endpoint URL
- `--mcp-auth-token`: Authorization token for MCP endpoint
- `--mcp-transport`: Transport type (http, stdio)
- `--command`: Command for stdio transport
- `--args`: Arguments for the stdio command
- `--mcp-scan-output`: Path to MCP-Scan output JSON
- `--rules`: Rules YAML file (default: rules/rules_default.yaml)
- `--policy`: Policy YAML file (optional)
- `--output`: Output path for results JSON

### Policy Checking

After generating tags, you can check tools against policy requirements:

```bash
# Check if tools pass policy gates
mcp-composer tag check \
  --report ./results.json \
  --require "pii_risk == 'none'" \
  --require "hipaa == 'none'"
```

### Export to Backstage

Export tagged results to Backstage-compatible format:

```bash
# Export to Backstage catalog format
mcp-composer tag export backstage \
  --report ./results.json \
  --out ./backstage-entities/
```

### Tool Tagging Input Examples

#### JSON Tool Descriptors File

```json
[
  {
    "id": "database_query",
    "name": "database_query",
    "description": "Execute SQL queries against the database",
    "input_schema": {
      "type": "object",
      "properties": {
        "query": {
          "type": "string",
          "description": "SQL query to execute"
        },
        "parameters": {
          "type": "object",
          "description": "Query parameters"
        }
      },
      "required": ["query"]
    },
    "output_schema": {
      "type": "object",
      "properties": {
        "results": {
          "type": "array",
          "items": {
            "type": "object"
          }
        },
        "row_count": {
          "type": "integer"
        }
      }
    },
    "annotations": {
      "vendor": "database-vendor",
      "version": "1.0.0"
    }
  }
]
```

#### MCP-Scan Output Format

```json
{
  "servers": [
    {
      "endpoint": "http://localhost:9000/mcp",
      "tools": [
        {
          "name": "get_user_data",
          "description": "Retrieve user information from database",
          "inputSchema": {
            "type": "object",
            "properties": {
              "user_id": {
                "type": "string"
              }
            }
          },
          "outputSchema": {
            "type": "object",
            "properties": {
              "user": {
                "type": "object",
                "properties": {
                  "id": "string",
                  "name": "string",
                  "email": "string"
                }
              }
            }
          },
          "annotations": {
            "server_name": "user-service",
            "transport": "http"
          }
        }
      ]
    }
  ]
}
```

### Tool Tagging Output Examples

#### Tool Tagging Results JSON

```json
{
  "reports": [
    {
      "tool": {
        "id": "database_query",
        "name": "database_query",
        "description": "Execute SQL queries against the database",
        "input_schema": {
          "type": "object",
          "properties": {
            "query": {
              "type": "string",
              "description": "SQL query to execute"
            },
            "parameters": {
              "type": "object",
              "description": "Query parameters"
            }
          },
          "required": ["query"]
        },
        "output_schema": {
          "type": "object",
          "properties": {
            "results": {
              "type": "array",
              "items": {
                "type": "object"
              }
            },
            "row_count": {
              "type": "integer"
            }
          }
        },
        "annotations": {
          "vendor": "database-vendor",
          "version": "1.0.0"
        },
        "endpoint": "http://localhost:9000/mcp",
        "scan_report": {
          "Level": "🟡 MEDIUM",
          "Destructive": "🔴 CRITICAL (Database Write Operation)",
          "Private Data": "✅ YES (Database Read Operation)",
          "Public Sink": "❌ NO"
        }
      },
      "capabilities": [
        "data-access",
        "query-execution"
      ],
      "policy": {
        "pii_risk": "high",
        "hipaa": "potential",
        "gdpr": "potential",
        "residency": {
          "required_region": "us-east-1",
          "source_regions": ["us-east-1", "eu-west-1"],
          "cross_border": true
        }
      },
      "evidence": {
        "description_keywords": ["database", "query", "execute"],
        "input_schema_analysis": "Contains SQL query parameter",
        "output_schema_analysis": "Returns potentially sensitive data arrays"
      }
    },
    {
      "tool": {
        "id": "send_email",
        "name": "send_email",
        "description": "Send notification emails to users",
        "input_schema": {
          "type": "object",
          "properties": {
            "to": {
              "type": "string",
              "format": "email"
            },
            "subject": {
              "type": "string"
            },
            "body": {
              "type": "string"
            }
          }
        },
        "output_schema": {
          "type": "object",
          "properties": {
            "message_id": {
              "type": "string"
            },
            "status": {
              "type": "string",
              "enum": ["sent", "failed"]
            }
          }
        },
        "scan_report": {
          "Level": "🟠 HIGH",
          "Destructive": "❌ NO",
          "Private Data": "❌ NO",
          "Public Sink": "✅ YES (External Email Transmission)"
        }
      },
      "capabilities": [
        "communication",
        "notification"
      ],
      "policy": {
        "pii_risk": "medium",
        "hipaa": "none",
        "gdpr": "potential",
        "residency": {
          "required_region": "global",
          "source_regions": [],
          "cross_border": false
        }
      },
      "evidence": {
        "description_keywords": ["email", "send", "notification"],
        "public_sink_detected": "Email transmission capability"
      }
    }
  ]
}
```

#### Policy Check Results

```text
[green]Policy gate passed[/green]
```

or

```text
[red]Policy gate failed:[/red] ['pii_risk == "none"', 'hipaa == "none"']
```

#### Backstage Export Output

The export command generates individual YAML files for each tagged tool in Backstage format, similar to the catalog generation output but focused on security and compliance metadata.

## 🔄 Integration Workflow

A typical workflow combines both catalog generation and tool tagging:

1. **Scan and Tag Tools**: Use `tag generate-tag` to analyze tools for security and compliance
2. **Check Policies**: Use `tag check` to validate tools against organizational policies
3. **Generate Catalog**: Use `catalog generate-catalog` with scan output to create Backstage entities
4. **Export to Backstage**: Use `tag export backstage` for additional security-focused catalog entries

This integrated approach ensures that your Backstage catalog contains both functional metadata and security/compliance information for comprehensive governance.
