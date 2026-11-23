# Choose a tool

Score a short request against three stock tools and print one of four outcomes. Use this when look-alike tools exist and the caller should see a small set, or a question, instead of every tool.

## What you will build

A program that prints a result for five requests: one clear read, one tie between two reads, one tie that includes a write, one clear write, and one request that matches nothing.

## Run it

From `modules/mcp_composer`:

```bash
uv run python ../../example/cookbook/choose-a-tool/run.py
```

Expected output:

```text
count the open boxes: RESOLVED count_open_boxes
count the boxes: FAN_OUT count_open_boxes, count_sealed_boxes
seal boxes: CLARIFY count_open_boxes, count_sealed_boxes, seal_box
seal one box: RESOLVED seal_box
what is the weather: NO_MATCH
```

## How it works

Each tool has a few words and a side effect, `read` or `write`. The script counts how many of those words appear in the request.

| Outcome | When |
| --- | --- |
| `RESOLVED` | One tool scores higher than the rest |
| `FAN_OUT` | Two read tools tie |
| `CLARIFY` | A tie includes a write tool |
| `NO_MATCH` | No tool shares a word with the request |

`FAN_OUT` names both read tools because either one can answer. A tie that includes `seal_box` is `CLARIFY` because that tool changes stock.

## Adapt it

1. Replace the three tool rows with names and words from your own servers.
2. Keep the four outcomes. Taking only the top score hides a tie.
3. Treat a write tool in a tie as a question, not as a tool to call.

## Not covered here

This recipe does not mount a server or call a tool. It only prints the decision.
