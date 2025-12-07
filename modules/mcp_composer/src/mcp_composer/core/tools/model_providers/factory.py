"""
Model Provider Factory

Factory for creating model provider adapters based on configuration.
"""

from typing import Dict, Any, Optional
from mcp_composer.core.tools.model_providers.base import ModelProviderAdapter
from mcp_composer.core.tools.model_providers.litellm_adapter import LiteLLMAdapter
from mcp_composer.core.tools.model_providers.ollama_adapter import OllamaAdapter
from mcp_composer.core.utils import LoggerFactory

logger = LoggerFactory.get_logger()

# Provider registry
PROVIDER_REGISTRY: Dict[str, type[ModelProviderAdapter]] = {
    "litellm": LiteLLMAdapter,
    "ollama": OllamaAdapter,
}

# Default provider
DEFAULT_PROVIDER = "litellm"


class ModelProviderFactory:
    """
    Factory for creating model provider adapters.
    """
    
    @staticmethod
    def create_provider(
        provider_name: str = DEFAULT_PROVIDER,
        base_url: str = "http://localhost:11434"
    ) -> ModelProviderAdapter:
        """
        Create a model provider adapter.
        
        Args:
            provider_name: Name of the provider ("litellm" or "ollama")
            base_url: Base URL for the model API
        
        Returns:
            ModelProviderAdapter instance
        
        Raises:
            ValueError: If the provider is not supported
            ImportError: If the provider library is not available
        """
        provider_name = provider_name.lower()
        
        if provider_name not in PROVIDER_REGISTRY:
            available = ", ".join(PROVIDER_REGISTRY.keys())
            raise ValueError(
                f"Unsupported provider '{provider_name}'. "
                f"Available providers: {available}"
            )
        
        adapter_class = PROVIDER_REGISTRY[provider_name]
        
        try:
            adapter = adapter_class(base_url=base_url)
            logger.info(f"Created {provider_name} adapter with base_url={base_url}")
            return adapter
        except ImportError as e:
            logger.error(f"Failed to create {provider_name} adapter: {e}")
            raise
    
    @staticmethod
    def get_default_provider() -> str:
        """Get the default provider name."""
        return DEFAULT_PROVIDER
    
    @staticmethod
    def get_available_providers() -> list[str]:
        """Get list of available provider names."""
        return list(PROVIDER_REGISTRY.keys())
    
    @staticmethod
    def is_provider_available(provider_name: str) -> bool:
        """
        Check if a provider is available (library installed).
        
        Args:
            provider_name: Name of the provider to check
        
        Returns:
            True if the provider is available, False otherwise
        """
        provider_name = provider_name.lower()
        
        if provider_name not in PROVIDER_REGISTRY:
            return False
        
        adapter_class = PROVIDER_REGISTRY[provider_name]
        
        # Try to create an instance to check availability
        try:
            adapter = adapter_class(base_url="http://localhost:11434")
            return adapter.is_available()
        except Exception:
            return False
