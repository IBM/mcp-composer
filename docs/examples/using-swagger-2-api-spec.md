# Using Swagger 2 API Specification

> As the Swagger 2 API does not have `operrationId` they will not work for the MCP composer. Hence we need to convert the swagger 2 file to swagger 3 file and fix the `operationId`

## Convert v2 to v3 yaml file
1. Open a tab in browser and navigate to `https://editor.swagger.io/`

2. Click "Import" and select the file `example/openapispec/spec.json`

3. Click Edit > Convert to OpenAPI 3
4. Click on "Convert" and if there is error ignore for now. As there is no operationId in v2 these error are being there 
5. Copy all from the editor open a new file in your text editor and save the file as `example/openapispec/spec.yaml` yaml file

## Fix the operation id

1. clone the repo   [mcp-schema-optimization](https://github.ibm.com/ai-elite/mcp-schema-optimization)
2. cd to the `mcp-schema-optimization` folder run `uv sync`
3. run the following command where `spec.yml` is the input file and `test_output.json` is the output
    ```bash 
    uv run python main.py spec.yml test_output.json
    ```
4. this will generate a file called `test_output.json` which has the operation id fixed