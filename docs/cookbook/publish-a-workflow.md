# Publish a workflow

Save a two-step workflow, list it, then mark that version deprecated. Use this when a playbook should be a catalog row with ordered tool calls.

## Run it

From `modules/mcp_composer`:

```bash
uv run python ../../example/cookbook/publish-a-workflow/run.py
```

Expected output:

```text
published: count-then-seal
steps: count_open_boxes, seal_box
listed: count-then-seal
status: deprecated
```

## How it works

`WorkflowManager.publish` stores one `WorkflowJSON` row. The row has a goal and a list of steps. Each step names a tool and the input for that call. `list` returns the latest rows. `update_status` sets this version to `deprecated`.

The recipe does not call `count_open_boxes` or `seal_box`. It only records the order a later run would follow.

This recipe uses an in-memory catalog. A file catalog or a database catalog uses the same manager.

## Adapt it

1. Number steps from 1 and name the tool each step calls.
2. Put the caller's values in `input` when they are already known.
3. Deprecate a version instead of editing it in place when the steps change.

## Not covered here

Executing the steps against a mounted member is separate. This recipe stops once the row is stored and marked deprecated.
