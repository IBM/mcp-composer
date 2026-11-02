# Publish an agent

Save an agent row in the catalog, list it, then delete it. Use this when an agent definition should sit beside skills and workflows.

## Run it

From `modules/mcp_composer`:

```bash
uv run python ../../example/cookbook/publish-an-agent/run.py
```

Expected output:

```text
published: shelf-clerk 1.0.0
listed: shelf-clerk
after delete: 0
```

## How it works

`AgentManager.publish` stores one `AgentJSON` row with a name, version, and description. `list` returns the latest rows. `delete` removes that name and version.

This recipe uses an in-memory catalog. A file catalog or a database catalog uses the same manager.

## Adapt it

1. Keep the agent name stable and publish a new version when the description changes.
2. Point the description at the task the agent is for.
3. Delete by name and version.

## Not covered here

Linking the agent to a running session is separate. This recipe only stores the row.
