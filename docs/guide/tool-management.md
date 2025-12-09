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

- **`add_tools_from_curl`**: Add tools using a cURL command.
- **`add_tools_from_python`**: Add tools using Python script.
- **`add_tools_from_openapi`**: Add tools using OpenAPI specifications.

## 🚀 Adding Dynamic Tools into MCP Composer

Learn how to add dynamic tools to MCP Composer.

### 🔧 Three Ways to Add Tools

MCP Composer currently supports **three flexible methods** for integrating tools:

---

#### 1. 🧩 Using a cURL Command

You can create a tool by simply providing a cURL command in a structured format.  
Use `add_tools_from_curl()`.

```python
curl_config = {
    "name": "event",
    "tool_type": "curl",
    "curl_config": {
        "value": "curl 'https://www.example.com/api' --header 'Authorization: Bearer XXXXXXXX'"
    },
    "description": "sample test",
    "permission": {
        "role 1": "permission 1 "
    }
}

# Add custom tools from curl command
await composer.add_tools_from_curl(curl_config)
```

- **Fields required**: `name`, `tool_type`, and `curl_config`
- **✅ Supports**: Both authenticated and unauthenticated APIs

---

#### 2. 🐍 Using a Python Script

You can use `add_tools_from_python()` to add tools using Python functions as strings.  
*Example Function*: A search tool fetching the top 5 articles about a stock market company.

NOTE: To enable this feature add `ENABLE_ADD_TOOLS_USING_PYTHON=True` in .env

```python
py_script = {
    "name": "test",
    "tool_type": "script",
    "script_config": {
        "value": "def search_news(keyword: str) -> str:\n    '''Simulate news search using a ticker and return top articles.'''\n    import yfinance as yf\n    import json\n    stock = yf.Ticker(keyword.upper())\n    news = stock.news[:5]\n    result = []\n    for article in news:\n        result.append({\n            'title': article.get('title'),\n            'publisher': article.get('publisher'),\n            'link': article.get('link'),\n            'providerPublishTime': article.get('providerPublishTime'),\n        })\n    return json.dumps(result, indent=2)"
    },
    "description": "Search top 5 news articles related to a stock ticker using yfinance.",
    "permission": {
        "role 1": "permission 1"
    }
}
# Add custom tools from Python scripts
await composer.add_tools_from_python(py_script)
```

- **Fields required**: `name`, `tool_type`, and `script_config`

---

#### 3. 📘 Using OpenAPI Specification

Auto-generate tools from OpenAPI spec using `add_tools_from_openapi()`

```python
openapi_spec = {
  "openapi": "3.0.1",
  "info": {
    "title": "IBM Concert API v1.1.0",
    "version": "1.1.0",
    ...
    ...
  }
}
auth_config = {
  "auth_strategy": "basic",
  "auth": {
    "username": "user1",
    "password": "xxxxxxxx"
  }
}
# Add tools from OpenAPI specifications
await composer.add_tools_from_openapi(
    openapi_spec=openapi_spec,
    auth_config=auth_config
)
```

- **Fields required**: OpenAPI spec + optional `auth_config`

## 🗂️ Where Are These Tools Stored?

Currently, all dynamically created tools are stored in a **custom tools folder** within the MCP Composer. However, there's a roadmap to move this storage to **databases or S3** for better scalability and management.
