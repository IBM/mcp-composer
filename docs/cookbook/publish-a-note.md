# Publish a note

Store a short text resource and print the composer's confirmation. Use this when a client should read a fixed note by URI.

## What you will build

A program that prints `Resource 'shelf-note' created successfully`.

## Run it

From `modules/mcp_composer`:

```bash
uv run python ../../example/cookbook/publish-a-note/run.py
```

Expected output:

```text
Resource 'shelf-note' created successfully
```

## How it works

`create_resource` needs `name` and `uri`. `text` is the body. `description` is what a client sees before it reads the body. The script in `example/cookbook/publish-a-note/run.py` stores one note at `resource://shelf-note` and prints the returned message.

## Adapt it

Change `uri` and `text` to the note you want clients to fetch. Use a URI scheme your client already understands. The name is the label in the confirmation line.

## Not covered here

Resource templates, with placeholders in the URI, use `create_resource_template` instead of `create_resource`.
