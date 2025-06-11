<div align="center">

<!-- omit in toc -->
# MCP Gateway
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
  - [MCP Gateway Tools](#mcp-gateway-tools)
- [Demo using MCP Inspector](#demo-using-mcp-inspector)

---

## Overview

The MCP gateway is a FastAPI based gateway that manages multiple MCP servers and tools.
Servers and tools can be registered at runtime using structured JSON configurations.
The MCP gateway serves as an orchestrator for tool execution and forwards tool requests to the correct upstream MCP server or interface.

The MCP Gateway supports multiple tool types, such as OpenAPI (REST), GraphQL, CLI-based tools, client SDKs, and nested MCP servers.

## Purpose

The goal of the gateway is to handle dynamic tool registration, authentication, invocation dispatching, and health monitoring.
It abstracts underlying protocol, authentication and routing complexities, 
and allows tools to be called through a single, unified interface. The MCP Gateway exposes a set of MCP-compliant functions that allow listing tools, invoking them, updating credentials, and removing them.

The goal is to provide a single unified gateway that:

* Discovers and registers new MCP tools on startup or via API.
* Mounts and unmounts member servers dynamically.
* Exposes all tools across registered servers.

## Installation

### Prerequisites

*   Python 3.10+
*   [uv](https://docs.astral.sh/uv/) (Recommended for environment management)

### Setup

Clone the repository
```bash
git clone https://github.ibm.com/ai-elite/mcp-gateway.git
cd mcp-gateway
```
2. Create and sync the environment: 
   ```bash
   uv sync
   ```
   This installs all dependencies.
   
3. Activate the virtual environment.
   ```bash
   source .venv/bin/activate
   ```


## Key Features
* Register or remove tools at runtime using structured JSON configurations.
* Support a range of tool types (openapi, graphql, client, mcp, etc.)
* Handles multiple authentication strategies.
* Automatically forwards each request to the correct upstream server or tool.
* List tools and metadata by name or server.

### MCP Gateway Tools

* register_mcp_server: Register a single server dynamically from config.
* remove_mcp_server: Remove a single server dynamically from config.
* get_tool_config_by_name: Get a tool configuration details
* get_tool_config_by_server: Get all tool configuration details of a specific member server 
* remove_tools: Remove a tool or multiple from the servers and gateway 
* list_member_servers: List all registered member servers
* update_tool_description: Update tool description of member servers

### Demo using MCP Inspector

1. Run the MCP Inspector
   ```bash
   npx -y @modelcontextprotocol/inspector@0.13.0
   ```
1. Run the following command
   ```bash
   uv run test/test_gw.py
   ```
1. Open the MCP Inspector in a browser; set _transport type_ and _URL_ from the previous step above and press `Connect`:

   > <img width="388" alt="image" src="https://github.ibm.com/ai-elite/mcp-gateway/assets/3014/4931cf7c-5a0b-4c18-b405-42df30bcac27">

1. Go to Tools in the MCP Inspector and List Tools:

   > <img width="999" alt="image" src="https://github.ibm.com/ai-elite/mcp-gateway/assets/3014/ce5eb760-d02c-42e5-9589-f807ce15ff15">

1. We will first use the `register_mcp_server` tool and register `stock_info` MCP server using the bellow config:

   ```json
   {
     "id": "mcp-stock-info",
     "type": "http",
     "endpoint": "https://mcp-stock-info.1vgzmntiwjzl.eu-es.codeengine.appdomain.cloud/mcp"
   }
   ```

   > <img width="1684" alt="image" src="https://github.ibm.com/ai-elite/mcp-gateway/assets/3014/af0157ab-c4e5-4a25-a2be-ccabd800ada7">

1. Once the tool is run, it will be successfully registered:

   > <img width="1684" alt="image" src="https://github.ibm.com/ai-elite/mcp-gateway/assets/3014/67f628fc-7773-496d-b9da-c44341f6d2d9">

1. Clear Tool and List Tool again - This is where it might take long time or throw time out error based on the configuration of the MCP Inspector. In case you have time out error disconnect the server and connect again and run the List Tool, it will show 2 tools from gateway and all tools from `mcp-stockinfo`:

   > <img width="1661" alt="image" src="https://github.ibm.com/ai-elite/mcp-gateway/assets/3014/caefc2d8-7528-4231-a81f-5885cc0deab8">

1. Run any tools:

   > <img width="1670" alt="image" src="https://github.ibm.com/ai-elite/mcp-gateway/assets/3014/f6678d13-99d3-4367-93ad-ab58d6431532">
