# Hide a write tool

Mount a tool that counts boxes and a tool that seals one, then remove the write tool from the list a client sees. Use this when a write should stay off until you are ready to allow it.

## What you will build

A program that prints the two stock tools, disables `seal_box`, and prints the list that remains.

## Run it

From `modules/mcp_composer`:

```bash
uv run python ../../example/cookbook/hide-a-write-tool/run.py
```

The member prints a startup banner. After that, the script prints:

```text
before: stock_count_open_boxes, stock_seal_box
Disabled ['seal_box'] tools from server stock
after: stock_count_open_boxes
```

## How it works

`stock_server.py` exposes `count_open_boxes` and `seal_box`. `run.py` mounts that server, then calls `disable_tools_by_server` with the member tool name `seal_box` and the server id `stock`. The composer stores that name on the member. The script prints the mounted names that are not on the member's disabled list.

The count tool stays. Hiding a tool does not stop the member process.

## Adapt it

1. Mount your own member.
2. Disable a write tool with its member name and the server id, not the prefixed composer name.
3. Drop any mounted name that appears on that member's disabled list.

## Not covered here

Turning the write tool back on is a separate call. This recipe stops once the write name is gone from the filtered list.
