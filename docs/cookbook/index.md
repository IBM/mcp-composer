# Cookbook

Copy a recipe, run it, then change the names to match your own servers.

Each recipe has a page here and a folder under `example/cookbook/`. The folder is the program. The page is how to run it and what the output means.

| Topic | Recipe | What it shows |
| --- | --- | --- |
| Compose | [List member servers](/cookbook/list-member-servers) | An empty composer reports zero members |
| Instruct | [Add a prompt](/cookbook/add-a-prompt) | A template the composer can hand to a client |
| Share | [Publish a note](/cookbook/publish-a-note) | A text resource stored under a URI |
| Connect | [Mount a stdio server](/cookbook/mount-a-stdio-server) | A local process joins the composer and answers a tool call |
| Import | [Import an OpenAPI spec](/cookbook/import-an-openapi-spec) | Two HTTP operations become named tools |

Run every recipe from `modules/mcp_composer` so `uv` uses this project's environment.

```bash
cd modules/mcp_composer
uv run python ../../example/cookbook/check_catalog.py
```
