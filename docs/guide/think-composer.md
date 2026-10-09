# Think Composer

Think Composer is the thinking domain process. The server name is `think-composer`. It registers `sequential_thinking`, hides the generic management tools, and still mounts member servers from the usual composer config.

The entry is `modules/mcp_composer/composers/think_composer.py`. `composers/thinker_composer.py` starts the same process.

## Run

From `modules/mcp_composer`:

```bash
uv run composers/think_composer.py
```

The default listen address is `http://127.0.0.1:9000/mcp`.

## Environment

| Variable | Default | Purpose |
|----------|---------|---------|
| `MCP_MODE` | `http` | `http` or `stdio` |
| `MCP_HOST` | `127.0.0.1` | Loopback name only |
| `MCP_PORT` | `9000` | Listen port |

A non-loopback host is refused. This process does not install authentication. Use the CLI with `--auth-type oauth` when a public bind is required.

Stdio member servers still require `MCP_COMPOSER_STDIO_ALLOWLIST`.

## Tool

`sequential_thinking` keeps a session of thoughts. Each call sends the current thought, whether another thought is needed, the thought number, and the current estimate of how many thoughts the problem needs. The tool can revise an earlier thought or branch into another line of reasoning.

Member servers configured for the composer stay available beside that tool.
