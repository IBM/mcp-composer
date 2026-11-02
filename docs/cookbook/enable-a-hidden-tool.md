# Enable a hidden tool

Hide a write tool, then show it again. Use this when a tool was disabled and should return to the client list.

## Run it

From `modules/mcp_composer`:

```bash
uv run python ../../example/cookbook/enable-a-hidden-tool/run.py
```

The member prints a startup banner. After that, the script prints:

```text
before: stock_count_open_boxes, stock_seal_box
Disabled ['seal_box'] tools from server stock
hidden: stock_count_open_boxes
Enabled ['seal_box'] tools from server stock
after: stock_count_open_boxes, stock_seal_box
```

## How it works

`disable_tools_by_server` stores `seal_box` on the member. The script drops that name from the printed list. `enable_tools_by_server` clears it, and `list_tools` shows both names again.

The names you pass are the member names, not the `stock_` prefixed names.

## Adapt it

1. Disable the tools that should stay hidden.
2. Enable the same member names when they should come back.
3. Read the member's disabled list if you need to know what is hidden.

## Not covered here

Hiding every tool at once is a different call. This recipe toggles one write tool.
