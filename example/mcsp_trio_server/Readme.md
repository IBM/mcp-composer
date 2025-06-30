# Run the composer

1. Change the spec location in `mcsp_trio_master.json` as well as the secrets

for example 

```
 {
  "id": "mcp-instana",
  ... ...  
  "spec_filepath": "/Users/<USERNAME>/mcp-composer/spec/instana-openapi.json",

  .. ...
 }
```

2. Change the `SERVER_CONFIG_FILE_PATH` in the env as your local json file . for example 

```
SERVER_CONFIG_FILE_PATH="example/mcsp_trio_server/mcsp_trio_master.json"
```

3. Run the composer

```
uv run test/test_composer.py
```