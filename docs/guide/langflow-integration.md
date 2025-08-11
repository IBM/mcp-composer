# 🧩 MCP Composer + Langflow Installation Guide

> ⚠️ Until MCP Composer is published to PyPI or open-sourced, you must install MCP Composer and Langflow separately.

---

## 🚀 MCP Composer: Install as a Tool

1. **Clone the MCP Composer Repository**  

```bash
   git clone https://github.ibm.com/ai-elite/mcp-composer.git
   cd mcp-composer
```

2. **Install using uv**

```bash
uv sync
```

If you hit a uv sync error: Failed to parse `uv.lock` you’ll need to delete the uv.lock file and rebuild it with `uv lock --upgrade`

3. **Install MCP Composer as a UV tool**

Update the path below based on your local install location:

```bash
uv tool install -e /Users/charna.parkey/code/mcp-composer
```
Export the path provided by that tool install

```bash
export PATH="/Users/charna.parkey/.local/bin:$PATH"
```

4. **Verify installation**

Use the CLI to see if mcp composer can successfully be booted via uvx

```bash
uvx mcp-composer --mode sse
```
You should see mcp composer successful boot up with an info message that says:

```bash
INFO:     Uvicorn running on http://0.0.0.0:9000 (Press CTRL+C to quit)
```

⚠️ Stop the MCP Composer before continuing
You can't run two MCP Composers on the same port during the rest of this demo.

## 🌐 Langflow Installation & Setup

1. **Clone the main branch**

```bash
git clone https://github.com/langflow-ai/langflow
cd langflow
```
2. **Install Langflow**

```bash
uv pip install langflow -U
```

Set the feature flag as an environment variable

```bash
export LANGFLOW_FEATURE_MCP_COMPOSER=true
make build_frontend
```

3. **Start Langflow**

```bash
uv run langflow run
```

4. **Open Langflow UI**

Navigate to: <http://127.0.0.1:7860>

### 🔐 Add Auth to MCP Server in Langflow

In Langflow, ensure you have a working flow (e.g., Simple Agent with OpenAI credentials).

1. **Navigate to Project > MCP Server > Click Edit Auth and enter:**

```bash
OAUTH_HOST=localhost
OAUTH_PORT=9000
OAUTH_SERVER_URL=http://localhost:9000
OAUTH_CALLBACK_PATH=
OAUTH_CLIENT_ID=<your-client-id>
OAUTH_CLIENT_SECRET=<your-client-secret>
OAUTH_AUTH_URL=https://preprod.login.w3.ibm.com/v1.0/endpoint/default/authorize
OAUTH_TOKEN_URL=https://preprod.login.w3.ibm.com/v1.0/endpoint/default/token
OAUTH_MCP_SCOPE=user
OAUTH_PROVIDER_SCOPE=openid
```

2. **Click Save Authentication**

✅ You can now use this MCP Server inside Langflow in new flows or install it into:

- Cursor
- Claude
- Windsurf

## 🧠 Claude Integration
1. Go to the Auto Install tab inside Langflow, click + next to Claude

2. Restart Claude. On opening, you should be redirected to the OAuth flow.

If Claude fails to start due to uvx path issues, update the configuration JSON to:

```json

"command": "/Users/charna.parkey/.langflow/uv/uvx"
```

## 🛠️ Using MCP Composer Server via Langflow Canvas

- Copy the JSON from the MCP Server tab of the flow you want to connect
- Create a new project and new simple agent flow from a template
- Add a MCP Tool from the side bar onto the canvas
- Click Add MCP Server
- Paste the JSON config and click add server
- This should redirect you to a successful auth flow
- Navigate back to Langflow and turn on tool mode for your MCP Tool
- Connect the toolset to the agent and click Playground to chat with the agent and have it use it’s tools
- Similarly, you now have a MCP Composer MCP Server running on port 9000 you'll need to delete the server from Langflow if you want this to stop running locally to go back to claude or try the next part

🛑 If you're done, remove the MCP Composer server from Langflow to stop running on port 9000

## 🌍 Connecting Other MCP Servers via MCP Composer
- Any MCP Servers that are in the config file of the MCP Composer will be made available when connecting MCP Composer to Langflow, you do not need to have the langflow servers passed via the json snippet and you do not need to pass the oath via the environment variable if it is configured this way
  - To do this you’ll need to create a config.json file in the mcp-composer/config folder
- Add mcp server configs to the config.json file in the config directory of the MCP Composer
- Create a .env file in the mcp-composer directory and add the auth environment variables above
- Then add the MCP Server of MCP Composer to Langflow
- When you add the MCP Server either in the canvas or in the global settings
- you can now use the MCP Tools in the canvas and reduced to the set of tools relevant to that flow
