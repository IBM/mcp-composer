# Prompt Management in MCP Composer


MCP Composer provides a comprehensive prompt management system that allows you to dynamically add, list, and manage prompts across your MCP infrastructure. The system supports both runtime prompt addition and static prompt loading from configuration files. As part of prompt management in MCP Composer, you will add prompts dynamically, list all registered prompts, get prompts from specific servers, filter prompts based on criteria, and apply safety and validation rules. Among them, add prompts dynamically, list all registered prompts, list prompts per server, and filter prompts are currently supported.

Here is the roadmap for prompt management in MCP Composer:

![prompt_roadmap](/images/prompt_roadmap.png)

P.S - features those are in purple are supported today. 

## Key Functionality

Based on the mind map shown, MCP Composer currently supports the following prompt management operations:

- **Add**: Dynamically add new prompts to the system*  
- **List**: Retrieve all registered prompts*
- **List per Server**: Get prompts from specific servers*
- **Filter**: Filter prompts based on criteria*

The following feature is planned to be implemented:

- **Guardrails**: Apply safety and validation rules

## Core Components

### 1. Prompt Management Tools

MCP Composer exposes four main tools for prompt management:

```python
# Add prompts dynamically
self.add_tool(Tool.from_function(self.add_prompts))

# List all prompts
self.add_tool(Tool.from_function(self.get_all_prompts))

# List prompts per server
self.add_tool(Tool.from_function(self.list_prompts_per_server))

# Filter prompts
self.add_tool(Tool.from_function(self.filter_prompts))
```

### 2. Prompt Management Flow

The following sequence diagram illustrates the flow of prompt management operations:

```mermaid
sequenceDiagram
    participant Client
    participant MCPComposer
    participant PromptManager
    participant MCPServerBuilder
    participant LocalFile
    participant FastMCP

    Note over Client, FastMCP: Dynamic Prompt Addition Flow
    Client->>MCPComposer: add_prompts(prompt_config)
    MCPComposer->>MCPComposer: validate prompt_config
    MCPComposer->>PromptManager: build_prompt_from_dict(entry)
    PromptManager->>PromptManager: create Prompt.from_function()
    PromptManager-->>MCPComposer: Prompt object
    MCPComposer->>FastMCP: super().add_prompt(prompt)
    MCPComposer-->>Client: list of added prompt names

    Note over Client, FastMCP: Static File Loading Flow
    Client->>MCPComposer: setup_member_servers()
    MCPComposer->>MCPServerBuilder: build() for local type
    MCPServerBuilder->>LocalFile: load_json(prompt_path)
    LocalFile-->>MCPServerBuilder: prompt data array
    loop For each prompt entry
        MCPServerBuilder->>PromptManager: build_prompt_from_dict(entry)
        PromptManager-->>MCPServerBuilder: Prompt object
        MCPServerBuilder->>FastMCP: add_prompt(prompt)
    end
    MCPServerBuilder-->>MCPComposer: FastMCP server with prompts
    MCPComposer->>MCPComposer: mount(sub_mcp, server_id)

    Note over Client, FastMCP: List Prompts Flow
    Client->>MCPComposer: get_all_prompts()
    MCPComposer->>FastMCP: get_prompts()
    FastMCP-->>MCPComposer: prompts_dict
    MCPComposer->>MCPComposer: convert to string list
    MCPComposer-->>Client: list of prompt strings

    Note over Client, FastMCP: List Prompts Per Server Flow
    Client->>MCPComposer: list_prompts_per_server(server_id)
    MCPComposer->>PromptManager: list_prompts_per_server(server_id)
    PromptManager->>ServerManager: get_member(server_id)
    ServerManager-->>PromptManager: member server
    PromptManager->>MemberServer: get_prompts()
    MemberServer-->>PromptManager: prompts_dict
    PromptManager->>PromptManager: format prompts with server_id
    PromptManager-->>MCPComposer: list of prompt dicts
    MCPComposer-->>Client: list of prompts with server info

    Note over Client, FastMCP: Filter Prompts Flow
    Client->>MCPComposer: filter_prompts(filter_criteria)
    MCPComposer->>PromptManager: filter_prompts(filter_criteria)
    PromptManager->>PromptManager: collect all prompts from composer and servers
    PromptManager->>PromptManager: apply filter criteria (name, description, tags)
    PromptManager-->>MCPComposer: filtered list of prompt dicts
    MCPComposer-->>Client: filtered prompts
```

### 3. Prompt Structure

Each prompt follows a standardized structure defined in `test/data/prompts.json`:

```json
{
    "name": "prompt_name",
    "description": "Description of what the prompt does",
    "template": "Template string with {{variable}} placeholders",
    "arguments": [
        {
            "name": "variable",
            "type": "string",
            "required": true,
            "description": "Description of the variable"
        }
    ]
}
```

