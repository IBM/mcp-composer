# mcp-composer-chatbot-ui
A demo UI of chatbot for MCP Composer client

Main interactions in this UI demo:
- Chat with API Agent by inputing any question
- Change LLM setting
- Test sample question

## Install dependencies

```bash
uv sync
```

### Demo Instructions

## 1. Launch an MCP composer instance 

Git clone mcp-composer (https://github.ibm.com/ai-elite/mcp-composer) 

```bash
cd mcp-composer
uv sync
source .venv/bin/activate
uv run test/test_composer.py
```

Note: Ensure your .env file has all the necessary vars showcased in .env.example (especially the config file)

## 2. Launch Single-Agent-Client agent server

In a new terminal within the same mcp-composer directory, run the agent server 

```bash
uv run src/mcp_composer_client/acp_server.py
```

It should output in terminal:
```bash
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://localhost:8000 (Press CTRL+C to quit)
```

## 3 Chatbot (by Beeai UI)

Prequisite: setup beeai locally (https://docs.beeai.dev/introduction/installation)

In a terminal window run: 
```bash
beeai platform start
beeai ui
```

Within the ui side bar select the **mcp_composer_chatbot** agent