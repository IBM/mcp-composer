# Add a curl tool

Turn one curl command into a composer tool. The script does not send the request. Use this when an HTTP call should become a tool without an OpenAPI file.

## Run it

From `modules/mcp_composer`:

```bash
uv run python ../../example/cookbook/add-a-curl-tool/run.py
```

Expected output:

```text
Successfully added tools
tools: list_shelf_items
```

## How it works

`add_tools_from_curl` reads `curl_config.value`, parses the command, and registers a tool named `list_shelf_items`. The sample command is `curl http://127.0.0.1:9/shelf`. Nothing is listening there, and this recipe never calls the tool.

The composer stores a versioned copy of the command so a later run can roll back to an older copy. This recipe stops once the name is registered.

## Adapt it

1. Put the real curl command in `curl_config.value`.
2. Register the tool before any client calls it.
3. Keep tokens out of the command string when you can pass them as headers at call time.

## Not covered here

Calling the tool, and rolling back to an older stored version, are separate steps.
