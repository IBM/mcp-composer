# Describe look-alike tools

Mount two tools that both count boxes, and print the descriptions a client sees. Use this when two tools could answer the same request and each description has to say when not to use it.

## What you will build

A member with `count_open_boxes` and `count_sealed_boxes`. Each description names the job, when to use the tool, and the other tool to avoid.

## Run it

From `modules/mcp_composer`:

```bash
uv run python ../../example/cookbook/describe-lookalike-tools/run.py
```

The member prints a startup banner. After that, the script prints two lines:

```text
stock_count_open_boxes: Count open boxes on a named shelf. Use when the caller asks how many boxes are still open. Do not use for sealed boxes.
stock_count_sealed_boxes: Count sealed boxes on a named shelf. Use when the caller asks how many boxes are sealed. Do not use for open boxes.
```

## How it works

`stock_server.py` is a FastMCP server on stdio. The docstring on each tool is the description the composer returns from `list_tools`. The composer prefixes the tool name with the server id `stock`.

A short label such as "Count boxes" would fit both tools. The extra sentences are what a later choice can compare.

## Adapt it

1. Replace the two tools with a pair that your callers mix up.
2. Keep one sentence for what the tool does, one for when to use it, and one for when not to.
3. Put the difference in the name as well as the description. `count_open_boxes` and `count_sealed_boxes` already differ by one word.

## Not covered here

Choosing one tool from a sentence is a separate recipe. This one stops once both descriptions are visible.
