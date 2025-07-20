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
- [Key Features](#key-features)
  - [MCP Composer Servers](#mcp-composer-servers)
  - [Command Line Interface (CLI)](#command-line-interface-cli)
  - [MCP Composer Tools](#mcp-composer-tools)
  - [MCP Composer Prompts](#mcp-composer-prompts)
- [Demo using MCP Inspector](#demo-using-mcp-inspector)
- [MCP Composer Client with Chatbot UI](#mcp-composer-client-with-chatbot-ui)

---

## Overview

The MCP Composer is a FastAPI based Composer that manages multiple MCP servers and tools.
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

### Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (Recommended for environment management)

### Setup

1. Clone the repository
   ```bash
   git clone https://github.ibm.com/ai-elite/mcp-composer.git
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

4. Synchronize the environment.

  
   ```bash
   uv sync --frozen        # Strict install (uses lock file exactly) - recommended as ensuring consistency across different environments
   uv sync               # Install (update lock file) - incremental refresh, commit uv.lock
   rm uv.lock && uv sync # Refresh child dependencies, commit uv.lock
   ```
5. Add a new dependency; automatically creates a virtual environment if necessary

   ```bash
   uv add <my-package>   
   ```
6. Leverage the project's virtual environment:
   ```
   uv run <command&args> 
   ```
7. Test if MCP Composer is installed successfully or not

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

## Key Features

- Register or remove tools at runtime using structured JSON configurations.
- Support a range of tool types (openapi, graphql, client, mcp, etc.)
- Handles multiple authentication strategies.
- Automatically forwards each request to the correct upstream server or tool.
- List tools and metadata by name or server.

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

- register_mcp_server: Register a single server.
- delete_mcp_server: Delete a single server.
- member_health: Get status for all member servers.
- activate_mcp_server: Reactivates a previously deactivated member server by loading its config, updating status in DB, and mounting it.
- deactivate_mcp_server: Deactivates a member server by unmounting it and marking it as deactivated in DB.
- list_member_servers: List status of all member servers (active or deactivated).
- get_tool_config_by_name: Get a tool configuration details
- get_tool_config_by_server: Get all tool configuration details of a specific member server
- disable_tools: Disable a tool or multiple from the servers and Composer
- enable_tools: Enable a tool or multiple from the servers and Composer
- update_tool_description: Update tool description of member servers
- [add_tools](#Add-tool-using-Curl-command-and-Python-script): Add tool using curl command or Python script.
- [add_tools_from_openapi](#Add-tool-using-OpenAPI-specification): Add tool using the OpenAPI specifications

#### Add tool using Curl command and Python script
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

#### Add tool using OpenAPI specification
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


### MCP Composer Prompts

#### Adding one or more prompts

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

### Get all Prompts

- `get_all_prompts() -> list[str]`
  Retrieves all registered prompts as JSON strings, with internal function references stripped.

- **Returns**: A list of JSON strings, each representing a prompt (excluding the `fn` field).

**Example:**

```python
prompts = await composer.get_all_prompts()
for prompt_json in prompts:
    print(prompt_json)
```

### Demo using MCP Inspector

1. Run the MCP Inspector as a background process, and take note of the session token/url with token pre-filled:

   ```bash
   npx @modelcontextprotocol/inspector
   ```

   To run a specific version use the following command

   ```bash
   npx @modelcontextprotocol/inspector@0.14.3
   ```

1. Navigate to `src/` and create a `.env` file by copying the contents of `.env.example`.Then, set the Server and Tool config path in env file accordingly:

   ```bash
   cp src/.env.example src/.env
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

Navigate to `src/mcp_composer` and create a `.env.oauth` file by copying the contents of `.env.oauth.example`:

```bash
cp src/mcp_composer/.env.oauth.example src/mcp_composer/.env.oauth
```

#### 2. Configure OAuth credentials

Open `.env.oauth` and replace the placeholder values with your actual OAuth provider details (e.g., client ID, client secret, redirect URI, etc.).

#### 3. Run the MCP Composer server

Execute the following command to start the server and test the OAuth integration:

```bash
uv run test/test_composer_oauth.py
```

### MCP Composer Client with Chatbot UI

MCP composer client provides an agent backend service to provide chatbot service that talks with all the tools from MCP Composer server.

A chatbot UI demo is also provided just for testing purpose ([Demo-Chatbot-UI](https://github.ibm.com/ai-elite/mcp-composer-chatbot-ui)).

#### 1. Setup env variables and configuration

In the same `.env` (copied from `src/.env.example`), setup the following variables:

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
