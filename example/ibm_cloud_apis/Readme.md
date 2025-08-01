# Run the composer

1. Update the `config.json` file:

Example:
```json
    {
    "id": "mcp-code-engine-v2",
    "auth_strategy": "dynamic_bearer",
    "auth": {
        "auth_prefix": "Bearer",
        "apikey": "<YOUR_API_KEY_HERE>",
        "token_url": "https://iam.cloud.ibm.com/identity/token"
    },
    ...
    }
```
make sure to **provide the API key** under the `auth` section


2. Change the `SERVER_CONFIG_FILE_PATH` in the env as your local json file . for example 

```
SERVER_CONFIG_FILE_PATH="example/ibm_mcp_composer/config.json"
```

3. Run the composer

```
uv run test/test_composer.py
```