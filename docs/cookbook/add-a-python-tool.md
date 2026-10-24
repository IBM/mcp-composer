# Add a Python tool

Turn one Python function into a composer tool. Use this when the tool is a short function, not a separate MCP server.

## Run it

From `modules/mcp_composer`:

```bash
uv run python ../../example/cookbook/add-a-python-tool/run.py
```

Expected output:

```text
Successfully added tools
tools: count_open_boxes
```

## How it works

`add_tools_from_python` takes a name, a description, and `script_config.value`. That value is the source of exactly one function. The composer compiles it and registers a tool with the same name.

The composer also writes the function into its custom tool file so a later process can load it again.

## Adapt it

1. Keep the script to one function.
2. Avoid imports unless you intend the composer to install them.
3. Call the new tool by the name you set, with no server prefix.

## Not covered here

A member server is a better home for more than one function. This recipe adds a single function.