## Adding Prompts

### Method 1: Dynamic Addition via API

You can add prompts dynamically using the `add_prompts` function:

```python
async def add_prompts(self, prompt_config: Union[dict, list[dict]]) -> list[str]:
    """
    Add one or more prompts based on the provided configuration.
    Returns a list of registered prompt names.
    """
    if not isinstance(prompt_config, list):
        raise TypeError("Prompt config must be a dict or a list of dicts")

    added = []
    for entry in prompt_config:
        prompt = await build_prompt_from_dict(entry)
        super().add_prompt(prompt)
        added.append(prompt.name)
    return added
```

#### Example Usage:

```python
# Add a single prompt
prompt_config = [{
    "name": "app_top_errors_yesterday",
    "description": "Show top erroneous calls handled by an application since yesterday",
    "template": "Show top erroneous calls handled by '{{ application }}' application since yesterday",
    "arguments": [
        {
            "name": "application",
            "type": "string",
            "required": true,
            "description": "The name of the application"
        }
    ]
}]

added_prompts = await composer.add_prompts(prompt_config)
print(f"Added prompts: {added_prompts}")
```

### Method 2: Static Loading from Local Files

Prompts can be loaded from local JSON files using the "local" server type:

#### Configuration Example:

```json
{
    "id": "mcp-prompt",
    "type": "local",
    "prompt_path": "./test/data/prompts.json",
    "_id": "mcp-prompt"
}
```

#### Implementation Details:

The local file loading is handled by the `MCPServerBuilder._build_from_local_file()` method:

```python
async def _build_from_local_file(self) -> FastMCP:
    mcp = FastMCP(self.config.get(ConfigKey.ID, ""))
    data = await load_json(self.config[ConfigKey.PROMPT_PATH])
    for entry in data:
        prompt = await build_prompt_from_dict(entry)
        logger.info("Prompt: %s", prompt)
        mcp.add_prompt(prompt)
    return mcp
```

## Listing Prompts

### Get All Prompts

The `get_all_prompts` function retrieves all registered prompts:

```python
async def get_all_prompts(self) -> list[str]:
    """Get all registered prompts mapped to their textual form from composer and mounted servers."""
    prompts_dict = await self._prompt_manager.get_prompts()
    return [str(prompt) for prompt in prompts_dict.values()]
```

#### Example Usage:

```python
# Get all registered prompts
all_prompts = await composer.get_all_prompts()
for prompt in all_prompts:
    print(prompt)
```

### List Prompts Per Server

The `list_prompts_per_server` function retrieves all prompts from a specific server:

```python
async def list_prompts_per_server(self, server_id: str) -> list[dict]:
    """List all prompts from a specific server."""
    return await self._prompt_manager.list_prompts_per_server(server_id)
```

#### Example Usage:

```python
# List prompts from a specific server
prompts = await composer.list_prompts_per_server("my-server")
for prompt in prompts:
    print(f"Prompt: {prompt['name']} from server: {prompt['server_id']}")
```

#### Implementation Details:

The method checks if the server exists and retrieves prompts from the specific server:

```python
async def list_prompts_per_server(self, server_id: str) -> List[Dict]:
    """List all prompts from a specific server."""
    try:
        if not self._server_manager or not self._server_manager.has_member_server(server_id):
            return []

        server = self._server_manager.get_member(server_id)
        if server and hasattr(server, 'server') and server.server:
            prompts = await server.server.get_prompts()
            result = []
            for key, prompt in prompts.items():
                name = getattr(prompt, 'name', key)
                description = getattr(prompt, 'description', '')
                result.append({
                    "name": name,
                    "description": description,
                    "template": str(prompt),
                    "server_id": server_id
                })
            return result
        return []
    except Exception as e:
        logger.error("Error listing prompts for server '%s': %s", server_id, e)
        return []
```

## Filtering Prompts

### Filter Prompts by Criteria

The `filter_prompts` function allows filtering prompts based on various criteria:

```python
async def filter_prompts(self, filter_criteria: dict) -> list[dict]:
    """Filter prompts based on criteria like name, description, tags, etc."""
    return await self._prompt_manager.filter_prompts(filter_criteria)
```

#### Example Usage:

```python
# Filter by name
result = await composer.filter_prompts({"name": "test"})

# Filter by description
result = await composer.filter_prompts({"description": "response"})

# Filter by multiple criteria
result = await composer.filter_prompts({
    "name": "prompt",
    "description": "test"
})
```

#### Implementation Details:

The filtering method collects prompts from both the composer and all mounted servers, then applies the filter criteria:

