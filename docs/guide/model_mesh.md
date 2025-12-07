# Model Mesh Tool - Complete Guide

A comprehensive guide to the Model Mesh Tool, a configurable small-model mesh MCP tool that routes prompts to specialized models based on task type.

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Provider Communication](#provider-communication)
4. [Task-to-Model Mapping](#task-to-model-mapping)
5. [Configuration](#configuration)
6. [Usage Examples](#usage-examples)
7. [Response Format](#response-format)
8. [Troubleshooting](#troubleshooting)

---

## Overview

The Model Mesh Tool implements a small-model mesh architecture where different models are configured for specific tasks:
- **Guardian tasks** → Content safety and moderation models (e.g., `ibm/granite3.3-guardian:8b`)
- **Vision tasks** → Vision-specialized models (e.g., `ibm/granite3.2-vision`)
- **Speech recognition tasks** → Speech models (e.g., `whisper`)
- **Text tasks** → General-purpose text models (e.g., `llama2`)

Models are accessed via configurable providers (LiteLLM by default, Ollama as alternative).

### Features

- ✅ Task-based model routing
- ✅ JSON prompt configuration file support
- ✅ Direct prompt input support
- ✅ Configurable model providers (LiteLLM, Ollama)
- ✅ Provider adapter pattern for extensibility
- ✅ Configurable temperature and max_tokens
- ✅ Model override capability
- ✅ Template variable substitution
- ✅ Graceful error handling (warns but doesn't fail if models unavailable)

### Prerequisites

1. **Install providers:**
   ```bash
   pip install litellm  # For LiteLLM provider (default)
   pip install ollama   # For Ollama provider (optional)
   ```

2. **Install and run Ollama:**
   ```bash
   # Install Ollama (if not already installed)
   # Visit: https://ollama.ai/
   
   # Start Ollama server
   ollama serve
   
   # Pull required models
   ollama pull ibm/granite3.3-guardian:8b
   ollama pull ibm/granite3.2-vision
   ```

---

## Architecture

### System Architecture

```
User Request
    ↓
ModelMeshTool.run()
    ↓
Task Type Detection (guardian/vision/text/speech)
    ↓
Model Selection (from model_config)
    ↓
Provider Detection (from model_config JSON)
    ↓
┌─────────────────┬──────────────────┐
│   LiteLLM       │  ollama-python   │
│   Provider      │  Provider        │
│   (default)     │  (direct)        │
│                 │                  │
│  litellm.       │  AsyncClient()   │
│  acompletion()  │  .chat()         │
└─────────────────┴──────────────────┘
    ↓                    ↓
Ollama API          Ollama API
    ↓                    ↓
Specialized Model   Specialized Model
    ↓                    ↓
Response            Response
```

### Provider Adapter Pattern

The Model Mesh Tool uses a provider adapter pattern for flexibility:

- **Base Adapter Interface**: `ModelProviderAdapter` - Abstract base class
- **LiteLLM Adapter**: `LiteLLMAdapter` - Uses LiteLLM library
- **Ollama Adapter**: `OllamaAdapter` - Uses ollama-python library directly
- **Provider Factory**: `ModelProviderFactory` - Creates adapters based on configuration

This architecture allows:
- Easy addition of new providers
- Provider-specific feature access (e.g., `think=True` for Ollama)
- Graceful fallback between providers
- Consistent interface across providers

---

## Provider Communication

### Provider Selection

The tool supports two providers:

#### 1. LiteLLM Provider (Default)
- **Library**: `litellm`
- **Format**: `ollama/model_name`
- **Usage**: `litellm.acompletion(model="ollama/llava", ...)`
- **Pros**: Unified interface, supports many providers
- **Cons**: May not support all provider-specific features

#### 2. Ollama-Python Provider (Direct)
- **Library**: `ollama` (from ollama-python)
- **Format**: Direct model name (e.g., `ibm/granite3.3-guardian:8b`)
- **Usage**: `AsyncClient().chat(model="ibm/granite3.3-guardian:8b", think=True, ...)`
- **Pros**: Full access to Ollama-specific features (think, streaming, etc.)
- **Cons**: Ollama-specific only

### How Communication Works

#### When Provider is "ollama"

When `provider: "ollama"` is specified, the tool uses the **ollama-python** library directly via `AsyncClient`:

```python
# Internal implementation
from ollama import AsyncClient

client = AsyncClient(host=base_url)

response = await client.chat(
    model="ibm/granite3.3-guardian:8b",
    think=True,  # From config options
    messages=[
        {
            "role": "user",
            "content": prompt
        }
    ],
    options={
        "temperature": 0  # From config options
    }
)
```

#### When Provider is "litellm"

When `provider: "litellm"` is specified (or default), the tool uses LiteLLM:

```python
# Internal implementation
import litellm

response = await litellm.acompletion(
    model="ollama/llava",
    messages=[
        {
            "role": "user",
            "content": prompt
        }
    ],
    temperature=temperature,
    max_tokens=max_tokens
)
```

### Options Priority

Provider-specific options are merged in priority order:
1. **Runtime arguments** (highest priority) - from `tool.run()` call
2. **Model config options** - from `model_config[task]["options"]`
3. **Default values** (lowest priority) - tool defaults

Example:
```python
# Config
{
    "guardian": {
        "options": {"temperature": 0, "think": True}
    }
}

# Runtime call
await tool.run({
    "task": "guardian",
    "temperature": 0.1  # Overrides config
})

# Final options: {"temperature": 0.1, "think": True}
# (temperature from runtime, think from config)
```

---

## Task-to-Model Mapping

### Mapping Architecture

```
User Request
    ↓
tool.run({"task": "vision", ...})
    ↓
Task Parameter Extraction ("vision")
    ↓
Lookup in model_config Dictionary
    ↓
    model_config = {
        "vision": {...},    ← Matches task="vision"
        "guardian": {...},
        "text": {...}
    }
    ↓
Get Model Configuration
    ↓
Route to Appropriate Model & Provider
```

### How the Mapping Works

The `model_config` dictionary maps **task names** to **model configurations**:

```python
model_config = {
    "vision": {                    # Task name
        "model": "ibm/granite3.2-vision",  # Model to use
        "provider": "ollama",
        "options": {...}
    },
    "guardian": {                  # Task name
        "model": "ibm/granite3.3-guardian:8b",  # Model to use
        "provider": "ollama",
        "options": {
            "think": True,
            "temperature": 0
        }
    },
    "text": {                      # Task name
        "model": "llama2",         # Model to use
        "provider": "litellm"
    }
}
```

### Routing Logic

When you call the tool:

```python
await tool.run({
    "task": "vision",  # ← This determines which model to use
    "prompt": "..."
})
```

The tool:
1. Extracts the `task` parameter: `"vision"`
2. Looks up `model_config.get("vision")` → finds model configuration
3. Routes to that model with the specified provider and options

### Task Name Convention

Task names are **case-insensitive** and can be any string. Common conventions:

- **Task type**: `"vision"`, `"speech"`, `"text"`, `"guardian"`
- **Model-specific**: `"granite-vision"`, `"granite-guardian"`
- **Use case**: `"image-analysis"`, `"safety-check"`, `"transcription"`

```python
# All of these work the same way:
await tool.run({"task": "vision", ...})
await tool.run({"task": "Vision", ...})      # Case-insensitive
await tool.run({"task": "VISION", ...})      # Case-insensitive
```

### Model Override

You can override the model selection at runtime:

```python
# Config has: "vision" → "llava"
# Runtime override:
await tool.run({
    "task": "vision",
    "model_override": "ibm/granite3.2-vision",  # Overrides config
    "prompt": "..."
})
```

---

## Configuration

### Model Configuration Structure

#### Simple Configuration (Backward Compatible)
```python
model_config = {
    "vision": "llava",
    "speech": "whisper",
    "text": "llama2"
}
```
This uses LiteLLM by default with format `ollama/model_name`.

#### Enhanced Configuration (Provider-Based)
```json
{
  "guardian": {
    "model": "ibm/granite3.3-guardian:8b",
    "provider": "ollama",
    "base_url": "http://localhost:11434",
    "options": {
      "think": true,
      "temperature": 0
    }
  },
  "vision": {
    "model": "ibm/granite3.2-vision",
    "provider": "ollama",
    "base_url": "http://localhost:11434"
  },
  "text": {
    "model": "llama2",
    "provider": "litellm",
    "base_url": "http://localhost:11434"
  }
}
```

### Basic Setup

```python
from mcp_composer.core.tools.model_mesh_tool import ModelMeshTool

model_mesh_tool = ModelMeshTool({
    "name": "model_mesh",
    "prompt_config_path": "./example/model_mesh_prompts.json",
    "model_config": {
        "guardian": {
            "model": "ibm/granite3.3-guardian:8b",
            "provider": "ollama",
            "options": {
                "think": True,
                "temperature": 0
            }
        },
        "vision": {
            "model": "ibm/granite3.2-vision",
            "provider": "ollama"
        }
    },
    "base_url": "http://localhost:11434",
    "default_provider": "litellm"
})
```

### Prompt Configuration File

Create a JSON file with prompt templates:

```json
{
  "guardian_content_safety": {
    "template": "Analyze the following content for safety: {content}",
    "description": "Template for content safety assessment",
    "task_type": "guardian"
  },
  "vision_analysis": {
    "template": "Analyze the following image: {image_description}. Focus on: {focus_areas}",
    "description": "Template for vision analysis",
    "task_type": "vision"
  }
}
```

### Configuration Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | No | Tool name (default: "model_mesh") |
| `prompt_config_path` | string | No | Path to JSON file with prompt templates |
| `model_config` | dict | Yes | Dictionary mapping task types to model configurations |
| `base_url` | string | No | Base URL for model API (default: http://localhost:11434) |
| `default_provider` | string | No | Default provider to use (default: "litellm") |

### Model Config Structure

Each task in `model_config` can be:

1. **Simple string** (backward compatible):
   ```python
   "vision": "llava"  # Uses default provider (litellm)
   ```

2. **Dictionary with provider**:
   ```python
   "guardian": {
       "model": "ibm/granite3.3-guardian:8b",  # Required
       "provider": "ollama",                    # Required: "litellm" or "ollama"
       "base_url": "http://localhost:11434",   # Optional
       "options": {                             # Optional, model-specific options
           "think": True,
           "temperature": 0
       }
   }
   ```

---

## Usage Examples

### Using Prompt Templates from JSON

```python
result = await model_mesh_tool.run({
    "task": "guardian",
    "prompt_key": "guardian_content_safety",
    "prompt_variables": {
        "content": "Hello, this is a test message"
    }
})
```

### Using Direct Prompts

```python
result = await model_mesh_tool.run({
    "task": "guardian",
    "prompt": "Analyze this content for safety: 'Hello world'",
    "temperature": 0
})
```

### Overriding Model Selection

```python
result = await model_mesh_tool.run({
    "task": "vision",
    "prompt": "Describe this image.",
    "model_override": "llava:13b"  # Use specific model variant
})
```

### Complete Example: Guardian Model

```python
import asyncio
from mcp_composer.core.tools.model_mesh_tool import ModelMeshTool

async def main():
    # Configure with Guardian model using ollama provider
    tool = ModelMeshTool({
        "name": "model_mesh",
        "model_config": {
            "guardian": {
                "model": "ibm/granite3.3-guardian:8b",
                "provider": "ollama",
                "base_url": "http://localhost:11434",
                "options": {
                    "think": True,
                    "temperature": 0
                }
            }
        }
    })
    
    # Use the tool
    result = await tool.run({
        "task": "guardian",
        "prompt": "hello world"
    })
    
    # Print result
    print(result.content[0].text)

if __name__ == "__main__":
    asyncio.run(main())
```

This will internally call:
```python
from ollama import AsyncClient

client = AsyncClient(host="http://localhost:11434")
response = await client.chat(
    model="ibm/granite3.3-guardian:8b",
    think=True,
    messages=[{"role": "user", "content": "hello world"}],
    options={"temperature": 0}
)
```

### Integration with MCP Composer

```python
from mcp_composer import MCPComposer
from mcp_composer.core.tools.model_mesh_tool import ModelMeshTool

composer = MCPComposer("my-composer")
composer.disable_composer_tool()  # Optional

model_mesh_tool = ModelMeshTool({
    "name": "model_mesh",
    "prompt_config_path": "./config/prompts.json",
    "model_config": {
        "guardian": {
            "model": "ibm/granite3.3-guardian:8b",
            "provider": "ollama",
            "options": {"think": True, "temperature": 0}
        },
        "vision": {
            "model": "ibm/granite3.2-vision",
            "provider": "ollama"
        }
    }
})

composer.add_tool(model_mesh_tool)
await composer.setup_member_servers()
```

---

## Tool Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `task` | string | Yes | Task type (e.g., 'guardian', 'vision', 'text', 'speech'). Determines which model will be used. |
| `prompt` | string | No* | Direct prompt text |
| `prompt_key` | string | No* | Key to look up in prompt config file |
| `prompt_variables` | object | No | Variables for template substitution |
| `model_override` | string | No | Override model selection |
| `temperature` | number | No | Generation temperature (0.0-2.0, default: 0.7) |
| `max_tokens` | integer | No | Max tokens to generate (default: 1000) |

*Either `prompt` or `prompt_key` must be provided.

### Task Parameter Details

The `task` parameter is critical - it determines which model and capability is used:

- **'guardian'**: Use for content safety, toxicity detection, policy compliance, risk assessment, and content moderation. Examples: 'check if content is safe', 'is this toxic?', 'does this comply with policy?', 'assess risk level', 'should I moderate this?'
- **'vision'**: Use for image analysis, object detection, and visual content analysis. Examples: 'analyze this image', 'what objects are in this scene?'
- **'text'**: Use for text summarization, question answering, and general text processing. Examples: 'summarize this text', 'answer this question based on context'
- **'speech'**: Use for audio transcription and speech sentiment analysis. Examples: 'transcribe this audio', 'analyze speech sentiment'

**IMPORTANT**: For content safety, toxicity checks, moderation, or policy compliance, ALWAYS use `task='guardian'`, NOT `task='text'`.

---

## Response Format

The tool returns a JSON response with comprehensive information:

```json
{
  "status": "success",
  "task": "guardian",
  "model": "ibm/granite3.3-guardian:8b",
  "provider": "ollama",
  "prompt": "Analyze this content for safety: 'Hello world'",
  "response": "Model response text...",
  "capability": {
    "task_type": "guardian",
    "description": "Content Safety & Moderation - Analyzes content for safety, toxicity, policy compliance, and risk assessment",
    "prompt_template": "guardian_content_safety",
    "model_used": "ibm/granite3.3-guardian:8b",
    "provider_used": "ollama"
  },
  "usage": {
    "prompt_tokens": 50,
    "completion_tokens": 100,
    "total_tokens": 150
  },
  "system_prompt": "...",
  "guardrails": [...]
}
```

### Response Fields

- **status**: "success" or "error"
- **task**: The task type that was used
- **model**: The model name that was used/attempted
- **provider**: The provider that was used/attempted
- **capability**: Object containing:
  - `task_type`: The task type
  - `description`: Human-readable description of the capability
  - `prompt_template`: Which prompt template was used (or "direct_prompt")
  - `model_used` / `model_attempted`: The model that was used or attempted
  - `provider_used` / `provider_attempted`: The provider that was used or attempted
- **response**: The model's response text (if successful)
- **usage**: Token usage information (if available)
- **error**: Error message (if status is "error")
- **suggestion**: Helpful suggestions for fixing errors

---

## Troubleshooting

### Model Not Found

If you get an error about a model not being found:
1. Ensure Ollama is running: `ollama serve`
2. Check available models: `ollama list`
3. Pull the required model: `ollama pull <model_name>`

**Note**: The tool will show warnings but continue to work with available models. If a model is unavailable, you'll get a graceful error message with suggestions.

### Provider Not Available

1. **Install required packages:**
   ```bash
   pip install litellm  # For LiteLLM provider
   pip install ollama   # For Ollama provider
   ```

2. **Check provider availability:**
   ```python
   from mcp_composer.core.tools.model_providers import ModelProviderFactory
   
   print(ModelProviderFactory.is_provider_available("litellm"))
   print(ModelProviderFactory.is_provider_available("ollama"))
   ```

### Prompt Config Not Found

- Ensure the path to `prompt_config_path` is correct (relative or absolute)
- Check that the JSON file is valid

### Wrong Task Type Selected

If Claude is selecting the wrong task type (e.g., using "text" for toxicity checks):

1. **Check tool description** - The tool description should clearly indicate that safety/moderation tasks use "guardian"
2. **Verify configuration** - Ensure guardian model is configured correctly
3. **Review prompts** - Use natural language that clearly indicates the task type

### Graceful Error Handling

The tool is designed to handle unavailable models gracefully:

- **During initialization**: Shows warnings but doesn't fail
- **During execution**: Returns helpful error messages instead of crashing
- **Model validation**: Checks model configurations and warns about issues
- **Provider fallback**: Attempts to fall back to default provider if configured provider is unavailable

---

## Benefits of Provider-Based Architecture

1. **Flexibility**: Choose the best provider for each model
2. **Feature Access**: Use provider-specific features (e.g., `think=True` for Guardian)
3. **Performance**: Direct provider access can be more efficient
4. **Backward Compatible**: Simple string configs still work
5. **Extensible**: Easy to add new providers (OpenAI, Anthropic, etc.)
6. **Graceful Degradation**: Works even if some models are unavailable

## Future Enhancements

- Support for more providers (OpenAI, Anthropic, etc.)
- Provider-specific authentication
- Connection pooling per provider
- Provider health checks
- Automatic failover between providers

---

## Best Practices

1. **Use descriptive task names**: `"vision"`, `"guardian"`, `"text"` are clearer than `"task1"`, `"task2"`
2. **Group related models**: Keep related models in the same tool configuration
3. **Document your mappings**: Add comments explaining which model handles which task
4. **Use consistent naming**: Follow a naming convention (e.g., all lowercase, kebab-case)
5. **Configure providers appropriately**: Use Ollama provider for models that need Ollama-specific features (like `think=True`)
6. **Handle errors gracefully**: The tool will warn about unavailable models - check logs for warnings

---

## Complete Flow Diagram

```
┌─────────────────────────────────────────────────────────┐
│  User Call: tool.run({"task": "guardian", ...})         │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│  Extract task parameter: "guardian"                      │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│  Lookup in model_config:                                │
│  model_config.get("guardian")                            │
│  → {"model": "ibm/granite3.3-guardian:8b", ...}         │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│  Get model configuration:                                │
│  - model: "ibm/granite3.3-guardian:8b"                   │
│  - provider: "ollama"                                    │
│  - options: {"think": True, "temperature": 0}            │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│  Get provider adapter via ModelProviderFactory          │
│  → Creates OllamaAdapter                                 │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│  Call adapter.chat()                                     │
│  → AsyncClient().chat(                                   │
│      model="ibm/granite3.3-guardian:8b",                 │
│      think=True,                                         │
│      options={"temperature": 0}                         │
│    )                                                     │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│  Format response with capability information             │
│  - model_used                                            │
│  - provider_used                                         │
│  - capability description                                │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│  Return response                                         │
└─────────────────────────────────────────────────────────┘
```

---

## Key Points Summary

1. **Task-Based Routing**: The `task` parameter determines which model configuration to use
2. **Provider Adapters**: Uses adapter pattern for flexible provider support
3. **Graceful Degradation**: Works even if some models are unavailable (shows warnings)
4. **Capability Information**: Response includes which model and capability was used
5. **Options Merging**: Runtime options override config options
6. **Backward Compatible**: Simple string configs still work (defaults to LiteLLM)
7. **Natural Language**: Tool description guides Claude to use correct task types
