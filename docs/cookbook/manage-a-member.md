# Manage a member

Mount a local member, pause it, resume it, replace its config, then remove it. Use this when a server should leave the client list without deleting its program.

## Run it

From `modules/mcp_composer`:

```bash
uv run python ../../example/cookbook/manage-a-member/run.py
```

The member prints a startup banner. After that, the script prints:

```text
Server 'shelf' mounted successfully.
active: shelf
Server 'shelf' deactivated successfully
active: none
Server 'shelf' activated
active: shelf
updated: Server 'shelf' mounted successfully.
Server 'shelf' unmounted successfully.
active: none
```

## How it works

`deactivate_mcp_server` keeps the saved config and drops the server from the active list. `activate_mcp_server` mounts that saved config again. `update_mcp_server_config` validates the new config and mounts it in place of the old one. `delete_mcp_server` unmounts the server and removes the saved config.

`active` is the list of servers that are not paused. A paused server is still on disk until you delete it.

## Adapt it

1. Start from a member you already registered.
2. Pause it when callers should stop seeing its tools.
3. Resume it from the saved config, or replace that config and mount again.
4. Delete it when the config itself should go.

## Not covered here

HTTP members and health checks are a separate recipe. GraphQL members use the same register call with a live schema endpoint, which this local program does not start.
