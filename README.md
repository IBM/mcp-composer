<div align="center">

<!-- omit in toc -->

# MCP Composer

</div>

---

<!-- omit in toc -->

## Table of Contents

- [Overview](#overview)
- [Purpose](#purpose)
- [Installation](#installation)
  - [Prerequisites](#prerequisites)
  - [Setup](#setup)
  - [Use as Tool](#use-as-tool)
- [Development with Makefile](#development-with-makefile)
- [Usage](#usage)
- [Key Features](#key-features)
  - [MCP Composer Servers](#mcp-composer-servers)
  - [Command Line Interface (CLI)](#command-line-interface-cli)
  - [MCP Composer Tools](#mcp-composer-tools)
  - [MCP Composer Prompts](#mcp-composer-prompts)
- [Demo using MCP Inspector](#demo-using-mcp-inspector)
- [MCP Composer Client with Chatbot UI](#mcp-composer-client-with-chatbot-ui)

---

## Overview

The MCP Composer is a [FastMCP](https://github.com/jlowin/fastmcp) based Composer that manages multiple MCP servers and tools.
Servers and tools can be registered at runtime using structured JSON configurations.
The MCP Composer serves as an orchestrator for tool execution and forwards tool requests to the correct upstream MCP server or interface.

The MCP Composer supports multiple tool types, such as OpenAPI (REST), GraphQL, CLI-based tools, client SDKs, and nested MCP servers.

## Purpose

The goal of the MCP Composer is to handle dynamic tool registration, authentication, invocation dispatching, and health monitoring.
It abstracts underlying protocol, authentication and routing complexities,
and allows tools to be called through a single, unified interface. The MCP Composer exposes a set of MCP-compliant functions that allow listing tools, invoking them, updating credentials, and removing them.

The goal is to provide a single unified MCP Composer that:

- Discovers and registers new MCP tools on startup or via API.
- Mounts and unmounts member servers dynamically.
- Exposes all tools across registered servers.

## Installation

Update the pyproject.toml if you need to install both `mcp_composer` and `mcp_composer_app`

```
[tool.setuptools.packages.find]
where = ["src"]
include = ["mcp_composer", "mcp_composer_app"]
```

If we only want to install `mcp_composer`

```
[tool.setuptools.packages.find]
where = ["src"]
include = ["mcp_composer"]
```

For multiple installation methods, please refer to the [**Installation Guide**](https://ibm.github.io/mcp-composer/guide/installation.html)

### Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (Recommended for environment management)

### Setup

1. Clone the repository

   ```bash
   git clone https://github.com/IBM/mcp-composer.git
   cd mcp-composer
   ```

2. Create virtual Environment:

   ```bash
   uv venv 
   ```

3. Activate the virtual environment.

   ```bash
   source .venv/bin/activate
   ```

4. **Environment Configuration (Required)**

   The MCP Composer requires environment variables to be set:

   **Setup**

   ```bash
   cp env.example .env
   ```

   Edit the `.env` file and set the required environment variables:
   - `SERVER_CONFIG_FILE_PATH`: Path to the server configuration file (default: `member_servers.json`)

   **Note**: If you don't set up the `.env` file, you'll get a `KeyError: 'SERVER_CONFIG_FILE_PATH'` error when trying to import the module.

5. **Database Configuration (Optional)**

   The MCP Composer supports multiple database backends for storing server configurations, tools, prompts, and resources:

   **Default Behavior**: If no database configuration is provided, MCP Composer runs without persistent storage (no database).

   **Environment Variable Configuration (Recommended)**:

   You can configure the database using environment variables, which take priority over programmatic configuration:

   ```bash
   # For Cloudant database
   export MCP_DATABASE_TYPE="cloudant"
   export MCP_DATABASE_API_KEY="your_cloudant_api_key"
   export MCP_DATABASE_SERVICE_URL="https://your-cloudant-instance.cloudantnosqldb.appdomain.cloud"
   export MCP_DATABASE_DB_NAME="mcp_servers"  # Optional, defaults to "mcp_servers"
   
   # For local file storage
   export MCP_DATABASE_TYPE="local_file"
   export MCP_DATABASE_FILE_PATH="/path/to/your/servers.json"  # Optional
   
   # Enable local file storage when no other database config is provided
   export MCP_USE_LOCAL_FILE_STORAGE="true"
   ```

   [**Environment Variables**](https://ibm.github.io/mcp-composer/guide/configuration.html#environment-variables):
   - `MCP_DATABASE_TYPE`: Database type (`"cloudant"` or `"local_file"`)
   - `MCP_DATABASE_API_KEY`: API key for Cloudant (required for cloudant type)
   - `MCP_DATABASE_SERVICE_URL`: Service URL for Cloudant (required for cloudant type)
   - `MCP_DATABASE_DB_NAME`: Database name (optional, defaults to `"mcp_servers"`)
   - `MCP_DATABASE_FILE_PATH`: File path for local storage (optional for local_file type)
   - `MCP_USE_LOCAL_FILE_STORAGE`: Set to `"true"` to enable local file storage when no other config is provided

   **Programmatic Database Configuration**:

   You can also provide a `database_config` dictionary when initializing MCPComposer:

   ```python
   from mcp_composer import MCPComposer
   
   # Cloudant configuration
   database_config = {
       "type": "cloudant",
       "api_key": "your_cloudant_api_key",
       "service_url": "https://your-cloudant-instance.cloudantnosqldb.appdomain.cloud",
       "db_name": "mcp_servers"  # Optional, defaults to "mcp_servers"
   }
   
   composer = MCPComposer(
       name="my-composer",
       database_config=database_config
   )
   ```

   **Local File Storage Configuration**:

   ```python
   from mcp_composer import MCPComposer
   
   # Local file storage configuration
   database_config = {
       "type": "local_file",
       "file_path": "/path/to/your/servers.json"  # Optional
   }
   
   composer = MCPComposer(
       name="my-composer",
       database_config=database_config
   )
   ```

   **Required Cloudant Parameters**:
   - `type`: Must be set to `"cloudant"`
   - `api_key`: Your IBM Cloudant API key
   - `service_url`: Your Cloudant service URL (must start with `http://` or `https://`)

   **Optional Cloudant Parameters**:
   - `db_name`: Database name (defaults to `"mcp_servers"`)

   **Custom Database Interface**:

   You can also provide a custom database implementation by passing a `DatabaseInterface` instance:

   ```python
   from mcp_composer.store.database import DatabaseInterface
   
   class MyCustomDatabase(DatabaseInterface):
       # Implement required methods
       pass
   
   custom_db = MyCustomDatabase()
   composer = MCPComposer(
       name="my-composer",
       database_config=custom_db
   )
   ```

   **Configuration Priority**:
   1. Environment variables (highest priority)
   2. Programmatic configuration
   3. No database (default behavior)

   **Error Handling**: If database configuration is provided but missing required keys or has invalid values, the composer will log warnings and fall back to no database configuration.

6. Synchronize the environment.

   **First time setup**: Run this to create the initial `uv.lock` file:

   ```bash
   uv sync
   ```

   **Subsequent runs**: Use the frozen lock file for consistency:

   ```bash
   uv sync --frozen        # Strict install (uses lock file exactly) - recommended as ensuring consistency across different environments
   ```

   **Update dependencies**: If you need to update dependencies:

   ```bash
   rm uv.lock && uv sync # Refresh child dependencies, commit uv.lock
   ```

7. Add a new dependency; automatically creates a virtual environment if necessary

   ```bash
   uv add <my-package>   
   ```

8. Leverage the project's virtual environment:

   ```
   uv run <command&args> 
   ```

9. Test if MCP Composer is installed successfully or not

   ```bash
   uv run python -c "import mcp_composer; print(mcp_composer.__version__)"
   ```

### Add MCP Composer as local dependency

1. Update the `pyproject.toml` with the following:

```toml
[tool.hatch.metadata]
allow-direct-references = true
```

Then you can run the command:

```bash
uv add <path to mcp-composer folder>
```

Then, the pyproject.toml file is updated with the below lines:

```toml
[tool.uv.sources]
mcp-composer = { path = "mcp-composer" }
```

Add mcp-composer to the dependencies section, example of the final pyproject.toml file:

```toml  
[project]
name = "py_project"

[tool.hatch.metadata]
allow-direct-references = true

dependencies = [
    "mcp-composer",
    ... ...
]

[tool.uv.sources]
mcp-composer= { path = "mcp-composer" }
```

To ensure the package is properly installed and importable in the consumer project, the following command must be run manually:

```bash
uv pip install -e ../mcp-composer
```

### Use as Tool

#### Install mcp-composer as a tool

1. Run the following command to install mcp-composer as a tool:

   ```bash:
   uv tool install -e /<absolute path>/mcp-composer 
   ```

2. Add the tool to $PATH:

   ```bash  
      export PATH="/<absolute path>/.local/bin:$PATH"
   ```

3. Check the installation:

   ```bash
   which mcp-composer
   ```

#### Uninstall mcp-composer as a tool

1. Run the following command to uninstall mcp-composer as a tool:

   ```bash:
   uv tool uninstall mcp-composer
   ```

## Development with Makefile

The MCP Composer project includes a comprehensive Makefile that provides convenient commands for development tasks, quality assurance, and package management.

### [Quick Start](https://ibm.github.io/mcp-composer/guide/quick-start.html#quick-start)

Run all quality assurance checks in sequence:

```bash
make all
```

### Development Tasks

#### Code Quality

- **`make format`** - Format code with black
- **`make lint`** - Lint code with ruff
- **`make type-check`** - Run type checks with mypy
- **`make test`** - Run tests with coverage
- **`make coverage`** - Generate coverage report
- **`make check`** - Run all checks in sequence

#### Module Testing

- **`make test-module module=<module_name>`** - Run unit tests for a specific module
- **`make test-modules`** - Run unit tests for all modules

#### Cleanup

- **`make clean`** - Clean up generated files and caches

### PyPI Release Management

#### Build and Release

- **`make build module=<module_name> version=<x.y.z>`** - Build wheel for a specific module
- **`make check-release module=<module_name> version=<x.y.z>`** - Verify wheel with twine
- **`make upload-testpypi module=<module_name> version=<x.y.z>`** - Upload to TestPyPI
- **`make upload-pypi module=<module_name> version=<x.y.z>`** - Upload to PyPI

#### Environment Status

- **`make status`** - Show environment status for releases

### Examples

```bash
# Run all QA checks
make all

# Test a specific module
make test-module module=mcp_composer

# Build a module for release
make build module=mcp_composer version=1.0.0

# Check release artifacts
make check-release module=mcp_composer version=1.0.0

# Upload to TestPyPI
make upload-testpypi module=mcp_composer version=1.0.0

# Clean up development artifacts
make clean
```

### Prerequisites for Releases

For PyPI uploads, you'll need to set environment variables:

```bash
# For TestPyPI
export TEST_TWINE_USERNAME="your_test_username"
export TEST_TWINE_PASSWORD="your_test_password"

# For PyPI
export TWINE_USERNAME="your_username"
export TWINE_PASSWORD="your_p   assword"
```

For more detailed information about available commands, run:

```bash
make help
```

## [Usage](https://ibm.github.io/mcp-composer/guide/use-with-claude.html)

1. Run MCP Server using MCP Composer Tool with oauth authentication with following command

```bash

uvx mcp-composer -sseurl --sse-url <url to remote sse mcp server> --auth_type oauth --env OAUTH_HOST <host> --env OAUTH_PORT <port> --env OAUTH_SERVER_URL <server url> --env OAUTH_CALLBACK_PATH <callback path> --env OAUTH_CLIENT_ID=<client id> --env OAUTH_CLIENT_SECRET <secret> --env OAUTH_AUTH_URL <auth url> -e-env OAUTH_TOKEN_URL <token url> --env OAUTH_MCP_SCOPE user --env OAUTH_PROVIDER_SCOPE=openid
```

## Key Features

- Register or remove tools at runtime using structured JSON configurations.
- Support a range of tool types (openapi, graphql, client, mcp, etc.)
- Handles multiple authentication strategies.
- Automatically forwards each request to the correct upstream server or tool.
- List tools and metadata by name or server.
- **Database Support**: Configurable database backends including IBM Cloudant and local file storage for persistent server configurations, tools, prompts, and resources.
- **Environment Variable Configuration**: Database configuration through environment variables with validation and fallback support.
- **Database Configuration Validation**: Strict validation of database configuration with fail-fast behavior to prevent startup with invalid database settings.

### MCP Composer Servers

#### Add MCP Server from local python file in stdio

To add an MCP server from a local python file, use the builder with a configuration containing the python file path:

**Example:**

```
[
  {
    "id": "mcp-local-news",
    "type": "stdio",
    "command": "uv",
    "args": [
      "--directory",
      "/<absolute path of the directory>",
      "run",
      "<name of the python file>.py"
    ],
    "_id": "mcp-local-news"
  }
]
```

Run

```bash
uv run test/test_composer.py
```

test_composer.py can run on either `stdio` or `http` type.
This will create a FastMCP server instance using the python file and its dependencies and also mount it on mcp-composer.

#### Add MCP Server from OpenAPI Specification

To add an MCP server from an OpenAPI spec, use the builder with a configuration containing the OpenAPI details:

**Example:**

```python
from mcp_composer.member_servers.builder import MCPServerBuilder

config = {
    "id": "my-openapi-server",
    "type": "openapi",
    "open_api": {
        "endpoint": "https://api.example.com",
        "spec_url": "https://api.example.com/openapi.json",
        # Optional: "custom_routes": "path/to/custom_routes.json"
    },
    "auth_strategy": "bearer",
    "auth": {
        "token": "your-token"
    }
}
builder = MCPServerBuilder(config)
mcp_server = await builder.build()
```

This will create a FastMCP server instance using the OpenAPI specification and authentication details provided.

---

#### Add MCP Server from GraphQL Schema

To add an MCP server from a GraphQL schema, use the builder with a configuration containing the GraphQL endpoint:

**Example:**

```python
from mcp_composer.member_servers.builder import MCPServerBuilder

config = {
    "id": "my-graphql-server",
    "type": "graphql",
    "endpoint": "https://graphql.example.com/graphql",
    # Add any other required config options
}
builder = MCPServerBuilder(config)
mcp_server = await builder.build()
```

This will create a FastMCP server instance with a GraphQL tool registered, allowing you to interact with the GraphQL API through MCP Composer.

#### Database Configuration for Server Management

When initializing MCPComposer, you can configure the database backend for persistent storage of server configurations:

**Example with Environment Variables (Recommended)**:

```bash
# Set environment variables
export MCP_DATABASE_TYPE="cloudant"
export MCP_DATABASE_API_KEY="your_cloudant_api_key"
export MCP_DATABASE_SERVICE_URL="https://your-cloudant-instance.cloudantnosqldb.appdomain.cloud"
export MCP_DATABASE_DB_NAME="mcp_servers"
```

```python
from mcp_composer import MCPComposer

# Initialize composer - database config will be loaded from environment variables
composer = MCPComposer(name="my-composer")

# Server configurations will be automatically persisted to Cloudant
await composer.setup_member_servers()
```

**Example with Programmatic Cloudant Configuration**:

```python
from mcp_composer import MCPComposer

# Configure Cloudant database programmatically
database_config = {
    "type": "cloudant",
    "api_key": "your_cloudant_api_key",
    "service_url": "https://your-cloudant-instance.cloudantnosqldb.appdomain.cloud",
    "db_name": "mcp_servers"  # Optional
}

# Initialize composer with database configuration
composer = MCPComposer(
    name="my-composer",
    database_config=database_config
)

# Server configurations will be automatically persisted to Cloudant
await composer.setup_member_servers()
```

**Example with Local File Storage**:

```bash
# Option 1: Using environment variables
export MCP_DATABASE_TYPE="local_file"
export MCP_DATABASE_FILE_PATH="/path/to/servers.json"

# Option 2: Enable local file storage when no other config is provided
export MCP_USE_LOCAL_FILE_STORAGE="true"
```

```python
from mcp_composer import MCPComposer

# Option 1: Environment variables will be used automatically
composer = MCPComposer(name="my-composer")

# Option 2: Programmatic configuration
database_config = {
    "type": "local_file",
    "file_path": "/path/to/servers.json"  # Optional
}

composer = MCPComposer(
    name="my-composer",
    database_config=database_config
)

# Server configurations will be stored locally
await composer.setup_member_servers()
```

**Example with No Database (Default)**:

```python
from mcp_composer import MCPComposer

# No database configuration - runs without persistent storage
composer = MCPComposer(name="my-composer")

# Server configurations will not be persisted
await composer.setup_member_servers()
```

**Benefits of Database Configuration**:

- **Persistence**: Server configurations, tools, prompts, and resources are saved across restarts
- **Scalability**: Cloudant provides distributed storage for multi-instance deployments
- **Management**: Tools for enabling/disabling tools, prompts, and resources per server
- **Versioning**: Support for configuration versioning and rollback capabilities

### Command Line Interface (CLI)

MCP Composer can now be launched directly via a CLI using the `mcp-composer` entry point. This provides a lightweight and flexible way to spin up the composer using either HTTP or stdio mode.

#### Usage

```bash
mcp-composer --mode <http|stdio> [--host HOST] [--port PORT] [--log-level LEVEL] [--path PATH] [--config <config.json>]
```

#### Options

| Flag          | Description                                         | Default      |
| ------------- | --------------------------------------------------- | ------------ |
| `--mode`      | Mode to run the Composer in: `http` or `stdio`      | `http`       |
| `--host`      | Host to bind to (for `http` mode)                   | `0.0.0.0`    |
| `--port`      | Port to run on (for `http` mode)                    | `9000`       |
| `--log-level` | Log level (e.g. `debug`, `info`, `warning`)         | `debug`      |
| `--path`      | URL path to mount the MCP Composer on               | `/mcp`       |

### MCP Composer Tools

#### [Server Management Tools](https://ibm.github.io/mcp-composer/guide/tool-management.html#tool-management)

- `register_mcp_server`: Register a single server.
- `delete_mcp_server`: Delete a single server.
- `member_health`: Get status for all member servers.
- `activate_mcp_server`: Reactivates a previously deactivated member server by loading its config, updating status in DB, and mounting it.
- `deactivate_mcp_server`: Deactivates a member server by unmounting it and marking it as deactivated in DB.
- `list_member_servers`: List status of all member servers (active or deactivated).

#### [Tool Management Tools](https://ibm.github.io/mcp-composer/guide/tool-management.html)

- `get_tool_config_by_name`: Get a tool configuration details
- `get_tool_config_by_server`: Get all tool configuration details of a specific member server
- `disable_tools`: Disable a tool or multiple from the servers and Composer
- `enable_tools`: Enable a tool or multiple from the servers and Composer
- `update_tool_description`: Update tool description of member servers
- [add_tools](#add-tool-using-curl-command-and-python-script): Add tool using curl command or Python script.
- [add_tools_from_openapi](#add-tool-using-openapi-specification): Add tool using the OpenAPI specifications

#### [Prompt Management Tools](https://ibm.github.io/mcp-composer/guide/prompt-management.html#_1-prompt-management-tools)

- `add_prompts`: Add one or more prompts to the composer
- `get_all_prompts`: Get all registered prompts as JSON strings (excluding disabled ones)
- `list_prompts_per_server`: List all prompts from a specific server (excluding disabled ones)
- `filter_prompts`: Filter prompts based on criteria like name, description, tags
- `enable_prompts`: Enable prompts from a specific server
- `disable_prompts`: Disable prompts from a specific server

#### [Resource Management Tools](https://ibm.github.io/mcp-composer/guide/resource-management.html#_1-resource-management-tools)

- `add_resource_template`: Add a resource template to the composer
- `create_resource`: Create a new resource in the composer
- `list_resources`: List all available resources (actual resources)
- `list_resource_templates`: List all available resource templates
- `list_resources_per_server`: List all resources and templates from a specific server
- `filter_resources`: Filter resources based on criteria like name, description, tags
- `enable_resources`: Enable resources or templates from a specific server
- `disable_resources`: Disable resources or templates from a specific server

#### [Add tool using Curl command and Python script](https://ibm.github.io/mcp-composer/guide/tool-management.html#_1-%F0%9F%A7%A9-using-a-curl-command)

**Curl command:**

```JSON
{
    "name": "event",
    "tool_type": "curl",
    "curl_config": {
        "value": "curl 'https://www.eventbriteapi.com/v3/users/me/organizations/' --header 'Authorization: Bearer XXXXXXXX'"
    },
    "description": "sample test",
    "permission": {
        "role 1": "permission 1 "
    }
}
```

**Python script:**

```python
{
  "name": "test",
  "tool_type": "script",
  "script_config": {
    "value": "def search_news(keyword: str) -> str:\n    '''Simulate news search using a ticker and return top articles.'''\n    import yfinance as yf\n    import json\n    stock = yf.Ticker(keyword.upper())\n    news = stock.news[:5]\n    result = []\n    for article in news:\n        result.append({\n            'title': article.get('title'),\n            'publisher': article.get('publisher'),\n            'link': article.get('link'),\n            'providerPublishTime': article.get('providerPublishTime'),\n        })\n    return json.dumps(result, indent=2)"
  },
  "description": "Search top 5 news articles related to a stock ticker using yfinance.",
  "permission": {
    "role 1": "permission 1"
  }
}
```

#### [Add tool using OpenAPI specification](https://ibm.github.io/mcp-composer/guide/tool-management.html#_3-%F0%9F%93%98-using-openapi-specification)

**input: openapi_spec**

```JSON
{
  "openapi": "3.0.1",
  "info": {
    "title": "IBM Concert API v1.1.0",
    "version": "1.1.0",
    ...
    ...
  }
}
```

**input: auth_config**

```JSON
{
  "auth_strategy": "basic",
  "auth": {
    "username": "user1",
    "password": "xxxxxxxx"
  }
}
```

### [MCP Composer Prompts](https://ibm.github.io/mcp-composer/guide/prompt-management.html)

#### [Adding one or more prompts](https://ibm.github.io/mcp-composer/guide/prompt-management.html#adding-prompts)

- `add_prompts(prompt_config: list[dict]) -> list[str]`
  Registers one or more prompts with the composer.

- **Arguments**:
  - `prompt_config`: A list of dictionaries, each describing a prompt. Each dictionary should contain at least a `name`, `description`, and `template` field.
- **Returns**: A list of registered prompt names.

**Example:**

```python
prompt_config = [
    {
        "name": "promo_http_avg_response",
        "description": "Average response time of promo HTTP calls handled by a cluster",
        "template": "What is the average response time of promo HTTP calls handled by Kubernetes cluster {{ cluster }}?",
        "arguments": [
            {
                "name": "cluster",
                "type": "string",
                "required": true,
                "description": "The name of the Kubernetes cluster"
            }
        ]
    }
]
added = await composer.add_prompts(prompt_config)
```

#### [Get all Prompts](https://ibm.github.io/mcp-composer/guide/prompt-management.html#get-all-prompts)

- `get_all_prompts() -> list[str]`
  Retrieves all registered prompts as JSON strings, with internal function references stripped.

- **Returns**: A list of JSON strings, each representing a prompt (excluding the `fn` field).

**Example:**

```python
prompts = await composer.get_all_prompts()
for prompt_json in prompts:
    print(prompt_json)
```

#### [List Prompts per Server](https://ibm.github.io/mcp-composer/guide/prompt-management.html#list-prompts-per-server)

- `list_prompts_per_server(server_id: str) -> list[dict]`
  Lists all prompts from a specific server (excluding disabled ones).

- **Arguments**:
  - `server_id`: The ID of the server to list prompts from.
- **Returns**: A list of dictionaries containing prompt information with server_id included.

**Example:**

```python
prompts = await composer.list_prompts_per_server("my-server")
for prompt in prompts:
    print(f"Prompt: {prompt['name']} from server: {prompt['server_id']}")
    print(f"  Description: {prompt['description']}")
    print(f"  Template: {prompt['template']}")
```

#### [Enable Prompts](https://ibm.github.io/mcp-composer/guide/prompt-management.html#enabling-and-disabling-prompts)

- `enable_prompts(prompts: list[str], server_id: str) -> str`
  Enables prompts from a specific server.

- **Arguments**:
  - `prompts`: A list of prompt names to enable.
  - `server_id`: The ID of the server containing the prompts.
- **Returns**: A status message indicating success or failure.

**Example:**

```python
result = await composer.enable_prompts(["app_top_errors_yesterday"], "mcp-prompt")
print(result)  # "Enabled ['mcp-prompt_app_top_errors_yesterday'] prompts from server mcp-prompt"
```

#### [Disable Prompts](https://ibm.github.io/mcp-composer/guide/prompt-management.html#enabling-and-disabling-prompts)

- `disable_prompts(prompts: list[str], server_id: str) -> str`
  Disables prompts from a specific server.

- **Arguments**:
  - `prompts`: A list of prompt names to disable.
  - `server_id`: The ID of the server containing the prompts.
- **Returns**: A status message indicating success or failure.

**Example:**

```python
result = await composer.disable_prompts(["app_top_errors_yesterday"], "mcp-prompt")
print(result)  # "Disabled ['mcp-prompt_app_top_errors_yesterday'] prompts from server mcp-prompt"
```

#### [Filter Prompts](https://ibm.github.io/mcp-composer/guide/prompt-management.html#filter-prompts)

- `filter_prompts(filter_criteria: dict) -> list[dict]`
  Filters prompts based on criteria like name, description, tags, etc.

- **Arguments**:
  - `filter_criteria`: A dictionary containing filter criteria (name, description, tags).
- **Returns**: A list of dictionaries containing matching prompts.

**Example:**

```python
# Filter by name
result = await composer.filter_prompts({"name": "test"})

# Filter by description
result = await composer.filter_prompts({"description": "response"})

# Filter by multiple criteria
result = await composer.filter_prompts({
    "name": "prompt",
    "description": "test"
})
```

### [MCP Composer Resources](https://ibm.github.io/mcp-composer/guide/resource-management.html)

#### [Adding resource templates](https://ibm.github.io/mcp-composer/guide/resource-management.html#creating-resource-templates)

- `add_resource_template(resource_config: dict) -> str`
  Registers a resource template with the composer.

- **Arguments**:
  - `resource_config`: A dictionary describing the resource template. Should contain at least a `name` field.
- **Returns**: A success message.

**Example:**

```python
resource_config = {
    "name": "my_template",
    "description": "A template for creating resources",
    "uri_template": "resource://{name}",
    "mime_type": "text/plain",
    "tags": ["template", "example"],
    "enabled": True
}
result = await composer.add_resource_template(resource_config)
```

#### [Creating actual resources](https://ibm.github.io/mcp-composer/guide/resource-management.html#creating-resources)

- `create_resource(resource_config: dict) -> str`
  Creates an actual resource in the composer.

- **Arguments**:
  - `resource_config`: A dictionary describing the resource. Should contain at least a `name` field.
- **Returns**: A success message.

**Example:**

```python
resource_config = {
    "name": "my_resource",
    "description": "An actual resource with content",
    "uri": "resource://my_resource",
    "mime_type": "text/plain",
    "content": "This is the actual content of the resource",
    "tags": ["resource", "example"],
    "enabled": True
}
result = await composer.create_resource(resource_config)
```

#### [Listing resources and templates](https://ibm.github.io/mcp-composer/guide/resource-management.html#listing-resources)

- `list_resources() -> list[dict]`
  Lists all actual resources from composer and mounted servers.

- `list_resource_templates() -> list[dict]`
  Lists all resource templates from composer and mounted servers.

**Example:**

```python
# List actual resources
resources = await composer.list_resources()
for resource in resources:
    print(f"Resource: {resource['name']} - {resource['description']}")

# List resource templates
templates = await composer.list_resource_templates()
for template in templates:
    print(f"Template: {template['name']} - {template['description']}")
```

#### [List Resources per Server](https://ibm.github.io/mcp-composer/guide/resource-management.html#listing-resources-per-server)

- `list_resources_per_server(server_id: str) -> list[dict]`
  Lists all resources and templates from a specific server.

- **Arguments**:
  - `server_id`: The ID of the server to list resources from.
- **Returns**: A list of dictionaries containing resource information with server_id and type included.

**Example:**

```python
resources = await composer.list_resources_per_server("my-server")
for resource in resources:
    print(f"Resource: {resource['name']} from server: {resource['server_id']}")
    print(f"  Type: {resource['type']}")  # 'resource' or 'template'
```

#### [Enable Resources](https://ibm.github.io/mcp-composer/guide/resource-management.html#enabling-and-disabling-resources)

- `enable_resources(resources: list[str], server_id: str) -> str`
  Enables resources or templates from a specific server.

- **Arguments**:
  - `resources`: A list of resource names to enable.
  - `server_id`: The ID of the server containing the resources.
- **Returns**: A status message indicating success or failure.

**Example:**

```python
result = await composer.enable_resources(["finance_reference"], "mcp-stock-info")
print(result)  # "Enabled ['mcp-stock-info_finance_reference'] resources/templates from server mcp-stock-info"
```

#### [Disable Resources](https://ibm.github.io/mcp-composer/guide/resource-management.html#enabling-and-disabling-resources)

- `disable_resources(resources: list[str], server_id: str) -> str`
  Disables resources or templates from a specific server.

- **Arguments**:
  - `resources`: A list of resource names to disable.
  - `server_id`: The ID of the server containing the resources.
- **Returns**: A status message indicating success or failure.

**Example:**

```python
result = await composer.disable_resources(["finance_reference"], "mcp-stock-info")
print(result)  # "Disabled ['mcp-stock-info_finance_reference'] resources/templates from server mcp-stock-info"
```

#### [Filter Resources](https://ibm.github.io/mcp-composer/guide/resource-management.html#filtering-resources)

- `filter_resources(filter_criteria: dict) -> list[dict]`
  Filters resources based on criteria like name, description, tags, etc.

- **Arguments**:
  - `filter_criteria`: A dictionary containing filter criteria (name, description, tags, type).
- **Returns**: A list of dictionaries containing matching resources.

**Example:**

```python
# Filter by name
result = await composer.filter_resources({"name": "resource"})

# Filter by description
result = await composer.filter_resources({"description": "test"})

# Filter by type (resource or template)
result = await composer.filter_resources({"type": "resource"})

# Filter by multiple criteria
result = await composer.filter_resources({
    "name": "resource",
    "description": "test",
    "type": "template"
})
```

### [Demo using MCP Inspector](https://ibm.github.io/mcp-composer/examples/mcp-inspector.html)

1. Run the MCP Inspector as a background process, and take note of the session token/url with token pre-filled:

   ```bash
   npx @modelcontextprotocol/inspector
   ```

   To run a specific version use the following command

   ```bash
   npx @modelcontextprotocol/inspector@0.14.3
   ```

1. Navigate to `mcp-composer/` and create a `.env` file by copying the contents of `.env.example`.Then, set the Server and Tool config path in env file accordingly:

   ```bash
   cp mcp-composer/.env.example mcp-composer/.env
   ```

1. Run the following command

   ```bash
   uv run test/test_composer.py
   ```

1. Open the MCP Inspector in a browser with token pre-filled from the first step above. You can also open on `localhost:6274` and provide the `token` from the first step as the `Proxy Session Token`.

1. set _transport type_ and _URL_ from the previous step above and press `Connect`:

   > <img width="388" alt="image" src="https://github.ibm.com/ai-elite/mcp-composer/assets/3014/4931cf7c-5a0b-4c18-b405-42df30bcac27">

1. Go to Tools in the MCP Inspector and List Tools:

   > <img width="999" alt="image" src="https://github.ibm.com/ai-elite/mcp-composer/assets/3014/ce5eb760-d02c-42e5-9589-f807ce15ff15">

1. We will first use the `register_mcp_server` tool and register `stock_info` MCP server using the bellow config:

   ```json
   {
     "id": "mcp-stock-info",
     "type": "http",
     "endpoint": "https://mcp-stock-info.1vgzmntiwjzl.eu-es.codeengine.appdomain.cloud/mcp"
   }
   ```

   > <img width="1684" alt="image" src="https://github.ibm.com/ai-elite/mcp-composer/assets/3014/af0157ab-c4e5-4a25-a2be-ccabd800ada7">

1. Once the tool is run, it will be successfully registered:

   > <img width="1684" alt="image" src="https://github.ibm.com/ai-elite/mcp-composer/assets/3014/67f628fc-7773-496d-b9da-c44341f6d2d9">

1. Clear Tool and List Tool again - This is where it might take long time or throw time out error based on the configuration of the MCP Inspector. In case you have time out error disconnect the server and connect again and run the List Tool, it will show all the tools from composer and all tools from `mcp-stockinfo`:

   > <img width="1661" alt="image" src="https://github.ibm.com/ai-elite/mcp-composer/assets/3014/caefc2d8-7528-4231-a81f-5885cc0deab8">

1. Run any tools:

   > <img width="1670" alt="image" src="https://github.ibm.com/ai-elite/mcp-composer/assets/3014/f6678d13-99d3-4367-93ad-ab58d6431532">

# Demo: OAuth

#### 1. Create the environment file

Navigate to `mcp-composer` and create a `.env` file by copying the contents of `.env.example`:

```bash
cp mcp-composer/.env.example mcp-composer/.env
```

#### 2. Configure OAuth credentials

Open `.env` and replace the placeholder values with your actual OAuth provider details (e.g., client ID, client secret, redirect URI, etc.).

#### 3. Run the MCP Composer server

Execute the following command to start the server and test the OAuth integration:

```bash
uv run test/test_composer_oauth.py
```

### MCP Composer Client with Chatbot UI

MCP composer client provides an agent backend service to provide chatbot service that talks with all the tools from MCP Composer server.

A chatbot UI demo is also provided just for testing purpose [Demo-Chatbot-UI]().

#### 1. Setup env variables and configuration

In the same `.env` (copied from `mcp-composer/.env.example`), setup the following variables:

- `CHAT_MODEL_NAME`: watsonx or ollama
- `WATSONX_CHAT_MODEL`: meta-llama/llama-4-maverick-17b-128e-instruct-fp8, ibm/granite-3-3-8b-instruct, etc
- `WATSONX_URL`: Watsonx Instance URL
- `WATSONX_API_KEY`: API-Key of Watsonx instance
- `WATSONX_PROJECT_ID`: Watsonx Project ID
- `CHAT_MODEL_NAME`: local ollama model (if `CHAT_MODEL_NAME=ollama`)

Config file `config/mcp_composer_client.yaml` defines what MCP servers are connected, at current stage, it supports:

- Remote MCP-Composer Server
- Remote SSE/Http MCP-Server (testing purpose)
- Stdio MCP-Server (testing purpose)

Each server config has a boolean field `enabled` to enable the server or disable it.

#### 2. Launch chatbot agent service

(Before running chatbot agent service, make sure all `enabled: true` server in `config/mcp_composer_client.yaml` is properly setup and can be connected.)

- **Option-1. Run agent service in local development environment**

Launch agent service:

```bash
uv run src/mcp_composer_client/acp_server.py
```

It should output agent server URL in terminal:

```bash
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://localhost:8000 (Press CTRL+C to quit)
```

- **Option-2. Build and Run Docker Image**

  Build the image, taking default tag as "chatbot":

  ```bash
  docker build -t chatbot -f Dockerfile_Client .
  ```

  Run the image in container interactively (for Windows/Mac), by default, it uses `MCP_BASE_URL` to connect to MCP composer server.

  ```bash
  docker run -it -e HOST=0.0.0.0 -p 8000:8000 chatbot
  ```

  (In Linux, `-e HOST=0.0.0.0` can be removed.)

  If using `config/mcp_composer_client.yaml` to config multiple MCP servers, set env `USER_CONFIG_FILE` to `yes`:

  ```bash
  docker run -it -e USER_CONFIG_FILE=yes -e HOST=0.0.0.0 -p 8000:8000 chatbot
  ```

#### 3. Launch chatbot UI (Optional)

Follow instruction in [Demo-Chatbot-UI](https://github.ibm.com/ai-elite/mcp-composer-chatbot-ui), open browser and input chatbot UI URL. Interact with the chatbot.

## Troubleshooting

### Common Issues

1. **`KeyError: 'SERVER_CONFIG_FILE_PATH'`**
   - **Cause**: Missing environment variable configuration
   - **Solution**: Copy `env.example` to `.env` and set the required environment variables

   ```bash
   cp env.example .env
   ```

2. **`error: Unable to find lockfile at uv.lock`**
   - **Cause**: Missing lock file (first-time setup)
   - **Solution**: Run `uv sync` first to create the initial lock file

   ```bash
   uv sync
   ```

3. **Import errors when testing installation**
   - **Cause**: Environment variables not loaded
   - **Solution**: Ensure `.env` file exists and contains required variables

   ```bash
   # Check if .env file exists
   ls -la .env
   
   # If not, create it
   cp env.example .env
   ```

4. **Package not found when adding as local dependency**
   - **Cause**: Path issues or missing development install
   - **Solution**: Use the full path and install in editable mode

   ```bash
   uv add /full/path/to/mcp-composer --frozen
   uv pip install -e /full/path/to/mcp-composer
   ```

5. **Database configuration not working**
   - **Cause**: Invalid environment variables or missing required parameters
   - **Solution**: Check environment variable format and required parameters

   ```bash
   # Check environment variables
   echo $MCP_DATABASE_TYPE
   echo $MCP_DATABASE_API_KEY
   echo $MCP_DATABASE_SERVICE_URL
   
   # For Cloudant, ensure URL starts with http:// or https://
   export MCP_DATABASE_SERVICE_URL="https://your-instance.cloudantnosqldb.appdomain.cloud"
   
   # For local file storage, ensure file path is valid
   export MCP_DATABASE_FILE_PATH="/path/to/valid/file.json"
   ```

6. **Environment variables not taking effect**
   - **Cause**: Environment variables not properly set or loaded
   - **Solution**: Ensure environment variables are set before running the application

   ```bash
   # Set environment variables in your shell
   export MCP_DATABASE_TYPE="cloudant"
   export MCP_DATABASE_API_KEY="your_key"
   export MCP_DATABASE_SERVICE_URL="https://your-instance.cloudantnosqldb.appdomain.cloud"
   
   # Or add them to your .env file
   echo "MCP_DATABASE_TYPE=cloudant" >> .env
   echo "MCP_DATABASE_API_KEY=your_key" >> .env
   echo "MCP_DATABASE_SERVICE_URL=https://your-instance.cloudantnosqldb.appdomain.cloud" >> .env
   ```

7. **Server fails to start with database configuration errors**
   - **Cause**: Invalid database configuration (missing required fields, invalid URLs, etc.)
   - **Solution**: Fix the database configuration errors

   ```bash
   # Check the error logs for specific database configuration issues
   # Common issues: missing API keys, invalid service URLs, unsupported database types
   
   # For Cloudant, ensure all required fields are set:
   export MCP_DATABASE_TYPE="cloudant"
   export MCP_DATABASE_API_KEY="your_valid_api_key"
   export MCP_DATABASE_SERVICE_URL="https://your-instance.cloudantnosqldb.appdomain.cloud"
   
   # For local file storage:
   export MCP_DATABASE_TYPE="local_file"
   export MCP_DATABASE_FILE_PATH="/path/to/valid/file.json"
   ```

8. **Server starts but some servers are not mounted**
   - **Cause**: Individual server configuration errors (unsupported types, invalid endpoints, etc.)
   - **Solution**: Check logs for mount errors and fix the problematic server configurations

   ```bash
   # Look for "Failed to mount server" messages in the logs
   # Fix the specific server configurations that are failing
   # Server will continue to run with successfully mounted servers
   ```
