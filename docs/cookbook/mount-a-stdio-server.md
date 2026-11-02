# Mount a stdio server

Start a small member process, mount it on the composer, and call one of its tools. Use this when the member is a program on the same machine, not an HTTP URL.

## What you will build

A member with two tools, `count_items` and `mark_sold`. The composer prefixes those names with the server id. The script then calls the count tool.

## Run it

From `modules/mcp_composer`:

```bash
uv run python ../../example/cookbook/mount-a-stdio-server/run.py
```

The member prints a startup banner. After that, the script prints:

```text
Server 'shelf' mounted successfully.
shelf tools: shelf_count_items, shelf_mark_sold
call: corner: 3
```

## How it works

`shelf_server.py` is a FastMCP server on stdio. `run.py` allowlists the current Python binary in `MCP_COMPOSER_STDIO_ALLOWLIST`, then registers this config:

```python
{
    "id": "shelf",
    "type": "stdio",
    "command": "<absolute path to python>",
    "args": ["<path to shelf_server.py>"],
}
```

The command has to be an absolute path, and that path has to be on the allowlist. The child process also receives `PYTHONPATH` so it can import FastMCP from the same environment.

`list_tools` returns composer tools and member tools. Member tool names start with `shelf_`. `call_tool` sends `{"shelf": "corner"}` to `shelf_count_items`.

## Adapt it

1. Replace `shelf_server.py` with your own stdio server.
2. Keep `command` as the absolute path of the interpreter or binary that starts it.
3. Put that same path in `MCP_COMPOSER_STDIO_ALLOWLIST` before you register the server.
4. Expect tool names to be `<server id>_<tool name>`.

## Not covered here

HTTP members, and hiding a tool after it is mounted, are separate tasks. This recipe stops once one call returns.
