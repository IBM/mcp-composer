# Rewrite a tool description

Replace the description the composer stores for one mounted tool. Use this when the member's own text is too short and you want the longer text without editing the member.

## Run it

From `modules/mcp_composer`:

```bash
uv run python ../../example/cookbook/rewrite-a-tool-description/run.py
```

The member prints a startup banner. After that, the script prints:

```text
Updated count_open_boxes with description: Count open boxes on a named shelf, for example corner. Use when the caller needs a number. Do not use to seal a box.
stored: Count open boxes on a named shelf, for example corner. Use when the caller needs a number. Do not use to seal a box.
```

## How it works

`update_tool_description` takes the member tool name, the new text, and the server id. It stores that text on the member. The script prints the text back from the member record.

The tool name here is `count_open_boxes`, without the `shelf_` prefix a client sees.

## Adapt it

1. Mount the member first.
2. Pass the member's tool name and the server id.
3. Write what the tool does, when to use it, and when not to.

## Not covered here

Changing the description inside the member program is a different edit. This recipe only changes the text the composer stores.