```python
async def filter_prompts(self, filter_criteria: dict) -> List[Dict]:
    """Filter prompts based on criteria like name, description, tags."""
    try:
        prompts_dict = self._prompts.copy()

        if self._server_manager:
            for server_id, member in self._server_manager._member_servers.items():
                if member.server:
                    try:
                        server_prompts = await member.server.get_prompts()
                        prompts_dict.update(server_prompts)
                    except Exception as e:
                        logger.warning("Error getting prompts from server %s: %s", server_id, e)

        result = []

        for key, prompt in prompts_dict.items():
            match = True
            name = getattr(prompt, 'name', key)
            description = getattr(prompt, 'description', '')
            tags = getattr(prompt, 'tags', [])

            if 'name' in filter_criteria and filter_criteria['name']:
                if filter_criteria['name'].lower() not in name.lower():
                    match = False

            if match and 'description' in filter_criteria and filter_criteria['description']:
                if filter_criteria['description'].lower() not in description.lower():
                    match = False

            if match and 'tags' in filter_criteria and filter_criteria['tags']:
                if not any(tag in tags for tag in filter_criteria['tags']):
                    match = False

            if match:
                result.append({
                    "name": name,
                    "description": description,
                    "template": str(prompt)
                })

        return result
    except Exception as e:
        logger.error("Error filtering prompts: %s", e)
        return []
```

## Removing Prompts

### Remove a Prompt

The `remove_prompt` function removes a specific prompt by name:

```python
async def remove_prompt(self, prompt_name: str) -> str:
    """Remove a specific prompt by name from composer or mounted servers."""
    return await self._prompt_manager.remove_prompt(prompt_name)
```

#### Example Usage:

```python
# Remove a specific prompt
result = await composer.remove_prompt("test_prompt")
print(result)  # "Prompt 'test_prompt' removed successfully" or "Prompt 'test_prompt' not found"
```

## Example Prompts

The system comes with a comprehensive set of pre-defined prompts for common operations:

### Application Monitoring Prompts

```json
{
    "name": "app_top_errors_yesterday",
    "description": "Show top erroneous calls handled by an application since yesterday",
    "template": "Show top erroneous calls handled by '{{ application }}' application since yesterday",
    "arguments": [
        {
            "name": "application",
            "type": "string",
            "required": true,
            "description": "The name of the application"
        }
    ]
}
```

### Performance Monitoring Prompts

```json
{
    "name": "promo_http_avg_response",
    "description": "Average response time of promo HTTP calls handled by a cluster",
    "template": "What is the average response time of promo HTTP calls handled by Kubernetes cluster {{ cluster }}?",
    "arguments": [
        {
            "name": "cluster",
            "type": "string",
            "required": true,
            "description": "The name of the Kubernetes cluster"
        }
    ]
}
```

### Infrastructure Monitoring Prompts

```json
{
    "name": "queue_depth_check",
    "description": "Current queue depth of a given AMQ queue",
    "template": "What is the current queue depth of {{ queue_name }} from the queue manager running on namespace {{ namespace }}?",
    "arguments": [
        {
            "name": "queue_name",
            "type": "string",
            "required": true,
            "description": "The name of the AMQ queue"
        },
        {
            "name": "namespace",
            "type": "string",
            "required": true,
            "description": "The namespace of the queue manager"
        }
    ]
}
```

## Testing Prompt Management

### Unit Tests

The system includes comprehensive unit tests for prompt management:

```python
@pytest.mark.asyncio
async def test_add_prompts():
    composer = MCPComposer("composer")
    config = [{
        "name": "promo_http_avg_response",
        "description": "Average response time of promo HTTP calls handled by a cluster",
        "template": "What is the average response time of promo HTTP calls handled by Kubernetes cluster {{ cluster }}?",
        "arguments": [
            {
                "name": "cluster",
                "type": "string",
                "required": "true",
                "description": "The name of the Kubernetes cluster"
            }
        ]
    }]
    res = await composer.add_prompts(config)     
    assert len(res) == 1, "Composer should return a dictionary of prompts"
```

### Integration Tests

```python
@pytest.mark.asyncio
async def test_builder_local():    
    config = [{
        "id": "mcp-prompt",
        "type": "local",
        "prompt_path": "./test/data/prompts.json"
    }]
    composer = MCPComposer("composer")
    await composer.setup_member_servers()
    prompts = await composer.get_all_prompts()
    assert len(prompts) == 16, "Composer should return 16 prompts from local file"
    assert isinstance(prompts, list), "Should return a list of prompts"
```

### Filter Tests

