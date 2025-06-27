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
  - [MCP Composer Tools](#mcp-composer-tools)
- [Demo using MCP Inspector](#demo-using-mcp-inspector)

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

### Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (Recommended for environment management)

### Setup

1. Clone the repository
   ```bash
   git clone https://github.ibm.com/ai-elite/mcp-composer.git
   cd mcp-composer
   ```
2. Create and sync the environment:

   ```bash
   uv sync --frozen        # Strict install (uses lock file exactly) - recommended as ensuring consistency across different environments
   # uv sync               # Install (update lock file) - incremental refresh, commit uv.lock
   # rm uv.lock && uv sync # Refresh child dependencies, commit uv.lock
   ```

   This installs all dependencies.

3. Activate the virtual environment.

   ```bash
   source .venv/bin/activate
   ```

   > If you want to use `pip` tool, run it as `uv pip <params>`, do not run explicitly (`pip <params>)`

## Key Features

- Register or remove tools at runtime using structured JSON configurations.
- Support a range of tool types (openapi, graphql, client, mcp, etc.)
- Handles multiple authentication strategies.
- Automatically forwards each request to the correct upstream server or tool.
- List tools and metadata by name or server.

### MCP Composer Tools

- register_mcp_server: Register a single server.
- delete_mcp_server: Delete a single server.
- member_health: Get status for all member servers.
- activate_mcp_server: Reactivates a previously deactivated member server by loading its config, updating status in DB, and mounting it.
- deactivate_mcp_server: Deactivates a member server by unmounting it and marking it as deactivated in DB.
- get_tool_config_by_name: Get a tool configuration details
- get_tool_config_by_server: Get all tool configuration details of a specific member server
- remove_tools: Remove a tool or multiple from the servers and Composer
- list_member_servers: List status of all member servers (active or deactivated).
- update_tool_description: Update tool description of member servers

### Demo using MCP Inspector

1. Run the MCP Inspector as a background process
   ```bash
   npx -y @modelcontextprotocol/inspector@0.13.0 &
   ```
1. Run the following command
   ```bash
   uv run test/test_composer.py
   ```
1. Open the MCP Inspector in a browser (usually  http://127.0.0.1:6274); set _transport type_ and _URL_ from the previous step above and press `Connect`:

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
