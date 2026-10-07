# Using Swagger 2 API Specification

> As the Swagger 2 API does not have `operrationId` they will not work for the MCP composer. Hence we need to convert the swagger 2 file to swagger 3 file and fix the `operationId`

## Convert v2 to v3 yaml file
1. Open a tab in browser and navigate to `https://editor.swagger.io/`

2. Click "Import" and select the file `example/openapispec/spec.json`

3. Click Edit > Convert to OpenAPI 3
4. Click on "Convert" and if there is error ignore for now. As there is no operationId in v2 these error are being there 
5. Copy all from the editor open a new file in your text editor and save the file as `example/openapispec/spec.yaml` yaml file

## Fix the operation id

Swagger 2 conversions often omit `operationId`. MCP Composer uses that field as the tool name. In the OpenAPI 3 document, set a unique `operationId` on each operation (Swagger Editor, or any OpenAPI linter). No extra repository is required.