# Keep a skill across turns

Match a skill from the words in a message, keep it on the next message, then add a second skill. Use this when instructions and tool names should follow the session, not only the latest sentence.

## What you will build

A program that prints the active skill names and their tool names for three turns.

## Run it

From `modules/mcp_composer`:

```bash
uv run python ../../example/cookbook/keep-a-skill-across-turns/run.py
```

Expected output:

```text
turn 1: count-open-boxes | tools: count_open_boxes
turn 2: count-open-boxes | tools: count_open_boxes
turn 3: count-open-boxes, seal-a-box | tools: count_open_boxes, seal_box
```

## How it works

`catalog.json` holds two skills. Each one has tags and `allowed-tools`. Turn 1 mentions open boxes, so `count-open-boxes` becomes active. Turn 2 is "yes go ahead" and matches no new skill, so the first skill stays. Turn 3 mentions seal, so `seal-a-box` is added and its tool joins the list.

The tool names are the same ones the stock recipes mount. This script does not call them. It only decides which names a later step would hand to the agent.

## Adapt it

1. Replace the catalog with your own skill names, tags, and tool names.
2. Keep a skill until the session ends, even when the next message is only a confirmation.
3. Add a skill when its tags appear. Do not drop the ones already active.

## Not covered here

Publishing skills to a shared catalog is separate. This recipe keeps the session in memory and stops after three printed turns.
