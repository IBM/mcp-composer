# Publish a skill

Save a skill in the catalog, mark that version deprecated, then delete it. Use this when instructions and allowed tool names should be a catalog row, not only a file.

## Run it

From `modules/mcp_composer`:

```bash
uv run python ../../example/cookbook/publish-a-skill/run.py
```

Expected output:

```text
published: count-open-boxes 1.0.0
listed: count-open-boxes
status: deprecated
after delete: 0
```

## How it works

`SkillManager.publish` stores one `SkillJSON` row: name, version, description, and `allowed-tools`. `list_summaries` returns the latest rows. `update_status` sets this version to `deprecated`. `delete` removes that name and version.

This recipe uses an in-memory catalog. The same manager talks to a file catalog or a database catalog. The calls do not change.

## Adapt it

1. Publish one version at a time. A new version does not erase the old row.
2. Set status to `deprecated` when callers should stop choosing that version.
3. Delete by name and version when the row should go.

## Not covered here

Mounting the skill catalog on a composer, and serving the skill to a live session, are separate from this publish path.
