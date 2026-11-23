# Import an OpenAPI spec

Read a local OpenAPI file and print the tool names the composer created. Use this when you already have an HTTP API and want one tool per operation.

## What you will build

Two tools from `shelf.openapi.json`: list items, and remove one item. The composer prefixes both names with the server id `shelf-api`.

## Run it

From `modules/mcp_composer`:

```bash
uv run python ../../example/cookbook/import-an-openapi-spec/run.py
```

Expected lines:

```text
Server 'shelf-api' mounted successfully.
openapi tools: shelf-api_list_shelf_items, shelf-api_remove_shelf_item
```

The script does not call those tools. The endpoint in the config is a placeholder, so a call would fail until you point it at a server that is running.

## How it works

`MCP_COMPOSER_MODE=dev` allows `spec_filepath`. Production mode accepts `spec_url` only. The config is:

```python
{
    "id": "shelf-api",
    "type": "openapi",
    "open_api": {
        "endpoint": "http://127.0.0.1:9",
        "spec_filepath": "<path to shelf.openapi.json>",
    },
}
```

Each `operationId` becomes a tool. `list_shelf_items` is the GET on `/items`. `remove_shelf_item` is the DELETE on `/items/{item_id}`.

## Adapt it

1. Put your OpenAPI 3 file next to the script, or pass its absolute path as `spec_filepath`.
2. Set `endpoint` to the API base URL the tools should call.
3. Give every operation an `operationId`. The composer uses that id in the tool name.
4. Leave `MCP_COMPOSER_MODE` unset when the spec is fetched from `spec_url` in production.

## Not covered here

Auth headers, and calling a tool against a live API, are not in this script. Mount the spec first, then point `endpoint` at a server you control.
