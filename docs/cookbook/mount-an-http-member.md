# Mount an HTTP member

Start a member on a local HTTP port, register it with a bearer token, and print its health. Use this when the member is a URL rather than a process the composer starts itself.

## Run it

From `modules/mcp_composer`:

```bash
uv run python ../../example/cookbook/mount-an-http-member/run.py
```

The member prints a startup banner. After that, the script prints:

```text
Server 'shelf' mounted successfully.
auth: bearer
tools: shelf_count_open_boxes
health: shelf OK
```

## How it works

`shelf_server.py` listens on `127.0.0.1` and a free port. The composer registers `type: http` with `endpoint` set to `http://127.0.0.1:<port>/mcp`. `auth_strategy: bearer` and `auth.token` tell the composer to send `Authorization: Bearer shelf-local` on each call. Replace `shelf-local` with the token your member expects.

`member_health` requests that endpoint. `OK` means the member answered.

## Adapt it

1. Point `endpoint` at your member's MCP URL.
2. Keep the token in the server config, not in the prompt you send a model.
3. Read `member_health` after register. A refused connection is not `OK`.

## Not covered here

OAuth and API keys use the same `auth_strategy` field with a different value. This recipe only sends a bearer token to a local member.
