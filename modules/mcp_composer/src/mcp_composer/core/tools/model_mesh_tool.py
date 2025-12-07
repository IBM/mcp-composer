# model_mesh_tool.py

"""
Model Mesh Tool - A configurable small-model mesh MCP tool.

This tool routes prompts to specialized models based on task type (e.g., vision, speech).
It uses configurable model providers (LiteLLM by default, Ollama as alternative).

Features:
- Load prompts from JSON configuration files
- Task-based model routing (vision -> vision model, speech -> speech model)
- Configurable model providers (LiteLLM, Ollama)
- Provider adapter pattern for extensibility
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, List

from pydantic import BaseModel, Field, ConfigDict, ValidationError, PrivateAttr

from fastmcp.tools.tool import ToolResult

from mcp_composer.core.tools.base_specialised_tool import BaseSpecializedTool
from mcp_composer.core.tools.model_providers import (
    ModelProviderAdapter,
    ModelProviderFactory,
    DEFAULT_PROVIDER,
)
from mcp_composer.core.utils import LoggerFactory

logger = LoggerFactory.get_logger()


class ModelMeshInput(BaseModel):
    """Input parameters for Model Mesh Tool"""
    
    model_config = ConfigDict(extra="forbid")
    
    task: str = Field(
        ...,
        description=(
            "The task type that determines which specialized model will be used. "
            "Available task types:\n"
            "- 'guardian': Use for content safety, toxicity detection, policy compliance, "
            "risk assessment, and content moderation. Examples: 'check if content is safe', "
            "'is this toxic?', 'does this comply with policy?', 'assess risk level', "
            "'should I moderate this?'\n"
            "- 'vision': Use for image analysis, object detection, and visual content analysis. "
            "Examples: 'analyze this image', 'what objects are in this scene?'\n"
            "- 'text': Use for text summarization, question answering, and general text processing. "
            "Examples: 'summarize this text', 'answer this question based on context'\n"
            "- 'speech': Use for audio transcription and speech sentiment analysis. "
            "Examples: 'transcribe this audio', 'analyze speech sentiment'\n"
            "\n"
            "IMPORTANT: For content safety, toxicity checks, moderation, or policy compliance, "
            "ALWAYS use task='guardian', NOT task='text'."
        )
    )
    
    prompt: Optional[str] = Field(
        None,
        description="The prompt to send to the model. If not provided, "
                   "will use the prompt template from the JSON config file."
    )
    
    prompt_key: Optional[str] = Field(
        None,
        description="Key to look up prompt template in the JSON config file. "
                   "Required if prompt is not provided directly."
    )
    
    prompt_variables: Optional[Dict[str, Any]] = Field(
        None,
        description="Variables to substitute in the prompt template (if using prompt_key)."
    )
    
    model_override: Optional[str] = Field(
        None,
        description="Optional override to use a specific model instead of the task-based routing."
    )
    
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Temperature for model generation (0.0-2.0)."
    )
    
    max_tokens: int = Field(
        default=1000,
        ge=1,
        description="Maximum number of tokens to generate."
    )


class ModelMeshTool(BaseSpecializedTool):
    """
    Model Mesh Tool for routing prompts to specialized models based on task type.
    
    This tool implements a small-model mesh architecture where different models
    are configured for specific tasks (e.g., vision, speech recognition).
    Models are accessed via configurable providers (LiteLLM by default, Ollama as alternative).
    
    Configuration:
        - prompt_config_path: Path to JSON file containing prompt configurations
        - model_config: Dictionary mapping task types to model configurations
        - base_url: Base URL for model API (default: http://localhost:11434)
        - default_provider: Default provider to use (default: "litellm")
    
    Example usage:
        tool = ModelMeshTool({
            "name": "model_mesh",
            "prompt_config_path": "./config/prompts.json",
            "model_config": {
                "vision": {
                    "model": "llava",
                    "provider": "litellm"
                },
                "guardian": {
                    "model": "ibm/granite3.3-guardian:8b",
                    "provider": "ollama",
                    "options": {"think": True, "temperature": 0}
                }
            },
            "base_url": "http://localhost:11434",
            "default_provider": "litellm"
        })
    """
    
    model_config = ConfigDict(extra="allow")
    
    # Private attributes
    _prompt_config: Dict[str, Any] = PrivateAttr(default_factory=dict)
    _model_config: Dict[str, Any] = PrivateAttr(default_factory=dict)  # Can be string or dict
    _base_url: str = PrivateAttr(default="http://localhost:11434")
    _default_provider: str = PrivateAttr(default=DEFAULT_PROVIDER)
    _provider_cache: Dict[str, ModelProviderAdapter] = PrivateAttr(default_factory=dict)
    
    def __init__(self, config: Optional[dict] = None):
        """
        Initialize the Model Mesh Tool.
        
        Args:
            config: Configuration dictionary containing:
                - name: Tool name (optional)
                - prompt_config_path: Path to JSON file with prompt configurations
                - model_config: Dictionary mapping task types to model configurations
                - base_url: Base URL for model API (optional, defaults to http://localhost:11434)
                - default_provider: Default provider to use (optional, defaults to "litellm")
        """
        # Check for available providers (warn but don't fail)
        litellm_available = ModelProviderFactory.is_provider_available("litellm")
        ollama_available = ModelProviderFactory.is_provider_available("ollama")
        
        if not litellm_available and not ollama_available:
            logger.warning(
                "No model providers are available. ModelMeshTool will initialize but may not work. "
                "Please install at least one provider: pip install litellm OR pip install ollama"
            )
        else:
            available_providers = []
            if litellm_available:
                available_providers.append("litellm")
            if ollama_available:
                available_providers.append("ollama")
            logger.info(f"Available providers: {', '.join(available_providers)}")
        
        # Generate parameters from Pydantic model
        parameters = ModelMeshInput.model_json_schema()
        
        description = """
        Model Mesh Tool - Routes prompts to specialized models based on task type.
        
        This tool implements a small-model mesh architecture where different models
        are configured for specific tasks:
        
        TASK TYPE SELECTION GUIDE:
        
        1. **'guardian'** - Content Safety & Moderation
           Use for: content safety checks, toxicity detection, policy compliance, 
           risk assessment, content moderation decisions.
           Examples: "check if content is safe", "is this toxic?", "does this comply?", 
           "assess risk", "should I moderate this?"
           
        2. **'vision'** - Image Analysis
           Use for: image analysis, object detection, visual content understanding.
           Examples: "analyze this image", "what objects are in this scene?"
           
        3. **'text'** - Text Processing
           Use for: text summarization, question answering, general text analysis.
           Examples: "summarize this text", "answer this question"
           
        4. **'speech'** - Audio Processing
           Use for: audio transcription, speech sentiment analysis.
           Examples: "transcribe this audio", "analyze speech sentiment"
        
        CRITICAL: For ANY content safety, toxicity, moderation, or policy-related requests,
        you MUST use task='guardian', NOT task='text'. The guardian model is specifically
        designed for safety and moderation tasks.
        
        Models are accessed via configurable providers (LiteLLM by default, Ollama as alternative).
        The tool can load prompt templates from a JSON configuration file, or accept
        prompts directly.
        
        The tool automatically routes requests to the appropriate specialized model based on
        the task type you specify.
        """
        
        # Get tool name from config
        tool_name = self._get_tool_name(config, default="model_mesh")
        
        # Initialize parent
        super().__init__(
            name=tool_name,
            description=description,
            parameters=parameters,
            config=config
        )
        
        # Load configuration
        if config:
            # Load prompt configuration from JSON file
            prompt_config_path = config.get("prompt_config_path")
            if prompt_config_path:
                self._load_prompt_config(prompt_config_path)
            
            # Load model configuration
            self._model_config = config.get("model_config", {})
            
            # Set base URL (support both old "ollama_base_url" and new "base_url")
            self._base_url = config.get("base_url") or config.get("ollama_base_url", "http://localhost:11434")
            
            # Set default provider
            self._default_provider = config.get("default_provider", DEFAULT_PROVIDER)
            
            # Validate model configurations (warn but don't fail)
            self._validate_model_configs()
        
        logger.info(
            f"ModelMeshTool '{tool_name}' initialized with {len(self._model_config)} model configurations, "
            f"default provider: {self._default_provider}"
        )
    
    def _load_prompt_config(self, config_path: str) -> None:
        """
        Load prompt configuration from JSON file.
        
        Args:
            config_path: Path to JSON file containing prompt configurations
            
        Raises:
            FileNotFoundError: If the config file doesn't exist
            json.JSONDecodeError: If the config file is invalid JSON
        """
        try:
            # Resolve path (support both absolute and relative paths)
            if not os.path.isabs(config_path):
                # Try relative to current working directory first
                resolved_path = Path(config_path)
                if not resolved_path.exists():
                    # Try relative to the project root
                    project_root = Path(__file__).parent.parent.parent.parent.parent.parent
                    resolved_path = project_root / config_path
            else:
                resolved_path = Path(config_path)
            
            if not resolved_path.exists():
                raise FileNotFoundError(f"Prompt config file not found: {config_path}")
            
            with open(resolved_path, "r", encoding="utf-8") as f:
                self._prompt_config = json.load(f)
            
            logger.info(f"Loaded prompt configuration from {resolved_path}")
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in prompt config file: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to load prompt config: {e}")
            raise
    
    def _validate_model_configs(self) -> None:
        """
        Validate model configurations and warn about unavailable models.
        This does not fail initialization - it only logs warnings.
        """
        if not self._model_config:
            return
        
        for task_name, model_config in self._model_config.items():
            try:
                # Get model name
                if isinstance(model_config, str):
                    model_name = model_config
                    provider = self._default_provider
                elif isinstance(model_config, dict):
                    model_name = model_config.get("model") or model_config.get("name", "")
                    provider = model_config.get("provider", self._default_provider)
                else:
                    logger.warning(
                        f"Invalid model configuration for task '{task_name}': "
                        f"expected string or dict, got {type(model_config).__name__}"
                    )
                    continue
                
                if not model_name:
                    logger.warning(
                        f"Task '{task_name}' has no model name configured"
                    )
                    continue
                
                # Check if provider is available
                if not ModelProviderFactory.is_provider_available(provider):
                    logger.warning(
                        f"Task '{task_name}' uses provider '{provider}' which is not available. "
                        f"Model '{model_name}' may not work. Install with: "
                        f"pip install {'litellm' if provider == 'litellm' else 'ollama'}"
                    )
                else:
                    logger.debug(
                        f"Task '{task_name}': model '{model_name}' via provider '{provider}' - validated"
                    )
                    
            except Exception as e:
                logger.warning(
                    f"Error validating model config for task '{task_name}': {e}. "
                    f"Tool will still initialize but this task may not work."
                )
    
    def _get_provider_adapter(self, provider_name: str, base_url: Optional[str] = None) -> ModelProviderAdapter:
        """
        Get or create a provider adapter.
        
        Args:
            provider_name: Name of the provider ("litellm" or "ollama")
            base_url: Base URL for the provider (optional, uses default if not provided)
        
        Returns:
            ModelProviderAdapter instance
        
        Raises:
            ValueError: If the provider is not supported
            ImportError: If the provider library is not available
        """
        # Use cache key to reuse adapters with same config
        cache_key = f"{provider_name}:{base_url or self._base_url}"
        
        if cache_key not in self._provider_cache:
            adapter = ModelProviderFactory.create_provider(
                provider_name=provider_name,
                base_url=base_url or self._base_url
            )
            self._provider_cache[cache_key] = adapter
            logger.debug(f"Created {provider_name} adapter (cached)")
        
        return self._provider_cache[cache_key]
    
    def _get_model_config_for_task(self, task: str, model_override: Optional[str] = None) -> Dict[str, Any]:
        """
        Get the model configuration for a given task type.
        
        Args:
            task: Task type (e.g., 'vision', 'speech')
            model_override: Optional model override (can be string or dict)
            
        Returns:
            Dictionary with model configuration:
            {
                "model": "model_name",
                "provider": "litellm" | "ollama",
                "base_url": "http://localhost:11434",
                "options": {...}
            }
            
        Raises:
            ValueError: If no model is configured for the task and no override is provided
        """
        # Handle model override
        if model_override:
            if isinstance(model_override, dict):
                return {
                    "model": model_override.get("model", model_override.get("name", "")),
                    "provider": model_override.get("provider", self._default_provider),
                    "base_url": model_override.get("base_url", self._base_url),
                    "options": model_override.get("options", {})
                }
            else:
                # Simple string override - use default provider
                return {
                    "model": model_override,
                    "provider": self._default_provider,
                    "base_url": self._base_url,
                    "options": {}
                }
        
        # Get model config for task
        model_config = self._model_config.get(task.lower())
        if not model_config:
            available_tasks = ", ".join(self._model_config.keys())
            raise ValueError(
                f"No model configured for task '{task}'. "
                f"Available tasks: {available_tasks}. "
                f"Please configure a model for this task or provide a model_override."
            )
        
        # Handle simple string config (backward compatible)
        if isinstance(model_config, str):
            return {
                "model": model_config,
                "provider": self._default_provider,
                "base_url": self._base_url,
                "options": {}
            }
        
        # Handle dict config (enhanced with provider support)
        if isinstance(model_config, dict):
            return {
                "model": model_config.get("model", model_config.get("name", "")),
                "provider": model_config.get("provider", self._default_provider),
                "base_url": model_config.get("base_url", self._base_url),
                "options": model_config.get("options", {})
            }
        
        raise ValueError(f"Invalid model configuration format for task '{task}'")
    
    def _get_prompt(self, prompt: Optional[str], prompt_key: Optional[str], 
                   prompt_variables: Optional[Dict[str, Any]]) -> str:
        """
        Get the prompt text, either directly or from the config file.
        
        Args:
            prompt: Direct prompt text (if provided)
            prompt_key: Key to look up in prompt config
            prompt_variables: Variables to substitute in template
            
        Returns:
            Final prompt text
            
        Raises:
            ValueError: If neither prompt nor prompt_key is provided
        """
        if prompt:
            return prompt
        
        if not prompt_key:
            raise ValueError(
                "Either 'prompt' or 'prompt_key' must be provided. "
                "If using prompt_key, ensure prompt_config_path is set in tool configuration."
            )
        
        if not self._prompt_config:
            raise ValueError(
                "prompt_config_path must be set in tool configuration to use prompt_key."
            )
        
        # Look up prompt template
        prompt_template = self._prompt_config.get(prompt_key)
        if not prompt_template:
            available_keys = ", ".join(self._prompt_config.keys())
            raise ValueError(
                f"Prompt key '{prompt_key}' not found in config. "
                f"Available keys: {available_keys}"
            )
        
        # Handle both string templates and dict with 'template' field
        if isinstance(prompt_template, dict):
            template = prompt_template.get("template") or prompt_template.get("prompt")
            if not template:
                raise ValueError(f"Prompt config for '{prompt_key}' must contain 'template' or 'prompt' field")
        else:
            template = prompt_template
        
        # Substitute variables if provided
        if prompt_variables and isinstance(template, str):
            try:
                return template.format(**prompt_variables)
            except KeyError as e:
                raise ValueError(f"Missing variable in prompt template: {e}")
        
        return template
    
    async def run(self, arguments: Dict[str, Any]) -> ToolResult:
        """
        Execute the model mesh tool.
        
        Args:
            arguments: Tool arguments containing:
                - task: Task type (required)
                - prompt: Direct prompt (optional)
                - prompt_key: Key for prompt template (optional)
                - prompt_variables: Variables for template (optional)
                - model_override: Override model selection (optional)
                - temperature: Generation temperature (optional)
                - max_tokens: Max tokens to generate (optional)
        
        Returns:
            ToolResult with model response
        """
        try:
            # Normalize arguments
            normalized_args = self._normalize_arguments(arguments)
            
            # Extract parameters
            task = normalized_args.get("task")
            if not task:
                raise ValueError("'task' parameter is required")
            
            prompt = normalized_args.get("prompt")
            prompt_key = normalized_args.get("prompt_key")
            prompt_variables = normalized_args.get("prompt_variables", {})
            model_override = normalized_args.get("model_override")
            temperature = normalized_args.get("temperature", 0.7)
            max_tokens = normalized_args.get("max_tokens", 1000)
            
            # Get the prompt text
            final_prompt = self._get_prompt(prompt, prompt_key, prompt_variables)
            
            # Get the model configuration for this task
            model_config = self._get_model_config_for_task(task, model_override)
            model_name = model_config["model"]
            provider = model_config["provider"]
            base_url = model_config["base_url"]
            config_options = model_config.get("options", {})
            
            # Determine capability description based on task type
            capability_descriptions = {
                "guardian": "Content Safety & Moderation - Analyzes content for safety, toxicity, policy compliance, and risk assessment",
                "vision": "Image Analysis - Analyzes images for objects, scenes, and visual content",
                "text": "Text Processing - Handles text summarization, question answering, and text analysis",
                "speech": "Audio Processing - Transcribes audio and analyzes speech sentiment"
            }
            capability_description = capability_descriptions.get(task.lower(), f"{task.capitalize()} - Specialized task processing")
            
            logger.info(
                f"Routing task '{task}' to model '{model_name}' via provider '{provider}' "
                f"(base_url: {base_url})"
            )
            logger.debug(f"Prompt: {final_prompt[:100]}...")
            logger.debug(f"Model config: {model_config}")
            
            # Get the provider adapter
            try:
                adapter = self._get_provider_adapter(provider, base_url)
            except (ValueError, ImportError) as e:
                # Fallback to default provider if configured provider is not available
                logger.warning(
                    f"Provider '{provider}' not available: {e}. "
                    f"Falling back to default provider '{self._default_provider}'"
                )
                try:
                    adapter = self._get_provider_adapter(self._default_provider, base_url)
                    provider = self._default_provider  # Update provider name for response
                except (ValueError, ImportError) as fallback_error:
                    raise ValueError(
                        f"Provider '{provider}' not available and fallback to "
                        f"'{self._default_provider}' also failed: {fallback_error}"
                    )
            
            # Call the model via the adapter
            try:
                # Optional: Check if model is available (for Ollama provider)
                if provider == "ollama" and hasattr(adapter, "check_model_available"):
                    try:
                        is_available = await adapter.check_model_available(model_name)
                        if not is_available:
                            logger.warning(
                                f"Model '{model_name}' may not be available in Ollama. "
                                f"Available models can be checked with: 'ollama list'. "
                                f"To install: 'ollama pull {model_name}'"
                            )
                    except Exception as check_error:
                        logger.debug(f"Could not verify model availability: {check_error}")
                
                # Prepare adapter-specific kwargs
                adapter_kwargs = {}
                
                # For Ollama adapter, pass think parameter if specified
                if provider == "ollama" and config_options.get("think", False):
                    adapter_kwargs["think"] = True
                
                response_data = await adapter.chat(
                    model_name=model_name,
                    prompt=final_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    options=config_options,
                    **adapter_kwargs
                )
                logger.info(f"Response data: {response_data}")
                
                # Verify model response (if verification info is available)
                if "model_verified" in response_data:
                    if not response_data["model_verified"]:
                        logger.warning(
                            f"Model verification failed: requested '{model_name}' but got response from "
                            f"'{response_data.get('response_model', 'unknown')}'. Response may not be from "
                            f"the designated model."
                        )
                    else:
                        logger.debug(f"Model verification passed: response confirmed from '{model_name}'")
                
                # Add common fields
                response_data["status"] = "success"
                response_data["task"] = task
                response_data["model"] = model_name
                response_data["provider"] = provider
                response_data["prompt"] = final_prompt
                response_data["capability"] = {
                    "task_type": task,
                    "description": capability_description,
                    "prompt_template": prompt_key if prompt_key else "direct_prompt",
                    "model_used": model_name,
                    "provider_used": provider
                }
                
                response = await self._create_success_response(response_data)
                logger.info(f"Response for the model mesh tool: {response}")
                return response
                
            except Exception as e:
                error_msg = str(e)
                error_lower = error_msg.lower()
                
                # Provide more specific error messages based on error type
                if "model" in error_lower and ("not found" in error_lower or "does not exist" in error_lower):
                    detailed_error = (
                        f"Model '{model_name}' is not available in Ollama. "
                        f"This usually means:\n"
                        f"1. The model hasn't been pulled: 'ollama pull {model_name}'\n"
                        f"2. The model name is incorrect (check with 'ollama list')\n"
                        f"3. Common vision model names: 'ibm/granite3.2-vision', 'llava', 'llava:13b'"
                    )
                elif "connection" in error_lower or "refused" in error_lower:
                    detailed_error = (
                        f"Cannot connect to Ollama at {base_url}. "
                        f"Please ensure:\n"
                        f"1. Ollama is running: 'ollama serve'\n"
                        f"2. The base_url is correct: {base_url}\n"
                        f"3. Check if Ollama is accessible: 'curl {base_url}/api/tags'"
                    )
                else:
                    detailed_error = (
                        f"Error calling model '{model_name}' via provider '{provider}': {error_msg}\n"
                        f"Please check:\n"
                        f"1. The model is installed/pulled (e.g., 'ollama pull {model_name}')\n"
                        f"2. The provider '{provider}' is available\n"
                        f"3. Ollama is running (if using Ollama models)\n"
                        f"4. Check available models: 'ollama list'"
                    )
                
                logger.warning(
                    f"Error calling model '{model_name}' via provider '{provider}': {error_msg}"
                )
                
                # Return a graceful error response instead of raising
                error_response = {
                    "status": "error",
                    "task": task,
                    "model": model_name,
                    "provider": provider,
                    "error": error_msg,
                    "error_type": type(e).__name__,
                    "capability": {
                        "task_type": task,
                        "description": capability_description,
                        "prompt_template": prompt_key if prompt_key else "direct_prompt",
                        "model_attempted": model_name,
                        "provider_attempted": provider
                    },
                    "suggestion": detailed_error
                }
                
                error_response = await self._create_success_response(error_response)
                logger.info(f"Error response for the model mesh tool: {error_response}")
                return error_response
            
        except ValidationError as e:
            return self._handle_validation_error(e, arguments)
        except Exception as e:
            return self._handle_unexpected_error(e, arguments)
    
    def _get_guardrails(self) -> List[str]:
        """
        Get guardrails for the model mesh tool.
        
        Returns:
            List of guardrail strings
        """
        return [
            "Always validate task type against configured models",
            "Ensure prompts are properly formatted before sending to models",
            "Handle model errors gracefully and provide meaningful error messages",
            "Respect rate limits and resource constraints for model calls",
            "Validate prompt variables match template placeholders",
            "Verify Ollama models are available before routing requests"
        ]


