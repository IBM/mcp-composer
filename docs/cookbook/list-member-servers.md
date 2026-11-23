# List member servers

Start a composer that stores members in a local file, then print the count. Use this when you want a known-empty composer before you register anything.

## What you will build

A short program that prints `member servers: 0`.

## Run it

From `modules/mcp_composer`:

```bash
uv run python ../../example/cookbook/list-member-servers/run.py
```

Expected output:

```text
member servers: 0
```

## How it works

`example/cookbook/list-member-servers/run.py` builds an `MCPComposer` with a `local_file` store inside a temporary directory. `setup_member_servers` loads that file. The file is empty, so `list_servers` returns an empty list.

The script calls `composer._server_manager.list_servers()`. That is the same function the composer registers as the `list_servers` tool.

## Adapt it

Point `file_path` at a JSON file you already use. The count becomes the number of active members in that file. Deactivated members stay out of the list.

## Not covered here

Registering a stdio or HTTP member is a later recipe. This one only reads an empty store.
