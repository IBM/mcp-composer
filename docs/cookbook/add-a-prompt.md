# Add a prompt

Register one prompt template and print the name the composer kept. Use this when a client should ask for a named instruction instead of a free-form string.

## What you will build

A program that prints `prompts: shelf_summary`.

## Run it

From `modules/mcp_composer`:

```bash
uv run python ../../example/cookbook/add-a-prompt/run.py
```

Expected output:

```text
prompts: shelf_summary
```

## How it works

`add_prompts` takes a dictionary with `name` and `template`. Optional `description` and `arguments` tell a client what to fill in. The method returns the names it registered. The script prints those names.

The template in `example/cookbook/add-a-prompt/run.py` is `Summarize the shelf called {shelf_name}.` The argument `shelf_name` is required.

## Adapt it

Replace `shelf_summary` and the template text with an instruction your client already asks for. Keep `{argument}` placeholders aligned with the `arguments` list. A missing `name` or `template` raises `ValueError`.

## Not covered here

Listing prompts back through a client session is separate from registration. This recipe stops once the name is stored.
