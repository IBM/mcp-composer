# Tool Management

MCP Composer supports the following tools by default:

- **`register_mcp_server`**: Register a single server.

```python
await composer.register_mcp_server({
    "id": "customer-api",
    "name": "Customer API",
    "type": "http",
    "endpoint": "https://api.customers.com/mcp"
})
```

- **`delete_mcp_server`**: Delete a single server.

```python
await composer.delete_mcp_server('customer-api')
```

- **`member_health`**: Get status for all member servers.

```python
await composer.member_health()
```

- **`activate_mcp_server`**: Reactivates a previously deactivated member server by loading its config, updating status in DB, and mounting it.

```python
await composer.activate_mcp_server('customer-api')
```

- **`deactivate_mcp_server`**: Deactivates a member server by unmounting it and marking it as deactivated in DB.

```python
await composer.deactivate_mcp_server('customer-api')
```

- **`list_servers`**: List status of all member servers (active or deactivated).

```python
await composer.list_servers()
```

- **`get_tool_config_by_name`**: Get a tool's configuration details.

```python
await composer.get_tool_config_by_name('tool_customer_info')
```

- **`get_tool_config_by_server`**: Get all tool configuration details of a specific member server.

```python
await composer.get_tool_config_by_server('customer-api')
```

- **`disable_tools`**: Disable one or more tools from the servers and Composer.

```python
await composer.disable_tools(tools= ["tool_customer_info"], server_id: "customer-api")
```

- **`enable_tools`**: Enable one or more tools from the servers and Composer.

```python
await composer.enable_tools(tools= ["tool_customer_info"], server_id: "customer-api")
```

- **`update_tool_description`**: Update tool descriptions on member servers.

```python
await composer.update_tool_description(tool='tool_customer_info', description="Get customer details", server_id="customer-api")
```

> **Removed:** `add_tools_from_curl`, `add_tools_from_python`, `add_tools_from_openapi`,
> `rollback_openapi_tool_version` and `rollback_curl_tool_version`, together with the
> `ENABLE_ADD_TOOLS_USING_CURL` and `ENABLE_ADD_TOOLS_USING_PYTHON` environment variables,
> are no longer available. Entries under the `tools:` section of a unified configuration
> (OpenAPI, `tool_type: curl` or `tool_type: script`) are no longer registered and are
> reported as failed. To expose an OpenAPI-based API, register it as a member server with
> `register_mcp_server` and `"type": "openapi"`.
