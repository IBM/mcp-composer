"""
Ollama Model Provider Adapter

Adapter for using ollama-python library directly as the model provider.
This provides access to Ollama-specific features like think=True for Guardian models.
"""

from typing import Dict, Any, Optional
from mcp_composer.core.tools.model_providers.base import ModelProviderAdapter
from mcp_composer.core.utils import LoggerFactory

logger = LoggerFactory.get_logger()

# Try to import ollama-python, but handle gracefully if not available
try:
    from ollama import AsyncClient
    OLLAMA_PYTHON_AVAILABLE = True
except ImportError:
    OLLAMA_PYTHON_AVAILABLE = False
    logger.warning("ollama-python not available. Please install it with: pip install ollama")


class OllamaAdapter(ModelProviderAdapter):
    """
    Ollama adapter for model provider.
    
    This adapter uses the ollama-python library directly, providing
    access to Ollama-specific features like think=True for Guardian models.
    """
    
    def __init__(self, base_url: str = "http://localhost:11434"):
        """
        Initialize the Ollama adapter.
        
        Args:
            base_url: Base URL for Ollama API (default: http://localhost:11434)
        """
        if not OLLAMA_PYTHON_AVAILABLE:
            raise ImportError(
                "ollama-python is not available. Please install it with: pip install ollama"
            )
        
        self.base_url = base_url
        self._client = AsyncClient(host=base_url)
    
    async def check_model_available(self, model_name: str) -> bool:
        """
        Check if a model is available in Ollama.
        
        Args:
            model_name: Name of the model to check
            
        Returns:
            True if model is available, False otherwise
        """
        try:
            # List available models
            models = await self._client.list()
            available_models = [model.model for model in models.models]
            
            # Check if exact match or partial match (handles tags)
            model_base = model_name.split(":")[0]  # Remove tag if present
            for available in available_models:
                if available == model_name or available.startswith(model_base):
                    return True
            return False
        except Exception as e:
            logger.warning(f"Could not check model availability: {e}")
            return False  # Assume not available if we can't check
    
    async def chat(
        self,
        model_name: str,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        options: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Send a chat request via ollama-python.
        
        Args:
            model_name: Name of the model (e.g., "ibm/granite3.3-guardian:8b")
            prompt: The prompt text to send
            temperature: Generation temperature (0.0-2.0)
            max_tokens: Maximum number of tokens to generate
            options: Model-specific options (e.g., {"think": True})
            **kwargs: Additional Ollama parameters (e.g., think=True)
        
        Returns:
            Dictionary with response and usage information
        """
        if not OLLAMA_PYTHON_AVAILABLE:
            raise ImportError("ollama-python is not available")
        
        # Merge options: kwargs override options dict
        merged_options = (options or {}).copy()
        
        # Temperature: use provided value
        if temperature is not None:
            merged_options["temperature"] = temperature
        
        # Max tokens: add to options
        if max_tokens is not None:
            merged_options["num_predict"] = max_tokens
        
        # Prepare chat parameters
        chat_params = {
            "model": model_name,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }
        
        # Add think parameter if specified (Guardian models)
        # Can come from options or kwargs
        if kwargs.get("think", False) or merged_options.get("think", False):
            chat_params["think"] = True
        
        # Add options if any
        if merged_options:
            chat_params["options"] = merged_options
        
        # Add any additional kwargs (excluding think which is handled above)
        for key, value in kwargs.items():
            if key not in ["think"] and key not in chat_params:
                chat_params[key] = value
        
        # Call Ollama
        try:
            response = await self._client.chat(**chat_params)
        except Exception as e:
            error_msg = str(e).lower()
            # Provide more helpful error messages for common issues
            if "model" in error_msg and ("not found" in error_msg or "does not exist" in error_msg):
                logger.error(
                    f"Model '{model_name}' not found in Ollama. "
                    f"Please ensure:\n"
                    f"1. Ollama is running: 'ollama serve'\n"
                    f"2. Model is pulled: 'ollama pull {model_name}'\n"
                    f"3. Check available models: 'ollama list'"
                )
            elif "connection" in error_msg or "refused" in error_msg:
                logger.error(
                    f"Cannot connect to Ollama at {self.base_url}. "
                    f"Please ensure Ollama is running: 'ollama serve'"
                )
            raise
        
        # Verify the response came from the requested model
        response_model = getattr(response, 'model', None)
        if response_model and response_model != model_name:
            logger.warning(
                f"Model mismatch: requested '{model_name}' but response indicates model '{response_model}'. "
                f"This may indicate a fallback or routing issue."
            )
        elif response_model:
            logger.debug(f"Verified response from model: {response_model}")
        
        # Extract response content
        response_text = response.message.content
        
        # Extract usage information if available
        usage_info = {}
        if hasattr(response, 'prompt_eval_count') and response.prompt_eval_count is not None:
            usage_info["prompt_tokens"] = response.prompt_eval_count
        if hasattr(response, 'eval_count') and response.eval_count is not None:
            usage_info["completion_tokens"] = response.eval_count
        if usage_info:
            usage_info["total_tokens"] = (
                usage_info.get("prompt_tokens", 0) + 
                usage_info.get("completion_tokens", 0)
            )
        
        # Include model verification in response
        result = {
            "response": response_text,
            "usage": usage_info if usage_info else {
                "prompt_tokens": None,
                "completion_tokens": None,
                "total_tokens": None
            }
        }
        
        # Add model verification info if available
        if response_model:
            result["model_verified"] = response_model == model_name
            result["response_model"] = response_model
        
        return result
    
    def is_available(self) -> bool:
        """Check if ollama-python is available."""
        return OLLAMA_PYTHON_AVAILABLE
    
    def get_provider_name(self) -> str:
        """Get the provider name."""
        return "ollama"
