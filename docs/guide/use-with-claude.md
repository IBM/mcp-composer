# Using whl file 
## Generate whl file
  - cd to the root folder of mcp-composer
  
  - Change Permission 
     ```
     chmod +x scripts/build.sh
     ```
  -  and Run
     ```
     ./scripts/build.sh
     ```

## Install whl file 
1. Downlaod the whl from given location
2. cd the folder where you installed it
3. There are different ways to install the `.whl` file


## Using python3

1. Install the whl
```
python3 -m pip install mcp_composer-0.1.0-py3-none-any.whl
```


## Using pipx

1. install pipx
   ```
   brew install pipx
   ```
3. install mcp-composer
   ```
   pipx install mcp_composer-0.1.0-py3-none-any.whl
   ```
  
5. ensure path
   ```
   pipx ensurepath
   ```
6. update the .zhs

   ```
   echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
   ```
   and 
   ```
   source ~/.zshrc
   ```

# Validate and Add to claude desktop
4. Validate the installation by running the following command
   ```
   which mcp-composer
   ```
   The output will look like 

   ```
    /Users/<username>/.local/bin/mcp-composer
   ```
   
6. update the claude desktop configuration by adding the following json inside the `claude_desktop_config.json`

```
   {
  "mcpServers": {
    "composer":{
    "command": "/Users/<username>/.local/bin/mcp-composer",
    "args": ["--mode", "stdio"],
    "env":{
       "SERVER_CONFIG_FILE_PATH": "/<path to the config file>/config.json"
    }
   }
  }
}
```

7. The `config.json` is an example of mcp server configuration for the mcp compsoer

   ```
   [{
    "id": "mcp-wxO",
    "type": "openapi",
    "open_api": {
      "endpoint": "https://api.dl.watson-orchestrate.ibm.com/instances/<instance_id>/v1/orchestrate/",
      "spec_filepath": "/<path-to-the-openapi-spec>/wxo-openapi-spec.json",
      "custom_routes": [
        {
          "methods": [
            "GET"
          ],
          "pattern": ".*/.*",
          "mcp_type": "TOOL"
        },
        {
          "methods": [
            "POST",
            "DELETE",
            "PUT",
            "PATCH"
          ],
          "pattern": ".*",
          "mcp_type": "EXCLUDE"
        }
      ]
    },
    "auth_strategy": "dynamic_bearer",
    "auth": {
      "apikey": "<api key>",
      "token_url": "https://iam.platform.saas.ibm.com/siusermgr/api/1.0/apikeys/token",
      "media_type": "json"
    }
   }]
   ```
   
9. Run Claude Desktop and confirm the composer server is connected.


## Run from cli
1. run the following command to run in http mode
```
mcp-composer --mode http --port 9000
```
2. To tun in `stdio` mode

```
mcp-composer --mode stdio 
```


## Uninstall mcp-composer


### Using pipx
```
pipx uninstall mcp-composer
```

and validate 

```
which mcp-composer
```