```python
@pytest.mark.asyncio
async def test_filter_prompts():
    """Test filtering prompts by criteria."""
    composer = MCPComposer("test-composer")

    # Add test prompts
    prompt_config = [
        {
            "name": "test_prompt_1",
            "description": "First test prompt",
            "template": "Template 1"
        },
        {
            "name": "test_prompt_2",
            "description": "Second test prompt",
            "template": "Template 2"
        },
        {
            "name": "another_prompt",
            "description": "Another prompt",
            "template": "Template 3"
        }
    ]

    composer.add_prompts(prompt_config)

    # Test filtering by name
    result = await composer.filter_prompts({"name": "test"})
    assert len(result) == 2
    assert any(r["name"] == "test_prompt_1" for r in result)
    assert any(r["name"] == "test_prompt_2" for r in result)

    # Test filtering by description
    result = await composer.filter_prompts({"description": "First"})
    assert len(result) == 1
    assert result[0]["name"] == "test_prompt_1"

    # Test filtering with no matches
    result = await composer.filter_prompts({"name": "nonexistent"})
    assert len(result) == 0
```

### List Per Server Tests

```python
@pytest.mark.asyncio
async def test_list_prompts_per_server():
    """Test listing prompts from a specific server."""
    composer = MCPComposer("test-composer")

    # Mock server manager to return a mock server
    mock_server = MagicMock()
    mock_server.server = MagicMock()

    # Create proper mock prompts
    mock_prompt1 = MagicMock()
    mock_prompt1.name = "prompt1"
    mock_prompt1.description = "Test prompt 1"

    mock_prompt2 = MagicMock()
    mock_prompt2.name = "prompt2"
    mock_prompt2.description = "Test prompt 2"

    mock_server.server.get_prompts = AsyncMock(return_value={
        "prompt1": mock_prompt1,
        "prompt2": mock_prompt2
    })

    composer._server_manager.has_member_server = MagicMock(return_value=True)
    composer._server_manager.get_member = MagicMock(return_value=mock_server)

    result = await composer.list_prompts_per_server("test-server")
    assert len(result) == 2
    assert result[0]["name"] == "prompt1"
    assert result[1]["name"] == "prompt2"
    assert result[0]["server_id"] == "test-server"
```

## API Endpoints

### REST API Support

MCP Composer also exposes prompt management through REST endpoints:

#### Add Prompts

```http
POST /mcp/tools/add_prompts
Content-Type: application/json

{
  "arguments": {
    "prompt_config": [
      {
        "name": "prompt_name",
        "description": "Prompt description",
        "template": "Template with {{variable}}",
        "arguments": [
          {
            "name": "variable",
            "type": "string",
            "required": true,
            "description": "Variable description"
          }
        ]
      }
    ]
  }
}
```

#### Get All Prompts

```http
POST /mcp/tools/get_all_prompts
Content-Type: application/json

{
  "arguments": {}
}
```

#### List Prompts Per Server

```http
POST /mcp/tools/list_prompts_per_server
Content-Type: application/json

{
  "arguments": {
    "server_id": "my-server"
  }
}
```

#### Filter Prompts

```http
POST /mcp/tools/filter_prompts
Content-Type: application/json

{
  "arguments": {
    "filter_criteria": {
      "name": "test",
      "description": "response"
    }
  }
}
```

## Best Practices

### 1. Prompt Naming

- Use descriptive, lowercase names with underscores
- Include the domain/context in the name (e.g., `app_`, `cluster_`, `jvm_`)

### 2. Template Design

- Use clear, natural language templates
- Include all required variables with `{{ variable_name }}` syntax
- Provide meaningful descriptions for each argument

### 3. Argument Validation

- Always specify `required: true` for mandatory arguments
- Use appropriate types (`string`, `integer`, `boolean`)
- Provide clear descriptions for each argument

### 4. Error Handling

- Templates should handle missing arguments gracefully
- Use try-catch blocks in prompt functions when appropriate

### 5. Filtering Best Practices

- Use case-insensitive filtering for better user experience
- Combine multiple criteria for more precise filtering
- Consider performance when filtering large numbers of prompts

### 6. Server-Specific Operations

- Always verify server existence before listing prompts
- Handle server connection errors gracefully
- Include server_id in results for clarity

## Configuration Files

### Prompt Servers Configuration

Location: `test/data/prompt_servers.json`

```json
[
  {
    "id": "mcp-prompt",
    "type": "local",
    "prompt_path": "./src/mcp-composer/test/data/prompts.json",
    "_id": "mcp-prompt"
  }
]
```

### Prompts Data

Location: `test/data/prompts.json`

Contains 16 pre-defined prompts covering:
- Application monitoring
- Performance analysis
- Infrastructure checks
- Security assessments
- Cost optimization

## Conclusion

MCP Composer's prompt management system provides a flexible and powerful way to handle dynamic prompt creation and management. The current implementation supports adding prompts both dynamically and through static configuration files, with comprehensive listing capabilities including server-specific listing and filtering functionality. The system is designed to be extensible, allowing for future enhancements like advanced guardrails and validation rules. 