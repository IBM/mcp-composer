# Overview

The MCP gateway is a FastAPI based gateway that manages multiple MCP servers and tools. It handles dynamic tool registration, authentication, invocation dispatching, and health monitoring.
Servers and tools can be registered at runtime using structured JSON configurations.
The MCP gateway serves as an orchestrator for tool execution and forwards tool requests to the correct upstream MCP server or interface.

# Purpose

This system allows user to register any MCP servers or tools through a configuration JSON. The MCP Gateway exposes a set of MCP-compliant functions that allow listing tools, invoking them, updating credentials, and removing them.

The goal is to provide a single unified gateway that:

* Discovers and registers new MCP tools on startup or via API.
* Handles multiple authentication strategies.
* Mounts and unmounts member servers dynamically.
* Exposes all tools across registered servers.
* Supports tool filtering by server or tool name.

# Setup

1. clone the project
2. cd mcp-gateway
3. run the `uv sync` command

# Demo

1. Run the MCP Inspector
   ```bash
   npx -y @modelcontextprotocol/inspector@0.13.0
   ```
1. run the following command
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

# Demo: OAuth
#### 1. Create the environment file
Navigate to src/mcp_gateway and create a .env.oauth file by copying the contents of .env.oauth.example:
```bash
cp src/mcp_gateway/.env.oauth.example src/mcp_gateway/.env.oauth

```

#### 2. Configure OAuth credentials
Open .env.oauth and replace the placeholder values with your actual OAuth provider details (e.g., client ID, client secret, redirect URI, etc.).

#### 3. Run the MCP Gateway server
Execute the following command to start the server and test the OAuth integration:
```bash
uv run test/test_gw_oauth.py
```