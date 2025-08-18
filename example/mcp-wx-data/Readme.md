## Run the composer

1. Update spec_filepath location, endpoint and apikey in `example/mcp-wx-data/wx-data-config.json`


```
 {
    "open_api": {
        "endpoint": "...",
        "spec_filepath": "./src/mcp-composer/spec/wx-data-openapi.json",
        "auth": {
            "auth_prefix": "Bearer",
            "apikey": "...",
            "token_url": "https://iam.cloud.ibm.com/identity/token"
        }
    }
 }
```

2. Change the `SERVER_CONFIG_FILE_PATH` in the env as your local json file . for example 

```
SERVER_CONFIG_FILE_PATH="example/mcp-wx-data/wx-data-config.json"
```


3. Run the composer

```
uv run test/test_composer.py
```

## Update OpenAPI specification

1. Open *https://cloud.ibm.com/apidocs/watsonxdata* webpage
2. Click the three vertical dots icon next to 'watsonx.data'
3. Select 'Download OpenAPI definition' from the menu
4. Copy downloaded file to `spec/wx-data-openapi.json`