"""
LiteLLM Model Provider Adapter

Adapter for using LiteLLM as the model provider.
"""

from typing import Dict, Any, Optional
from mcp_composer.core.tools.model_providers.base import ModelProviderAdapter
from mcp_composer.core.utils import LoggerFactory

logger = LoggerFactory.get_logger()

# Try to import litellm, but handle gracefully if not available
try:
    import litellm
    LITELLM_AVAILABLE = True
except ImportError:
    LITELLM_AVAILABLE = False
    logger.warning("LiteLLM not available. Please install it with: pip install litellm")


class LiteLLMAdapter(ModelProviderAdapter):
    """
    LiteLLM adapter for model provider.
    
    This adapter uses LiteLLM to communicate with models, providing
    a unified interface for multiple model providers.
    """
    
    def __init__(self, base_url: str = "http://localhost:11434"):
        """
        Initialize the LiteLLM adapter.
        
        Args:
            base_url: Base URL for the model API (default: Ollama)
        """
        if not LITELLM_AVAILABLE:
            raise ImportError(
                "LiteLLM is not available. Please install it with: pip install litellm"
            )
        
        self.base_url = base_url
        self._configure_litellm()
    
    def _configure_litellm(self) -> None:
        """Configure LiteLLM settings."""
        try:
            # Set Ollama base URL in environment if using Ollama
            import os
            os.environ.setdefault("OLLAMA_API_BASE", self.base_url)
            
            # Configure LiteLLM settings
            litellm.set_verbose = False  # Set to True for debugging
            
            logger.debug(f"Configured LiteLLM with base URL: {self.base_url}")
            
        except Exception as e:
            logger.warning(f"Failed to configure LiteLLM: {e}")
    
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
        Send a chat request via LiteLLM.
        
        Args:
            model_name: Name of the model (e.g., "llava", "llama2")
            prompt: The prompt text to send
            temperature: Generation temperature (0.0-2.0)
            max_tokens: Maximum number of tokens to generate
            options: Additional options (ignored for LiteLLM, use kwargs)
            **kwargs: Additional LiteLLM parameters
        
        Returns:
            Dictionary with response and usage information
        """
        if not LITELLM_AVAILABLE:
            raise ImportError("LiteLLM is not available")
        
        # Format model name for LiteLLM (assumes Ollama backend)
        # Format: "ollama/model_name"
        litellm_model = f"ollama/{model_name}"
        
        # Prepare messages
        messages = [
            {
                "role": "user",
                "content": prompt
            }
        ]
        
        # Prepare parameters
        params = {
            "model": litellm_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs
        }
        
        # Call LiteLLM
        response = await litellm.acompletion(**params)
        
        # Verify the response came from the requested model
        response_model = getattr(response, 'model', None)
        if response_model:
            # LiteLLM may return model in different format, extract base model name
            response_model_clean = response_model.replace("ollama/", "").replace("ollama:", "")
            model_name_clean = model_name.replace("ollama/", "").replace("ollama:", "")
            if response_model_clean != model_name_clean:
                logger.warning(
                    f"Model mismatch: requested '{model_name}' but response indicates model '{response_model}'. "
                    f"This may indicate a fallback or routing issue."
                )
            else:
                logger.debug(f"Verified response from model: {response_model}")
        
        # Extract response text
        response_text = response.choices[0].message.content
        
        # Extract usage information
        usage_info = {}
        if hasattr(response, 'usage') and response.usage:
            usage_info = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
        
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
            response_model_clean = response_model.replace("ollama/", "").replace("ollama:", "")
            model_name_clean = model_name.replace("ollama/", "").replace("ollama:", "")
            result["model_verified"] = response_model_clean == model_name_clean
            result["response_model"] = response_model
        
        return result
    
    def is_available(self) -> bool:
        """Check if LiteLLM is available."""
        return LITELLM_AVAILABLE
    
    def get_provider_name(self) -> str:
        """Get the provider name."""
        return "litellm"
